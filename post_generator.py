from __future__ import annotations
import re, random
from typing import Dict, Any
from settings import settings
from utils import fmt_date_ddmmyyyy, pick_hashtags, add_utm, slugify

def _norm(s: str) -> str:
    return (s or "").strip()

def _split_tags(s: str) -> list[str]:
    # separa por comas o espacios
    return [t.lower().lstrip("#").strip() for t in re.split(r"[,\\s]+", s or "") if t.strip()]

def _pick_mods(row_mods: str, lang: str) -> list[str]:
    allowed = settings.ALLOWED_MODS_EN if (lang or "es").lower() == "en" else settings.ALLOWED_MODS_ES
    if row_mods:
        mods = [m for m in _split_tags(row_mods) if m in allowed]
        if mods:
            # máximo 2 por post
            return mods[: settings.DEFAULT_MODS_PER_POST_MAX]
    k = random.randint(settings.DEFAULT_MODS_PER_POST_MIN, settings.DEFAULT_MODS_PER_POST_MAX)
    return random.sample(allowed, k=k)

def _fmt_extras(mods: list[str], bpm: str, key: str) -> str:
    tags = [f"[{m}]" for m in mods]
    if bpm.isdigit():
        tags.append(f"[BPM {bpm}]")
    if key:
        tags.append(f"[Key {key}]")
    return " ".join(tags)

def _fit_length(text: str, url_in_text: str) -> Dict[str, str]:
    """
    Asegura 130–220 caracteres aprox., sin romper el link al final.
    """
    t = text.strip()
    if len(t) < settings.TARGET_CHARS_MIN:
        pad = " Listen in full on YouTube." if "released" in t else " Escúchalo completo en YouTube."
        t = (t.replace(url_in_text, "").strip() + pad + "\n" + url_in_text).strip()
    if len(t) > settings.TARGET_CHARS_MAX:
        if url_in_text in t:
            pre = t.split(url_in_text, 1)[0].rstrip()
            pre = pre[: settings.TARGET_CHARS_MAX - len(url_in_text) - 1]
            t = (pre + "\n" + url_in_text).strip()
        else:
            t = t[: settings.TARGET_CHARS_MAX]
    return {"text": t}

def build_post(row: Dict[str, Any]) -> Dict[str, str]:
    """
    Genera un post neutral (sin adjetivos). Usa etiquetas [mods] y datos objetivos.
    Si el Excel trae 'Mods', 'BPM' o 'Key', se respetan. Si no, elige 1–2 mods neutros.
    """
    title = _norm(row.get("Title"))
    artist = _norm(row.get("Artist"))
    lang = (_norm(row.get("Language")) or settings.DEFAULT_LANG).lower()
    rel = row["ReleaseDate"]  # datetime (viene parseado desde excel_manager)
    url_base = _norm(row["YouTubeURL"])  # URL canónica (sin UTM para control de duplicados)

    # Link con UTM (solo para el texto)
    url_text = url_base
    if settings.ENABLE_UTM:
        campaign = f"{settings.UTM_CAMPAIGN_PREFIX}-{slugify(title)}"
        url_text = add_utm(url_base, settings.UTM_SOURCE, settings.UTM_MEDIUM, campaign)

    # Override manual del copy
    override = _norm(row.get("CopyOverride"))
    if override:
        if url_text and url_text not in override:
            override = f"{override}\n{url_text}"
        out = _fit_length(override, url_text)
        # Devolvemos además la URL canónica para el histórico
        out["youtube_url"] = url_base
        return out

    mods = _pick_mods(_norm(row.get("Mods")), lang)
    bpm = _norm(row.get("BPM"))
    key = _norm(row.get("Key"))
    extras = _fmt_extras(mods, bpm, key)

    hashtags = pick_hashtags(lang)
    date_txt = fmt_date_ddmmyyyy(rel)
    artist_part = f" — {artist}" if artist else ""

    if lang == "en":
        base = f"New on our channel: {title}{artist_part} — released {date_txt}."
    else:
        base = f"Nuevo en el canal: {title}{artist_part} — lanzamiento {date_txt}."

    text = f"{base} {extras} {hashtags}\n{url_text}".strip()
    out = _fit_length(text, url_text)
    # importante: para anti-duplicados guardamos la URL base (sin UTM)
    out["youtube_url"] = url_base
    return out
