from __future__ import annotations
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional
from utils import is_valid_youtube, log
from settings import settings

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
        self.sheet = sheet or settings.EXCEL_SHEET
        self.df: Optional[pd.DataFrame] = None

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
            df[c] = df[c].fillna("").astype(str)

        # Fechas
        df["ReleaseDate"] = pd.to_datetime(df["ReleaseDate"], errors="coerce")

        # Flags de estado
        df["Posted"] = df.get("Posted", False)
        # si venían como texto/vacío
        df["Posted"] = df["Posted"].fillna(False).astype(bool)

        self.df = df
        log(event="excel_loaded", rows=int(len(df)), path=str(self.path), sheet=self.sheet)
        return df

    def validate_row(self, row) -> bool:
        """Fila válida: URL de YouTube válida + fecha válida."""
        return is_valid_youtube(row["YouTubeURL"]) and pd.notnull(row["ReleaseDate"])

    def mark_posted(self, row_idx: int, when: datetime):
        """Marca la fila como publicada y guarda el Excel."""
        assert self.df is not None, "Debes llamar load() primero"
        self.df.loc[row_idx, "Posted"] = True
        self.df.loc[row_idx, "LastPostedAt"] = when
        self.save()

    def save(self):
        """Escribe el DataFrame de vuelta al Excel."""
        assert self.d
