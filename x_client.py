from __future__ import annotations
import requests
from requests_oauthlib import OAuth1
from settings import settings

API_BASE = "https://api.x.com/2"

class XClient:
    """
    Cliente simple para publicar texto en X.
    Si DRY_RUN=True, no publica: devuelve el payload simulando el envío.
    """

    def post_text(self, text: str) -> dict:
        payload = {"text": text}

        # Modo simulación (no publica)
        if settings.DRY_RUN:
            return {"dry_run": True, "payload": payload}

        url = f"{API_BASE}/tweets"

        if settings.X_AUTH_METHOD.lower() == "oauth1":
            auth = OAuth1(
                settings.X_API_KEY,
                settings.X_API_SECRET,
                settings.X_ACCESS_TOKEN,
                settings.X_ACCESS_SECRET,
            )
            r = requests.post(url, json=payload, auth=auth, timeout=20)
        else:
            # OAuth2 user context (requiere token de usuario con scope write)
            headers = {
                "Authorization": f"Bearer {settings.X_BEARER_TOKEN}",
                "Content-Type": "application/json",
            }
            r = requests.post(url, json=payload, headers=headers, timeout=20)

        r.raise_for_status()
        return r.json()
