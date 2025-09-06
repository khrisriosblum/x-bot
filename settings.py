from __future__ import annotations
from pydantic import BaseSettings, Field
from typing import List

class Settings(BaseSettings):
    # --- X (Twitter) API ---
    X_API_KEY: str = ""
    X_API_SECRET: str = ""
    X_ACCESS_TOKEN: str = ""
    X_ACCESS_SECRET: str = ""
    X_BEARER_TOKEN: str = ""          # opcional si usas OAuth2 user context
    X_AUTH_METHOD: str = Field("oauth1", description="oauth1|oauth2")

    # --- OpenAI (opcional, lo dejaremos desactivado) ---
    OPENAI_API_KEY: str = ""
    USE_OPENAI: bool = False
    OPENAI_MODEL: str = "gpt-4o-mini"

    # --- Datos (ruta del Excel y hoja) ---
    EXCEL_PATH: str = "/app/data/tracks.xlsx"
    EXCEL_SHEET: str = "Sheet1"

    # --- Zona horaria y calendario ---
    TZ: str = "Europe/Madrid"
    DAILY_SLOTS: List[int] = Field(default_factory=lambda: [10, 13, 16, 19, 22])  # horas locales
    DAILY_POSTS: int = 5
    SLOT_JITTER_MINUTES: int = 15  # ±15 min

    # --- Selección de contenido ---
    RECENT_DAYS: int = 60          # prioriza lanzamientos <= 60 días
    NO_REPEAT_DAYS: int = 14       # no repetir mismo YouTubeURL en <=14 días

    # --- Copys / longitud ---
    TARGET_CHARS_MIN: int = 130
    TARGET_CHARS_MAX: int = 220
    DEFAULT_LANG: str = "es"       # idioma por defecto (es/en)

    # --- Etiquetas (mods) neutras sin adjetivos ---
    ALLOWED_MODS_ES: List[str] = Field(default_factory=lambda: [
        "tribal","minimal","acid","dub","jackin","micro","latin","garage","bassline",
        "breaks","vocal","instrumental","tool","groove","afro","chicago","detroit","classic"
    ])
    ALLOWED_MODS_EN: List[str] = Field(default_factory=lambda: [
        "tribal","minimal","acid","dub","jackin","micro","latin","garage","bassline",
        "breaks","vocal","instrumental","tool","groove","afro","chicago","detroit","classic"
    ])
    DEFAULT_MODS_PER_POST_MIN: int = 1
    DEFAULT_MODS_PER_POST_MAX: int = 2

    # --- UTM ---
    ENABLE_UTM: bool = True
    UTM_SOURCE: str = "X"
    UTM_MEDIUM: str = "social"
    UTM_CAMPAIGN_PREFIX: str = "track"

    # --- App / ejecución ---
    DRY_RUN: bool = False           # pon True en Render para probar sin publicar
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
