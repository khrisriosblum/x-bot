# post_generator.py
from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from settings import settings

# Hashtags por plataforma
PLATFORM_TAGS = {
    "YouTube":    ["#TechHouse", "#YouTube", "#NewMusic"],
    "Beatport":   ["#TechHouse", "#Beatport", "#OutNow"],
    "AppleMusic": ["#TechHouse", "#AppleMusic", "#NewRelease"],
    "Spotify":    ["#TechHouse", "#Spotify", "#NowPlaying"],
}

def _slug(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in (s or ""))[:60].strip("-")

def _add_utm(url: str, campaign: str) -> str:
    if not settings.USE_UTM:
        return url
    u = urlparse(url)
    q = dict(parse_qsl(u.query))
    q.update({
        "utm_source": settings.UTM_SOURCE,
        "utm_medium": settings.UTM_MEDIUM,
        "utm_campaign": campaign,
    })
    new_q = urlencode(q)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, new_q, u.fragment))

def build_copy(title: str, artist: str | None, lang: str | None, release_dt, platform: str, url: str) -> str:
    # 1) Primera línea FIJA
    headline = settings.FIXED_HEADLINE

    # 2) Info del track (Título — Artista · Fecha DD/MM/YYYY)
    date_str = release_dt.astimezone().strftime("%d/%m/%Y") if isinstance(release_dt, datetime) else ""
    artist_part = f" — {artist}" if artist else ""
    base_info = f"{title}{artist_part} · {date_str}".strip()

    # 3) Hashtags por plataforma
    tags = " ".join(PLATFORM_TAGS.get(platform, ["#TechHouse", "#NewMusic"]))

    # 4) Enlace con UTM opcional
    campaign = f"{_slug(title)}-{platform.lower()}"
    final_url = _add_utm(url, campaign)

    copy = f"{headline}\n{base_info}\n{tags}\n{final_url}"

    # Asegurar <= 280 caracteres (prioriza headline + link)
    if len(copy) > 280:
        reserved = len(headline) + len(tags) + len(final_url) + 3
        max_base = max(10, 280 - reserved)
        if len(base_info) > max_base:
            base_info = base_info[:max_base - 1] + "…"
        copy = f"{headline}\n{base_info}\n{tags}\n{final_url}"
    if len(copy) > 280:
        short_tags = " ".join(PLATFORM_TAGS.get(platform, ["#TechHouse"])[:1])
        copy = f"{headline}\n{base_info}\n{short_tags}\n{final_url}"
    if len(copy) > 280:
        copy = f"{headline}\n{base_info}\n{final_url}"

    return copy
# Compatibilidad con versiones anteriores del scheduler
build_post = build_copy
