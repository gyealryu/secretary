"""SQLite 저장소: 설정, 대화, 할 일을 PC 안의 파일 하나에 저장합니다."""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_SETTINGS = {
    # Ollama의 OpenAI 호환 주소. 사내 LLM 서버가 생기면 이 주소만 바꾸면 됩니다.
    "base_url": "http://localhost:11434/v1",
    "model": "qwen2.5-coder:7b",
    "api_key": "",
    # 문서 하나에서 모델에 보낼 최대 글자 수 (로컬 모델은 문맥 길이가 짧음)
    "max_doc_chars": "12000",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    due TEXT,
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
"""


def data_dir() -> Path:
    path = Path(os.environ.get("SECRETARY_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(data_dir() / "secretary.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------- 설정 ----------

def get_settings() -> dict:
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    settings = dict(DEFAULT_SETTINGS)
    settings.update({r["key"]: r["value"] for r in rows})
    return settings


def update_settings(values: dict) -> dict:
    with connect() as conn:
        for key, value in values.items():
            if key in DEFAULT_SETTINGS and value is not None:
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, str(value)),
                )
    return get_settings()


# ---------- 대화 ----------

def list_conversations() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM conversations ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


def create_conversation(title: str = "새 대화") -> dict:
    ts = now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (title, created_at, updated_at) VALUES (?, ?, ?)",
            (title, ts, ts),
        )
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_conversation(conv_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    return dict(row) if row else None


def rename_conversation(conv_id: int, title: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id))


def delete_conversation(conv_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))


def list_messages(conv_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id", (conv_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def add_message(conv_id: int, role: str, content: str) -> None:
    ts = now()
    with connect() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conv_id, role, content, ts),
        )
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (ts, conv_id))


# ---------- 할 일 ----------

def list_tasks() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY done, due IS NULL, due, id"
        ).fetchall()
    return [dict(r) for r in rows]


def create_task(title: str, due: str | None = None) -> dict:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, due, created_at) VALUES (?, ?, ?)",
            (title, due or None, now()),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def update_task(task_id: int, values: dict) -> dict | None:
    allowed = {k: v for k, v in values.items() if k in ("title", "due", "done")}
    with connect() as conn:
        for key, value in allowed.items():
            if key == "done":
                value = 1 if value else 0
            elif key == "due":
                value = value or None
            conn.execute(f"UPDATE tasks SET {key} = ? WHERE id = ?", (value, task_id))
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def delete_task(task_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
