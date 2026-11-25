import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import litellm
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from litellm import Cache

APP_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
DB_PATH = DATABASE_URL.replace("sqlite:///", "", 1)
if not DB_PATH.startswith("/"):
    DB_PATH = str((APP_DIR / DB_PATH).resolve())
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
API_KEYS = [k.strip() for k in os.getenv("LLM_API_KEYS", "").split(",") if k.strip()]
DEFAULT_SYSTEM_PROMPT = os.getenv(
    "DEFAULT_SYSTEM_PROMPT",
    "You are a helpful, accurate assistant. Keep answers clear and useful."
)
SIMULATION_ENABLED = os.getenv("ENABLE_FAILURE_SIMULATION", "false").lower() == "true"
CACHE_DIR = os.getenv("LITELLM_CACHE_DIR", "/tmp/lyftr-litellm-cache")
Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

# LiteLLM's disk cache persists across process restarts. The full messages array
# and model form LiteLLM's cache identity; API keys are deliberately not exposed.
litellm.cache = Cache(type="local")
litellm.drop_params = True

app = FastAPI(title="Lyftr AI Chat API", version="1.0.0")
origins = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Simulate-Failure"],
)

@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                system_prompt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id)
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id)")

@app.on_event("startup")
def startup():
    init_db()

class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    system_prompt: Optional[str] = None

    @field_validator("session_id", "message", mode="before")
    @classmethod
    def trim_required(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

def parse_simulation(header: Optional[str]):
    if not header:
        return {}
    if not SIMULATION_ENABLED:
        return {}
    result = {}
    for pair in header.split(","):
        if "=" not in pair:
            continue
        key, status = pair.strip().split("=", 1)
        if status.strip() in {"429", "500", "502", "503"}:
            result[key.strip()] = int(status.strip())
    return result

def response_is_cached(response):
    hidden = getattr(response, "_hidden_params", {}) or {}
    if isinstance(hidden, dict) and hidden.get("cache_hit") is True:
        return True
    # LiteLLM versions may expose this flag directly.
    return getattr(response, "cache_hit", False) is True

def error_status(exc):
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if status is None:
        name = exc.__class__.__name__.lower()
        if "ratelimit" in name:
            return 429
        if "quota" in str(exc).lower():
            return 429
        return 500
    try:
        return int(status)
    except (TypeError, ValueError):
        return 500

def get_history(db, session_id):
    rows = db.execute(
        "SELECT role, content, metadata FROM messages WHERE session_id=? ORDER BY id",
        (session_id,)
    ).fetchall()
    history = []
    for row in rows:
        item = {"role": row["role"], "content": row["content"]}
        if row["role"] == "assistant" and row["metadata"]:
            item["metadata"] = json.loads(row["metadata"])
        history.append(item)
    return history


def call_model(messages, simulation):
    if len(API_KEYS) < 1:
        raise HTTPException(
            status_code=503,
            detail="all providers unavailable"
        )

    failed = 0

    for index, api_key in enumerate(API_KEYS, start=1):
        key_id = f"key_{index}"

        if simulation.get("*") or key_id in simulation:
            failed += 1
            continue

        try:
            kwargs = {
                "model": MODEL,
                "messages": messages,
                "api_key": api_key,
                "caching": not bool(simulation),
                "timeout": float(
                    os.getenv("LLM_TIMEOUT_SECONDS", "45")
                ),
            }

            api_base = os.getenv("LLM_API_BASE")
            if api_base:
                kwargs["api_base"] = api_base

            result = litellm.completion(**kwargs)

            cached = response_is_cached(result)

            usage = getattr(result, "usage", None)
            input_tokens = int(
                getattr(usage, "prompt_tokens", 0) or 0
            )
            output_tokens = int(
                getattr(usage, "completion_tokens", 0) or 0
            )

            reply = result.choices[0].message.content

            if isinstance(reply, list):
                reply = "".join(
                    part.get("text", "")
                    if isinstance(part, dict)
                    else str(part)
                    for part in reply
                )

            if not reply:
                raise RuntimeError(
                    "The model returned an empty response"
                )

            actual_model = getattr(result, "model", None) or MODEL

            return {
                "reply": str(reply),
                "model": actual_model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "key_id": None if cached else key_id,
                "fallback_attempts": 0 if cached else failed,
                "resolution_source": (
                    "LLM_CACHE" if cached else "LIVE_INFERENCE"
                ),
            }

        except Exception as exc:
            status = error_status(exc)

            safe_message = str(exc)
            for secret in API_KEYS:
                if secret:
                    safe_message = safe_message.replace(secret, "[REDACTED]")
            print(
                f"Provider attempt {key_id} failed: "
                f"{type(exc).__name__}; HTTP status={status}; "
                f"Details: {safe_message[:500]}"
        )

            if status in {429, 500, 502, 503}:
                failed += 1
                continue

            raise HTTPException(
                status_code=503,
                detail="all providers unavailable"
            )

    # This line is outside the for loop.
    raise HTTPException(
        status_code=503,
        detail="all providers unavailable"
    )


@app.get("/health")
def health():
    try:
        init_db()
        with connection() as db:
            db.execute("SELECT 1").fetchone()
        if len(API_KEYS) < 1:
            raise HTTPException(status_code=503, detail="provider key pool requires at least two keys")
        return {
            "status": "ok",
            "keys_configured": len(API_KEYS),
            "cache_enabled": True
        }
    except Exception:
        raise HTTPException(status_code=503, detail="service unavailable")

@app.post("/chat")
def chat(payload: ChatRequest, x_simulate_failure: Optional[str] = Header(default=None)):
    if not payload.message.strip() or not payload.session_id.strip():
        raise HTTPException(status_code=422, detail="session_id and message are required")
    if len(payload.message.strip()) > 4000:
        raise HTTPException(status_code=422, detail="message must be at most 4000 characters")
    if len(API_KEYS) < 1:
        raise HTTPException(status_code=503, detail="all providers unavailable")

    started = time.perf_counter()
    init_db()
    with connection() as db:
        session = db.execute(
            "SELECT system_prompt FROM sessions WHERE session_id=?",
            (payload.session_id,)
        ).fetchone()
        if session is None:
            prompt = payload.system_prompt.strip() if payload.system_prompt and payload.system_prompt.strip() else DEFAULT_SYSTEM_PROMPT
            db.execute(
                "INSERT INTO sessions(session_id, system_prompt, created_at) VALUES (?, ?, ?)",
                (payload.session_id, prompt, datetime.now(timezone.utc).isoformat())
            )
        else:
            prompt = session["system_prompt"]
            if payload.system_prompt is not None and payload.system_prompt.strip():
                prompt = payload.system_prompt.strip()
                db.execute("UPDATE sessions SET system_prompt=? WHERE session_id=?", (prompt, payload.session_id))

        history_rows = db.execute(
            "SELECT role, content FROM messages WHERE session_id=? ORDER BY id",
            (payload.session_id,)
        ).fetchall()
        messages = [{"role": "system", "content": prompt}]
        messages.extend({"role": row["role"], "content": row["content"]} for row in history_rows)
        messages.append({"role": "user", "content": payload.message.strip()})

        simulation = parse_simulation(x_simulate_failure)
        result = call_model(messages, simulation)
        latency = max(0, int((time.perf_counter() - started) * 1000))
        metadata = {
            "resolution_source": result["resolution_source"],
            "model": result["model"],
            "latency_ms": latency,
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "key_id": result["key_id"],
            "fallback_attempts": result["fallback_attempts"],
        }
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO messages(session_id, role, content, metadata, created_at) VALUES (?, 'user', ?, NULL, ?)",
            (payload.session_id, payload.message.strip(), now)
        )
        db.execute(
            "INSERT INTO messages(session_id, role, content, metadata, created_at) VALUES (?, 'assistant', ?, ?, ?)",
            (payload.session_id, result["reply"], json.dumps(metadata), now)
        )

    return {"session_id": payload.session_id, "reply": result["reply"], "metadata": metadata}

@app.get("/sessions/{session_id}/messages")
def session_messages(session_id: str):
    init_db()
    with connection() as db:
        exists = db.execute("SELECT 1 FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="session not found")
        return {"session_id": session_id, "messages": get_history(db, session_id)}
@app.get("/sessions")
def list_sessions():
    init_db()

    with connection() as db:
        rows = db.execute("""
            SELECT
                s.session_id,
                s.created_at,
                COUNT(m.id) AS message_count,
                (
                    SELECT content
                    FROM messages
                    WHERE session_id = s.session_id
                    ORDER BY id DESC
                    LIMIT 1
                ) AS last_message
            FROM sessions s
            LEFT JOIN messages m
                ON s.session_id = m.session_id
            GROUP BY s.session_id
            ORDER BY s.created_at DESC
        """).fetchall()

        return {
            "sessions": [
                {
                    "session_id": row["session_id"],
                    "created_at": row["created_at"],
                    "message_count": row["message_count"],
                    "last_message": row["last_message"] or ""
                }
                for row in rows
            ]
        }
