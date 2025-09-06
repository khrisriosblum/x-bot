from __future__ import annotations
import sqlite3
from datetime import datetime, date
from typing import Iterable, Optional

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS post_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  youtube_url TEXT NOT NULL,
  posted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_url ON post_history(youtube_url);
CREATE INDEX IF NOT EXISTS idx_history_posted_at ON post_history(posted_at);

CREATE TABLE IF NOT EXISTS daily_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_date TEXT NOT NULL,
  slot_index INTEGER NOT NULL,
  youtube_url TEXT NOT NULL,
  planned_at TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  UNIQUE(run_date, slot_index)
);
"""

class DB:
    def __init__(self, path: str = "xbot.db"):
        self.path = path
        self._ensure()

    def _ensure(self):
        with sqlite3.connect(self.path) as con:
            con.executescript(SCHEMA)

    # ---- Historial de publicaciones ----
    def add_history(self, youtube_url: str, when: datetime):
        with sqlite3.connect(self.path) as con:
            con.execute(
                "INSERT INTO post_history(youtube_url, posted_at) VALUES (?, ?)",
                (youtube_url, when.isoformat())
            )

    def posted_in_last_days(self, urls: Iterable[str], days: int) -> set[str]:
        urls = [u for u in urls if u]
        if not urls:
            return set()
        since_ts = datetime.now().timestamp() - days * 86400
        since_iso = datetime.fromtimestamp(since_ts).isoformat()
        placeholders = ",".join("?" for _ in urls)
        q = (
            f"SELECT DISTINCT youtube_url FROM post_history "
            f"WHERE youtube_url IN ({placeholders}) AND posted_at >= ?"
        )
        with sqlite3.connect(self.path) as con:
            rows = con.execute(q, [*urls, since_iso]).fetchall()
        return {r[0] for r in rows}

    # ---- Cola diaria (slots) ----
    def upsert_queue_item(self, run_date: date, slot_index: int, youtube_url: str, planned_at: Optional[datetime]):
        with sqlite3.connect(self.path) as con:
            con.execute(
                "INSERT INTO daily_queue(run_date, slot_index, youtube_url, planned_at, status) "
                "VALUES (?, ?, ?, ?, 'pending') "
                "ON CONFLICT(run_date, slot_index) DO UPDATE SET "
                "youtube_url=excluded.youtube_url, planned_at=excluded.planned_at",
                (run_date.isoformat(), slot_index, youtube_url, planned_at.isoformat() if planned_at else None)
            )

    def get_queue_for_date(self, run_date: date):
        with sqlite3.connect(self.path) as con:
            rows = con.execute(
                "SELECT slot_index, youtube_url, status FROM daily_queue "
                "WHERE run_date=? ORDER BY slot_index",
                (run_date.isoformat(),)
            ).fetchall()
        return rows

    def claim_queue_item(self, run_date: date, slot_index: int) -> Optional[str]:
        with sqlite3.connect(self.path) as con:
            cur = con.cursor()
            cur.execute(
                "SELECT youtube_url FROM daily_queue "
                "WHERE run_date=? AND slot_index=? AND status='pending'",
                (run_date.isoformat(), slot_index)
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                "UPDATE daily_queue SET status='posting' "
                "WHERE run_date=? AND slot_index=?",
                (run_date.isoformat(), slot_index)
            )
            con.commit()
            return row[0]

    def finish_queue_item(self, run_date: date, slot_index: int, status: str):
        with sqlite3.connect(self.path) as con:
            con.execute(
                "UPDATE daily_queue SET status=? "
                "WHERE run_date=? AND slot_index=?",
                (status, run_date.isoformat(), slot_index)
            )
