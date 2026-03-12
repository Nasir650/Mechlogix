import json
import sqlite3
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "mechlogix.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                preferred_llm TEXT NOT NULL DEFAULT 'Gemini',
                theme TEXT NOT NULL DEFAULT 'dark',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                input_type TEXT NOT NULL,
                input_text TEXT NOT NULL,
                raw_response TEXT NOT NULL,
                parsed_json TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "theme" not in columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN theme TEXT NOT NULL DEFAULT 'dark'"
            )


def utcnow():
    return datetime.utcnow().replace(microsecond=0).isoformat()


def row_to_dict(row):
    return dict(row) if row else None


def create_user(name, email, password_hash, preferred_llm="Gemini", theme="dark"):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (name, email, password_hash, preferred_llm, theme, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, email.lower().strip(), password_hash, preferred_llm, theme, utcnow()),
        )
        return cursor.lastrowid


def get_user_by_email(email):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()
    return row_to_dict(row)


def get_user_by_id(user_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return row_to_dict(row)


def get_or_create_google_user(name, email):
    user = get_user_by_email(email)
    if user:
        if name and user["name"] != name:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE users SET name = ? WHERE id = ?",
                    (name, user["id"]),
                )
            user["name"] = name
        return user

    user_id = create_user(
        name=name or email.split("@")[0],
        email=email,
        password_hash="",
        theme="dark",
    )
    return get_user_by_id(user_id)


def update_user(user_id, name, email, preferred_llm, theme):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET name = ?, email = ?, preferred_llm = ?, theme = ?
            WHERE id = ?
            """,
            (name.strip(), email.lower().strip(), preferred_llm, theme, user_id),
        )


def create_plan(user_id, title, input_type, input_text, raw_response, parsed_json, status):
    parsed_payload = json.dumps(parsed_json) if parsed_json is not None else None
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO plans (
                user_id, title, input_type, input_text, raw_response,
                parsed_json, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                title,
                input_type,
                input_text,
                raw_response,
                parsed_payload,
                status,
                utcnow(),
            ),
        )
        return cursor.lastrowid


def get_plan_for_user(plan_id, user_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM plans WHERE id = ? AND user_id = ?",
            (plan_id, user_id),
        ).fetchone()
    return row_to_dict(row)


def delete_plan_for_user(plan_id, user_id):
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM plans WHERE id = ? AND user_id = ?",
            (plan_id, user_id),
        )
        return cursor.rowcount > 0


def get_recent_plans(user_id, limit=5):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM plans
            WHERE user_id = ?
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_dashboard_stats(user_id):
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM plans WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        completed = conn.execute(
            "SELECT COUNT(*) FROM plans WHERE user_id = ? AND status = 'completed'",
            (user_id,),
        ).fetchone()[0]
        last_activity = conn.execute(
            """
            SELECT created_at FROM plans
            WHERE user_id = ?
            ORDER BY datetime(created_at) DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return {
        "total_plans": total,
        "completed_plans": completed,
        "last_activity": last_activity["created_at"] if last_activity else None,
    }
