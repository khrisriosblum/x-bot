from __future__ import annotations
import pandas as pd
from datetime import datetime, timedelta, timezone, time
from pathlib import Path
from typing import Optional
from utils import is_valid_youtube, log
from settings import settings
import random

# ===== Config =====
RECENT_WINDOW_DAYS = 60
COOLDOWN_DAYS = 30  # <-- cooldown de 30 días
UTC = timezone.utc

# Columnas que maneja el bot (algunas son opcionales pero las creamos si faltan)
REQUIRED_COLUMNS = [
    "Title", "YouTubeURL", "ReleaseDate",      # obligatorias (ReleaseDate debe ser válida)
    # enriquecimiento opcional (neutro, sin adjetivos)
    "Artist", "Language", "Mods", "BPM", "Key", "Hashtags", "CopyOverride",
    # estado
    "Posted", "LastPostedAt", "Notes"
]

class ExcelManager:
    def __init__(self, path: str | Path | None = None, sheet: str | None = None):
        self.path = Path(path or settings.EXCEL_PATH)
        self.sheet = sheet or getattr(settings, "EXCEL_SHEET", "Tracks")
        self.df: Optional[pd.DataFrame] = None

    # ---------- IO ----------
    def load(self) -> pd.DataFrame:
        """Lee el Excel y normaliza columnas/tipos."""
        if not self.path.exists():
            raise FileNotFoundError(f"Excel no encontrado en {self.path}")

        # Cargamos todo como string para limpiar, y luego casteamos fechas
        df = pd.read_excel(self.path, sheet_name=self.sheet, dtype=str)

        # Soportar nombre alternativo de fecha
        if "ReleaseDate" not in df.columns and "ReleaseDate (YYYY-MM-DD)" in df.columns:
            df["ReleaseDate"] = df["ReleaseDate (YYYY-MM-DD)"]

        # Crear columnas faltantes
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                df[col] = None

        # Normalizaciones
        df["YouTubeURL"] = df["YouTubeURL"].fillna("").astype(str).str.strip()
        for c in ["Artist", "Language", "Mods", "BPM", "Key", "Hashtags", "CopyOverride", "Notes"]:
            df[c] = (df[c].fillna("").astype(str)) if c in df.columns else ""

        # Fechas (ReleaseDate en fecha sin tz; LastPostedAt en UTC)
        df["ReleaseDate"] = pd.to_datetime(df["ReleaseDate"], errors="coerce")  # datetime64[ns]
        if "LastPostedAt" in df.columns:
            df["LastPostedAt"] = pd.to_datetime(df["LastPostedAt"], errors="coerce", utc=True)
        else:
            df["LastPostedAt"] = pd.NaT

        # Flags de estado
        # si venían como texto/vacío
        if "Posted" not in df.columns:
            df["Posted"] = False
        df["Posted"] = df["Posted"].fillna(False).astype(bool)

        self.df = df
        log(event="excel_loaded", rows=int(len(df)), path=str(self.path), sheet=self.sheet)
        return df

    def save(self):
        """Escribe el DataFrame de vuelta al Excel."""
        assert self.df is not None, "Debes llamar load() primero"
        # Guardamos. openpyxl mantiene formato básico.
        with pd.ExcelWriter(self.path, engine="openpyxl", mode="w") as writer:
            self.df.to_excel(writer, sheet_name=self.sheet, index=False)
        log(event="excel_saved", rows=int(len(self.df)), path=str(self.path), sheet=self.sheet)

    # ---------- Validación / Estado ----------
    def validate_row(self, row) -> bool:
        """Fila válida: URL de YouTube válida + fecha válida."""
        return is_valid_youtube(row["YouTubeURL"]) and pd.notnull(row["ReleaseDate"])

    def mark_posted(self, row_idx: int, when: datetime):
        """Marca la fila como publicada y guarda el Excel."""
        assert self.df is not None, "Debes llamar load() primero"
        # Forzamos UTC en LastPostedAt
        when_utc = when.astimezone(UTC) if when.tzinfo else when.replace(tzinfo=UTC)
        self.df.loc[row_idx, "Posted"] = True
        self.df.loc[row_idx, "LastPostedAt"] = when_utc
        self.save()

    # ---------- Selección (cooldown + prioridad) ----------
    @staticmethod
    def _cooldown_cutoff(now_utc: datetime) -> datetime:
        assert now_utc.tzinfo is not None, "now_utc debe llevar tzinfo=UTC"
        return now_utc - timedelta(days=COOLDOWN_DAYS)

    def eligible_pool(self, now_utc: datetime) -> pd.DataFrame:
        """
        Subconjunto elegible para publicar hoy:
        - Excluye filas con LastPostedAt dentro de los últimos COOLDOWN_DAYS.
        - Requiere ReleaseDate y YouTubeURL válidos.
        - Filtra URLs de YouTube válidas.
        - Deduplica por YouTubeURL quedándose con la más reciente (por ReleaseDate).
        """
        assert self.df is not None, "Debes llamar load() primero"
        df = self.df.copy()

        # Normalización de tipos mínimos
        df["LastPostedAt"] = pd.to_datetime(df.get("LastPostedAt"), errors="coerce", utc=True)
        df["ReleaseDate"] = pd.to_datetime(df.get("ReleaseDate"), errors="coerce")  # naive

        # Filtro cooldown
        cutoff = self._cooldown_cutoff(now_utc)
        recent_block = df["LastPostedAt"].notna() & (df["LastPostedAt"] >= cutoff)
        pool = df[~recent_block].copy()

        # Validaciones mínimas
        pool = pool[pd.notnull(pool["ReleaseDate"]) & pool["YouTubeURL"].astype(str).str.len().gt(0)]
        pool = pool[pool["YouTubeURL"].apply(is_valid_youtube)]

        # Deduplicar por URL (elige la más reciente por ReleaseDate)
        pool.sort_values(by=["ReleaseDate"], ascending=False, inplace=True, kind="stable")
        pool = pool.drop_duplicates(subset=["YouTubeURL"], keep="first")

        pool.reset_index(drop=True, inplace=True)
        return pool

    def pick_daily_set(self, now_local: datetime, now_utc: datetime, k: int = 5) -> pd.DataFrame:
        """
        Devuelve hasta k filas únicas priorizando lanzamientos recientes (últimos 60 días)
        y luego back-catalog, respetando cooldown.
        """
        pool = self.eligible_pool(now_utc=now_utc)
        if pool.empty:
            return pool

        today = now_local.date()
        recent_cut = today - timedelta(days=RECENT_WINDOW_DAYS)

        # ReleaseDate podría venir con hora; pasamos a date
        pool["ReleaseDateDate"] = pd.to_datetime(pool["ReleaseDate"], errors="coerce").dt.date

        recent = pool[pool["ReleaseDateDate"] >= recent_cut].copy()
        backcat = pool[pool["ReleaseDateDate"] < recent_cut].copy()

        # Mezcla aleatoria sin random_state fijo
        if len(recent):
            recent = recent.sample(frac=1)
        if len(backcat):
            backcat = backcat.sample(frac=1)

        chosen = pd.concat([recent, backcat], axis=0).head(k).copy()

        # Si faltan, rellena desde el pool (sin violar cooldown y sin repetir URL)
        if len(chosen) < k:
            extra = pool[~pool["YouTubeURL"].isin(chosen["YouTubeURL"])].sample(frac=1)
            needed = k - len(chosen)
            chosen = pd.concat([chosen, extra.head(needed)], axis=0)

        chosen.reset_index(drop=True, inplace=True)
        return chosen

    # ---------- Utilidades opcionales ----------
    @staticmethod
    def format_ddmmyyyy(dt: pd.Timestamp | datetime) -> str:
        if isinstance(dt, pd.Timestamp):
            dt = dt.to_pydatetime()
        if isinstance(dt, datetime):
            return dt.strftime("%d/%m/%Y")
        # Si vino como date
        return datetime(dt.year, dt.month, dt.day).strftime("%d/%m/%Y")
