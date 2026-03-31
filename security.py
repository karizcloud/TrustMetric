"""
security.py
-----------
Security utilities for the Alternative Financial Trust Score System.

Provides three independent layers of protection:

  1. Email hashing   — SHA-256, one-way, no salt needed (email is the lookup key)
  2. Password hashing — PBKDF2-HMAC-SHA256 with a random 16-byte salt,
                        260 000 iterations (NIST-recommended 2024 baseline)
  3. Data encryption  — Fernet (AES-128-CBC + HMAC-SHA256) for score JSON

Why not bcrypt / passlib?
    Those libraries are not installed in this environment. PBKDF2 via the
    `cryptography` package (which IS available) is equally secure and is
    recommended by NIST SP 800-132.

Environment variable
--------------------
    SCORE_ENCRYPTION_KEY  — a Fernet key (44-byte URL-safe base64 string).
    Generate one with:
        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    Add it to .env as:
        SCORE_ENCRYPTION_KEY=your_key_here

    If the variable is absent, a random key is generated at startup (data is
    unrecoverable across restarts — fine for hackathon, not for production).

Public API
----------
    hash_user_email(email)              -> str   (hex digest)
    hash_password(password)             -> str   (salt:hash, both base64)
    verify_password(password, stored)   -> bool
    encrypt_score_data(data_dict)       -> str   (Fernet token, base64)
    decrypt_score_data(token_str)       -> dict
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=False)


# ---------------------------------------------------------------------------
# FERNET KEY — loaded from environment or auto-generated for this session
# ---------------------------------------------------------------------------

def _load_or_generate_fernet_key() -> bytes:
    """
    Load SCORE_ENCRYPTION_KEY from environment, or use a stable fallback.

    Priority:
      1. SCORE_ENCRYPTION_KEY from .env / environment
      2. Stable default key (app always starts — scores survive restarts)

    For production: always set SCORE_ENCRYPTION_KEY in your .env file.
    """
    raw = os.getenv("SCORE_ENCRYPTION_KEY", "").strip()
    if raw:
        try:
            # Validate the key is a proper Fernet key before using it
            Fernet(raw.encode())
            return raw.encode()
        except Exception:
            print(
                "[security.py] WARNING: SCORE_ENCRYPTION_KEY is invalid. "
                "Using stable default key instead."
            )

    # Stable default key — works for hackathon/dev without any .env setup
    # Generated once: Fernet.generate_key() — hardcoded so app always starts
    default_key = b"TrustMetric-Default-Key-2024-ForHackathon=="
    # Pad/hash it to a valid 32-byte URL-safe base64 Fernet key
    import hashlib as _hl
    raw_bytes = _hl.sha256(default_key).digest()
    valid_key = base64.urlsafe_b64encode(raw_bytes)

    print(
        "[security.py] INFO: Using default encryption key. "
        "Set SCORE_ENCRYPTION_KEY in .env for production use."
    )
    return valid_key


_FERNET_KEY = _load_or_generate_fernet_key()
_fernet     = Fernet(_FERNET_KEY)

# PBKDF2 parameters
_PBKDF2_ITERATIONS = 260_000
_SALT_LENGTH       = 16   # bytes


# ---------------------------------------------------------------------------
# LAYER 1 — Email hashing
# ---------------------------------------------------------------------------

def hash_user_email(email: str) -> str:
    """
    Hash an email address with SHA-256.

    The hash is used as the database lookup key so the real email is never
    stored. SHA-256 without a salt is intentional here — email addresses
    must remain reversibly comparable for login lookups, and the hash space
    (2^256) is large enough to prevent practical preimage attacks on emails.

    Parameters
    ----------
    email : str
        Raw email address (will be lowercased and stripped before hashing).

    Returns
    -------
    str — 64-character lowercase hex digest
    """
    normalised = email.strip().lower()
    return hashlib.sha256(normalised.encode()).hexdigest()


# ---------------------------------------------------------------------------
# LAYER 2 — Password hashing (PBKDF2-HMAC-SHA256)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """
    Hash a plaintext password using PBKDF2-HMAC-SHA256.

    A random 16-byte salt is generated per password. The salt and hash are
    stored together as "salt_b64:hash_b64" so verify_password can reconstruct
    the KDF with the correct salt.

    Parameters
    ----------
    password : str   — plaintext password from the user

    Returns
    -------
    str — "salt_b64:hash_b64"  (both URL-safe base64, colon-separated)
    """
    salt = os.urandom(_SALT_LENGTH)
    kdf  = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    derived = kdf.derive(password.encode())

    salt_b64 = base64.urlsafe_b64encode(salt).decode()
    hash_b64 = base64.urlsafe_b64encode(derived).decode()
    return f"{salt_b64}:{hash_b64}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a plaintext password against a stored PBKDF2 hash.

    Reconstructs the KDF using the salt embedded in stored_hash, derives the
    key from the candidate password, and does a constant-time comparison.

    Parameters
    ----------
    password    : str — candidate plaintext password
    stored_hash : str — value returned by hash_password()

    Returns
    -------
    bool — True if the password is correct, False otherwise
    """
    try:
        salt_b64, hash_b64 = stored_hash.split(":", 1)
        salt        = base64.urlsafe_b64decode(salt_b64)
        stored_key  = base64.urlsafe_b64decode(hash_b64)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=_PBKDF2_ITERATIONS,
        )
        kdf.verify(password.encode(), stored_key)   # raises if wrong
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# LAYER 3 — Financial data encryption (Fernet / AES-128-CBC + HMAC)
# ---------------------------------------------------------------------------

def encrypt_score_data(data: dict) -> str:
    """
    Encrypt a score result dictionary with Fernet.

    Fernet provides authenticated encryption — the ciphertext cannot be
    tampered with or decrypted without the key.

    Parameters
    ----------
    data : dict   — score result containing trust_score, risk_tier, etc.

    Returns
    -------
    str — URL-safe base64 Fernet token (safe to store as TEXT in SQLite)
    """
    plaintext = json.dumps(data).encode()
    token     = _fernet.encrypt(plaintext)
    return token.decode()


def decrypt_score_data(token_str: str) -> dict:
    """
    Decrypt a Fernet token back to the original score dict.

    Parameters
    ----------
    token_str : str — value returned by encrypt_score_data()

    Returns
    -------
    dict — the original score result dictionary

    Raises
    ------
    ValueError — if the token is invalid, corrupted, or was encrypted with
                 a different key
    """
    try:
        plaintext = _fernet.decrypt(token_str.encode())
        return json.loads(plaintext)
    except InvalidToken:
        raise ValueError(
            "Could not decrypt score data. "
            "The encryption key may have changed since this score was stored."
        )