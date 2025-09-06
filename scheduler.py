from __future__ import annotations
from typing import List, Tuple
from datetime import datetime, date, time
import random

import pandas as pd
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from settings import settings
from excel_manager import ExcelManager
from post_generator import build_post
from x_client import XClient
from db import DB
from utils import log


def select_candidates(df: pd.DataFrame, db: DB) -> List[Tuple[int, pd.Series]]:
    """
    Aplica reglas de prioridad:
    1) Solo filas válidas (YouTube + fecha).
    2) Excluye URLs posteadas en <= NO_REPEAT_DAYS.
    3) Prioriza recientes (ReleaseDate dentro de RECENT_DAYS).
    """
    now = pd.Timestamp.now(tz=settings.TZ)
    # Filtrado básico
    df = df.dropna(subset=["ReleaseDate"]).copy()
    df = df[df["YouTubeURL"].str.len() > 0]

    # Anti-duplicados por historial
    urls = df["YouTubeURL"].tolist()
    blocked = db.posted_in_last_days(urls, settings.NO_REPEAT_DAYS)
    if blocked:
        df = df[~df["YouTubeURL"].isin(blocked)]

    if df.empty:
        return []

    # Prioridad por reciente
    recent_cut = now - pd.Timedelta(days=settings.RECENT_DAYS)
    df_recent = df[df["ReleaseDate"] >= recent_cut]
    df_back = df[df["ReleaseDate"] < recent_cut]

    ordered: List[Tuple[int, pd.Series]] = []
    ordered.extend(list(df_recent.iterrows()))
    ordered.extend(list(df_back.iterrows()))
    return ordered


class BotScheduler:
    def __init__(self):
        self.tz = pytz.timezone(settings.TZ)
        self.scheduler = BackgroundScheduler(timezone=self.tz)
        self.db = DB()
        self.excel = ExcelManager()
        self.client = XClient()

    def start(self):
        # Slots horarios con jitter ±N minutos (convertido a segundos)
        for i, hour in enumerate(settings.DAILY_SLOTS):
            trig = CronTrigger(
                hour=hour, minute=0,
                jitter=settings.SLOT_JITTER_MINUTES * 60,
                timezone=self.tz,
            )
            self.scheduler.add_job(
                self.post_one, trigger=trig, kwargs={"slot_index": i}, id=f"slot-{i}"
            )

        # Construye la cola cada día a las 00:05
        self.scheduler.add_job(
            self.build_daily_queue,
            trigger=CronTrigger(hour=0, minute=5, timezone=self.tz),
            id="plan-daily",
        )

        self.scheduler.start()
        log(event="scheduler_started", slots=settings.DAILY_SLOTS, tz=settings.TZ)

    def build_daily_queue(self):
        today = date.today()
        df = self.excel.load()
        candidates = select_candidates(df, self.db)
        if not candidates:
            log(event="no_candidates_today")
            return

        chosen: List[Tuple[int, pd.Series]] = []
        seen_urls = set()
        for idx, row in candidates:
            if len(chosen) >= settings.DAILY_POSTS:
                break
            url = row["YouTubeURL"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            chosen.append((idx, row))

        # Planifica en slots
        for slot_index, (_, row) in enumerate(chosen[: settings.DAILY_POSTS]):
            planned_at = self._localize_datetime(today, hour=settings.DAILY_SLOTS[slot_index])
            self.db.upsert_queue_item(today, slot_index, row["YouTubeURL"], planned_at)

        log(event="daily_queue_built", count=len(chosen), date=str(today))

    def post_one(self, slot_index: int):
        """
        Publica 1 post (o simula si DRY_RUN=True).
        - Intenta tomar de la cola diaria.
        - Si no hay, selecciona al vuelo respetando reglas.
        """
        now = datetime.now(self.tz)
        today = date.today()

        # 1) Intentar obtener URL de la cola
        url_from_queue = self.db.claim_queue_item(today, slot_index)

        # 2) Cargar Excel y localizar fila candidata
        df = self.excel.load()

        row = None
        if url_from_queue:
            matches = df[df["YouTubeURL"] == url_from_queue]
            if not matches.empty:
                _, row = next(iter(matches.iterrows()))
            else:
                log(event="queue_url_missing_in_excel", url=url_from_queue)

        if row is None:
            # Selección al vuelo
            candidates = select_candidates(df, self.db)
            if not candidates:
                log(event="skip_no_candidates", slot_index=slot_index)
                self.db.finish_queue_item(today, slot_index, "skipped")
                return
            # Elige aleatorio entre los primeros 20 (para variar)
            pick_idx, row = random.choice(candidates[: min(20, len(candidates))])

        # 3) Generar post neutral con mods
        post = build_post(row)
        text = post["text"]
        base_url = post["youtube_url"]

        # 4) Enviar (o simular) a X
        res = self.client.post_text(text)

        # 5) Persistir resultados
        if settings.DRY_RUN:
            # En simulación no marcamos historial ni Excel
            self.db.finish_queue_item(today, slot_index, "dry_run")
            log(event="posted_dry_run", slot_index=slot_index, response=res)
        else:
            # Guardar historial anti-duplicados y marcar Excel
            self.db.add_history(base_url, now)
            self._mark_excel_posted(base_url, now)
            self.db.finish_queue_item(today, slot_index, "posted")
            log(event="posted", slot_index=slot_index, response=res)

    # ----------------- Helpers -----------------

    def _localize_datetime(self, d: date, hour: int) -> datetime:
        naive = datetime(d.year, d.month, d.day, hour, 0, 0)
        return self.tz.localize(naive)

    def _mark_excel_posted(self, youtube_url: str, when: datetime):
        # Marca la PRIMERA fila que coincida con la URL dada
        self.excel.load()
        assert self.excel.df is not None
        for idx, row in self.excel.iter_valid_rows():
            if row["YouTubeURL"] == youtube_url:
                self.excel.mark_posted(idx, when)
                break
