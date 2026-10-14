"""Worker app. `/drain` and loop mode arrive in PLAN 3.10 (SPEC §9)."""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Plant Advisor worker", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "worker"}
