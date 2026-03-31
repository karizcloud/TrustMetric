"""
database.py
-----------
SQLite database layer for the Alternative Financial Trust Score System.

Responsibilities:
  - Create and migrate the database schema (users, scores, transactions)
  - Register new users
  - Look up users by email hash
  - Save encrypted score results linked to a user
  - Retrieve and return stored scores for a user

All financial data is stored encrypted — this module only handles raw
storage and retrieval. Encryption/decryption lives in security.py.

Tables
------
    users        — account credentials (email hash + password hash)
    scores       — encrypted score snapshots linked to a user
    transactions — individual transactions linked to a score

Usage
-----
    from database import init_db, save_user, get_user_by_email_hash, save_score, get_scores_for_user
    init_db()   # call once at app startup
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Database file lives next to this module
DB_PATH = Path(__file__).parent / "trust_score.db"


# ---------------------------------------------------------------------------
# SCHEMA CREATION
# ---------------------------------------------------------------------------

_CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email_hash    TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_SCORES_TABLE = """
CREATE TABLE IF NOT EXISTS scores (
    score_id            TEXT PRIMARY KEY,
    user_id             INTEGER NOT NULL,
    encrypted_score_data TEXT   NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

_CREATE_TRANSACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS transactions (
    score_id  TEXT NOT NULL,
    date      TEXT,
    merchant  TEXT,
    amount    REAL,
    category  TEXT,
    FOREIGN KEY (score_id) REFERENCES scores(score_id)
);
"""


def _connect() -> sqlite3.Connection:
    """Open a database connection with row_factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Create all tables if they do not already exist.
    Safe to call on every startup — uses CREATE TABLE IF NOT EXISTS.
    """
    with _connect() as conn:
        conn.execute(_CREATE_USERS_TABLE)
        conn.execute(_CREATE_SCORES_TABLE)
        conn.execute(_CREATE_TRANSACTIONS_TABLE)
        conn.commit()


# ---------------------------------------------------------------------------
# USER OPERATIONS
# ---------------------------------------------------------------------------

def save_user(email_hash: str, password_hash: str) -> int:
    """
    Insert a new user record and return the new user ID.

    Parameters
    ----------
    email_hash    : SHA-256 hex digest of the user's email (from security.py)
    password_hash : PBKDF2/Fernet-derived password hash (from security.py)

    Returns
    -------
    int — the auto-assigned user ID

    Raises
    ------
    ValueError — if the email hash already exists (duplicate account)
    """
    try:
        with _connect() as conn:
            cursor = conn.execute(
                "INSERT INTO users (email_hash, password_hash) VALUES (?, ?)",
                (email_hash, password_hash),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("An account with this email already exists.")


def get_user_by_email_hash(email_hash: str) -> dict | None:
    """
    Look up a user by their hashed email.

    Returns
    -------
    dict with keys: id, email_hash, password_hash, created_at
    or None if no matching user is found.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email_hash = ?", (email_hash,)
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# SCORE OPERATIONS
# ---------------------------------------------------------------------------

def save_score(
    score_id: str,
    user_id: int,
    encrypted_score_data: str,
    transactions: list[dict],
) -> None:
    """
    Persist an encrypted score snapshot and its raw transactions.

    Parameters
    ----------
    score_id             : UUID string identifying this score run
    user_id              : FK to users.id
    encrypted_score_data : Fernet-encrypted JSON string (from security.py)
    transactions         : list of transaction dicts to store alongside
    """
    with _connect() as conn:
        # Insert the encrypted score row
        conn.execute(
            """
            INSERT INTO scores (score_id, user_id, encrypted_score_data)
            VALUES (?, ?, ?)
            """,
            (score_id, user_id, encrypted_score_data),
        )

        # Insert each transaction linked to this score
        conn.executemany(
            """
            INSERT INTO transactions (score_id, date, merchant, amount, category)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    score_id,
                    txn.get("date", ""),
                    txn.get("merchant", ""),
                    txn.get("amount", 0.0),
                    txn.get("category", ""),
                )
                for txn in transactions
            ],
        )
        conn.commit()


def get_scores_for_user(user_id: int) -> list[dict]:
    """
    Retrieve all score records for a given user.

    Returns a list of dicts with keys:
        score_id, user_id, encrypted_score_data, created_at

    The encrypted_score_data must be decrypted by the caller using security.py.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT score_id, user_id, encrypted_score_data, created_at
            FROM scores
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]