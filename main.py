from __future__ import annotations
from fastapi import FastAPI, Query
from settings import settings
from scheduler import BotScheduler
from utils import log

app = FastAPI(title="x-bot", version="1.0.0")
_scheduler: BotScheduler | None = None

@app.get("/health")
def health():
    return {"status": "ok", "dry_run": settings.DRY_RUN, "tz": settings.TZ}

@app.post("/post-now")
def post_now(slot_index: int = Query(0, ge=0, le=4)):
    """
    Dispara una publicación inmediata sin esperar al horario.
    slot_index: 0..4 (corresponde a 10:00, 13:00, 16:00, 19:00, 22:00)
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = BotScheduler()
        _scheduler.start()
    _scheduler.post_one(slot_index=slot_index)
    return {"status": "triggered", "slot_index": slot_index}

def run_server():
    global _scheduler
    _scheduler = BotScheduler()
    _scheduler.start()

if __name__ == "__main__":
    run_server()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
