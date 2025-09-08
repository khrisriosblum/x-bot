# settings.py
from __future__ import annotations

import os
from pydantic import BaseSettings, Field
from typing import List

class Settings(BaseSettings):
    # ---------------------------
    # Horarios / Scheduler
    # ---------------------------
    TZ: str = Field(default="Europe/Madrid")
    START_SCHEDULER: bool = Field(default=True)
    SLOTS_LOCAL: str = Field(default="10:00,13:00,16:00,19:00,22:00")
    SLOT_JITTER_MINUTES: int = Field(default=15)
    CARD_WARMUP_SECONDS: int = Field(default=0)

    # ---------------------------
    # Selección / Anti-duplicado
    # ---------------------------
    PLATFORMS_ENABLED: str = Field(default="YouTube,Beatport,AppleMusic,Spotify")
    RECENT_DAYS_PRIORITY: int = Field(default=60)
    COOLDOWN_DAYS_PER_URL: int = Field(default=30)

    # ---------------------------
    # Copy / UTM
    # ---------------------------
    FIXED_HEADLINE: str = Field(default="¡Only Techouse For You!")
    USE_UTM: bool = Field(default=True)
    UTM_SOURCE: str = Field(default="X")
    UTM_MEDIUM: str = Field(default="social")

    # ---------------------------
    # X API / Auth
    # ---------------------------
    X_AUTH_METHOD: str = Field(default="oauth2")  # oauth1 | oauth2
    X_BEARER_TOKEN: str = Field(default="")
    X_API_KEY: str = Field(default="")
    X_API_SECRET: str = Field(default="")
    X_ACCESS_TOKEN: str = Field(default="")
    X_ACCESS_SECRET: str = Field(default="")

    # ---------------------------
    # Publicación
    # ---------------------------
    PREVIEW_WAIT_SECONDS: int = Field(default=15)   # espera PRE-publicación (tras pegar el enlace)
    DRY_RUN: bool = Field(default=False)

    # ---------------------------
    # Excel / Paths
    # ---------------------------
    EXCEL_PATH: str = Field(default="./data/tracks.xlsx")

    # ---------------------------
    # Miniatura opcional YouTube
    # ---------------------------
    ATTACH_THUMBNAIL: bool = Field(default=False)
    THUMBNAIL_QUALITY: str = Field(default="hqdefault")  # maxresdefault|sddefault|hqdefault|mqdefault|default

    class Config:
        env_file = ".env"
        case_sensitive = False

    # Helpers convenientes
    @property
    def platforms(self) -> List[str]:
        return [s.strip() for s in self.PLATFORMS_ENABLED.split(",") if s.strip()]

# instancia global
settings = Settings()
