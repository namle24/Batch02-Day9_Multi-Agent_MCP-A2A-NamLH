from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from .supervisor_workers import ask
except ImportError:  # Allows running this file directly during quick demos.
    from supervisor_workers import ask


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Day08 Supervisor-Workers Assignment")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=8)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/ask")
def ask_api(payload: AskRequest):
    response = ask(payload.question, top_k=payload.top_k)
    return {
        "answer": response.answer,
        "route": response.route,
        "trace": response.trace,
        "latency_ms": round(response.latency_ms, 2),
        "worker_latencies_ms": response.worker_latencies_ms,
        "mode": response.mode,
        "model": response.model,
        "evidence": [asdict(item) for item in response.evidence],
    }

