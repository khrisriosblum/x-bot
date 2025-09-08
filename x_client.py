# x_client.py
from __future__ import annotations

import logging
import time
from typing import Optional, List

import requests
from requests_oauthlib import OAuth1
from urllib.parse import urlparse, parse_qs

from settings import settings

API_BASE = "https://api.x.com/2"
UPLOAD_BASE_V11 = "https://upload.twitter.com/1.1"

logger = logging.getLogger("xbot")


class XClient:
    """
    Cliente para publicar en X.
    - Espera PREVIA a publicar: settings.PREVIEW_WAIT_SECONDS (por defecto 15 s).
    - DRY_RUN=True: no publica, devuelve payload simulado.
    - Soporta OAuth1 (user context) y OAuth2 Bearer (X_BEARER_TOKEN) según settings.X_AUTH_METHOD.
    - Opcional: subir miniatura de YouTube si ATTACH_THUMBNAIL=true (requiere OAuth1 para media v1.1).
    """

    # ---------------------------
    # Autenticación
    # ---------------------------
    def _oauth1_auth(self) -> OAuth1:
        return OAuth1(
            settings.X_API_KEY,
            settings.X_API_SECRET,
            settings.X_ACCESS_TOKEN,
            settings.X_ACCESS_SECRET,
        )

    def _oauth2_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {settings.X_BEARER_TOKEN}",
            "Content-Type": "application/json",
        }

    # ---------------------------
    # Publicación
    # ---------------------------
    def post_text(self, text: str, media_ids: Optional[List[str]] = None) -> dict:
        """
        Publica un tweet con texto (y media opcional).
        IMPORTANTE: Esperamos PRE-publicación tras construir el texto (y pegar el enlace)
        para dar tiempo a que X procese la tarjeta de enlace.
        """
        payload: dict = {"text": text}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}

        # Espera PRE-publicación (tras escribir el texto y pegar el enlace)
        if not settings.DRY_RUN and settings.PREVIEW_WAIT_SECONDS > 0:
            logger.info(
                {"event": "pre_publish_wait", "seconds": settings.PREVIEW_WAIT_SECONDS}
            )
            time.sleep(settings.PREVIEW_WAIT_SECONDS)

        # Modo simulación (no publica)
        if settings.DRY_RUN:
            logger.info({"event": "dry_run_create_post", "payload": payload})
            return {"dry_run": True, "payload": payload}

        url = f"{API_BASE}/tweets"
        if settings.X_AUTH_METHOD.lower() == "oauth1":
            r = requests.post(url, json=payload, auth=self._oauth1_auth(), timeout=20)
        else:
            r = requests.post(url, json=payload, headers=self._oauth2_headers(), timeout=20)

        if r.status_code >= 400:
            logger.error({"event": "x_api_error", "status": r.status_code, "body": r.text})
        r.raise_for_status()
        return r.json()

    # ---------------------------
    # Miniatura opcional (YouTube)
    # ---------------------------
    def prepare_thumbnail_if_enabled(self, url: str, platform: str) -> Optional[List[str]]:
        """
        Si settings.ATTACH_THUMBNAIL=True y platform == "YouTube", intenta subir la miniatura
        y devuelve [media_id] para adjuntarla al post. Devuelve None si no aplica.
        Nota: La subida de media v1.1 normalmente requiere OAuth1 (user context).
        """
        if not getattr(settings, "ATTACH_THUMBNAIL", False):
            return None
        if platform != "YouTube":
            return None

        vid = self._extract_yt_id(url)
        if not vid:
            return None

        quality = getattr(settings, "THUMBNAIL_QUALITY", "hqdefault")
        thumb_url = f"https://img.youtube.com/vi/{vid}/{quality}.jpg"
        try:
            img = requests.get(thumb_url, timeout=15)
            if not img.ok:
                logger.warning({"event": "thumb_fetch_failed", "status": img.status_code})
                return None
        except Exception as e:
            logger.warning({"event": "thumb_fetch_exception", "error": str(e)})
            return None

        # Subida de media: prioriza OAuth1. Con OAuth2 Bearer suele NO ser válida en v1.1
        if settings.X_AUTH_METHOD.lower() != "oauth1":
            logger.warning(
                {
                    "event": "thumb_upload_skipped",
                    "reason": "media_upload_requires_oauth1",
                }
            )
            return None

        try:
            media_id = self._upload_image_v11(img.content, img.headers.get("Content-Type", "image/jpeg"))
            return [media_id] if media_id else None
        except Exception as e:
            logger.warning({"event": "thumb_upload_failed", "error": str(e)})
            return None

    # ---------------------------
    # Helpers YouTube
    # ---------------------------
    def _extract_yt_id(self, url: str) -> Optional[str]:
        u = urlparse(url)
        if u.netloc in ("youtu.be", "www.youtu.be"):
            return u.path.lstrip("/") or None
        if "youtube.com" in u.netloc:
            if u.path == "/watch":
                return parse_qs(u.query).get("v", [None])[0]
            for prefix in ("/shorts/", "/embed/"):
                if u.path.startswith(prefix):
                    parts = u.path.split("/")
                    return parts[2] if len(parts) > 2 else None
        return None

    # ---------------------------
    # Subida de imágenes (v1.1)
    # ---------------------------
    def _upload_image_v11(self, image_bytes: bytes, media_type: str = "image/jpeg") -> str:
        """
        Sube imagen a media upload v1.1 (normalmente requiere OAuth1 user context).
        Devuelve media_id_string.
        """
        if settings.DRY_RUN:
            logger.info({"event": "dry_run_media_upload"})
            return "0"

        url = f"{UPLOAD_BASE_V11}/media/upload.json"
        files = {"media": ("thumb.jpg", image_bytes, media_type)}
        auth = self._oauth1_auth()
        r = requests.post(url, files=files, auth=auth, timeout=30)
        r.raise_for_status()
        data = r.json()
        media_id = data.get("media_id_string") or data.get("media_id")
        if not media_id:
            raise RuntimeError(f"Media upload sin media_id: {data}")
        return str(media_id)
