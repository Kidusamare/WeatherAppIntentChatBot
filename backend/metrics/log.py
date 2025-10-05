from __future__ import annotations

import os
import json
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any, Dict


def _db_path() -> Path:
    path = os.getenv("WEATHER_BOT_DB_PATH")
    if path:
        return Path(path)
    # default under data/
    return Path(__file__).resolve().parents[1] / "data" / "metrics.sqlite"


_INITIALIZED: Dict[Path, bool] = {}
_INIT_LOCK = Lock()


def init_db(path: Path | None = None) -> None:
    db = (path or _db_path()).resolve()
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db), timeout=5) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interactions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts DATETIME DEFAULT CURRENT_TIMESTAMP,
              session_id TEXT,
              text TEXT,
              intent TEXT,
              confidence REAL,
              latency_ms INTEGER,
              entities_json TEXT,
              reply_snippet TEXT
            )
            """
        )
        conn.commit()


def _ensure_db(db: Path | None = None) -> Path:
    resolved = (db or _db_path()).resolve()
    with _INIT_LOCK:
        if _INITIALIZED.get(resolved):
            return resolved
        init_db(resolved)
        _INITIALIZED[resolved] = True
        return resolved


def log_interaction(
    *,
    session_id: str,
    text: str,
    intent: str,
    confidence: float,
    latency_ms: int,
    entities: Dict[str, Any],
    reply: str,
    path: Path | None = None,
) -> None:
    db = _ensure_db(path)
    snippet = (reply or "")[:200]
    with sqlite3.connect(str(db), timeout=5) as conn:
        conn.execute(
            """
            INSERT INTO interactions(session_id, text, intent, confidence, latency_ms, entities_json, reply_snippet)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                text,
                intent,
                float(confidence),
                int(latency_ms),
                json.dumps(entities, ensure_ascii=False),
                snippet,
            ),
        )
        conn.commit()
