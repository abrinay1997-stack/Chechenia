from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "users.db"


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
    ).hex()


@contextmanager
def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def user_exists(email: str) -> bool:
    email = normalize_email(email)
    if not email:
        return False
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE email = ? LIMIT 1", (email,)
        ).fetchone()
    return row is not None


def create_user(email: str, password: str) -> tuple[bool, str]:
    email = normalize_email(email)
    if not email or "@" not in email:
        return False, "invalid_email"
    if len(password) < 8:
        return False, "weak_password"
    if user_exists(email):
        return False, "already_registered"

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO users (email, salt, password_hash) VALUES (?, ?, ?)",
                (email, salt, password_hash),
            )
    except sqlite3.IntegrityError:
        return False, "already_registered"
    return True, "created"


def seed_if_empty() -> list[str]:
    """Seed a few demo accounts so the checker has something to find."""
    init_db()
    samples = [
        "ana@chechenia.local",
        "carlos@chechenia.local",
        "soporte@chechenia.local",
    ]
    created = []
    for email in samples:
        ok, _ = create_user(email, "DemoPass123")
        if ok:
            created.append(email)
    return created


def count_users() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
    return int(row["n"] if row else 0)
