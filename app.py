"""Lien d'avis direct — petit serveur FastAPI.

Sert la page lien-avis.html et ouvre les liens courts Google Maps
(maps.app.goo.gl) pour retrouver le long lien du commerce.

Lancer :  .venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
"""
from pathlib import Path
from urllib.parse import urlparse
import urllib.request

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

PAGE = Path(__file__).with_name("lien-avis.html")
ALLOWED_HOSTS = {"maps.app.goo.gl", "goo.gl"}
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"

app = FastAPI(title="Lien d'avis direct")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    body = PAGE.read_text(encoding="utf-8")
    return (
        "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">"
        "</head><body>" + body + "</body></html>"
    )


class _Collect(urllib.request.HTTPRedirectHandler):
    """Garde chaque adresse de redirection et s'arrête dès que le code du commerce apparaît."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.urls.append(newurl)
        if "0x" in newurl and ":0x" in newurl:
            return None  # on a ce qu'il faut, inutile d'aller plus loin
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@app.get("/api/resolve")
def resolve(url: str = Query(..., max_length=300)) -> dict:
    host = (urlparse(url).hostname or "").lower()
    if urlparse(url).scheme not in ("http", "https") or host not in ALLOWED_HOSTS:
        raise HTTPException(400, "Seuls les liens maps.app.goo.gl sont acceptés.")
    collector = _Collect()
    opener = urllib.request.build_opener(collector)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr"})
    try:
        with opener.open(req, timeout=10) as resp:
            collector.urls.append(resp.geturl())
    except urllib.error.HTTPError as e:
        # Redirection arrêtée volontairement : l'adresse utile est déjà gardée
        if not collector.urls:
            raise HTTPException(502, f"Google a répondu {e.code}.")
    except Exception:
        if not collector.urls:
            raise HTTPException(502, "Impossible d'ouvrir ce lien court.")
    for u in reversed(collector.urls):
        if "0x" in u and ":0x" in u:
            return {"url": u}
    return {"url": collector.urls[-1] if collector.urls else url}
