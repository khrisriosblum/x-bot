import json, logging, re, unicodedata
from urllib.parse import urlparse, urlencode, urlunparse, parse_qsl
from datetime import datetime
import random

# ---------- Logger JSON ----------
class JSONLogger:
    def __init__(self, name: str, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(handler)

    def log(self, **kwargs):
        # imprime JSON en una línea (apto para Render/Railway)
        self.logger.info(json.dumps(kwargs, ensure_ascii=False))

log = JSONLogger("x-bot").log

# ---------- Validaciones y utilidades ----------
_YT_RE = re.compile(r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/", re.IGNORECASE)

def is_valid_youtube(url: str) -> bool:
    return bool(url and _YT_RE.match(url.strip()))

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:60] or "track"

def add_utm(url: str, source: str, medium: str, campaign: str) -> str:
    if not url:
        return url
    parts = list(urlparse(url))
    q = dict(parse_qsl(parts[4]))
    q.update({"utm_source": source, "utm_medium": medium, "utm_campaign": campaign})
    parts[4] = urlencode(q)
    return urlunparse(parts)

def fmt_date_ddmmyyyy(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y")

def pick_hashtags(language: str) -> str:
    base_es = ["#TechHouse", "#NewMusic", "#YouTube", "#Club", "#Estreno"]
    base_en = ["#TechHouse", "#NewMusic", "#YouTube", "#Club", "#OutNow"]
    base = base_en if (language or "es").lower() == "en" else base_es
    sample = random.sample(base, k=min(3, len(base)))
    # quitar duplicados preservando orden
    seen = set()
    ordered = []
    for t in sample:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return " ".join(ordered)
