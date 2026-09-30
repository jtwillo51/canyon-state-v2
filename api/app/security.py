"""Passwords and secret tokens: the small primitives sign-in is built on. No database or web code here.

- Passwords are hashed with Argon2id (RFC 9106's recommended profile: 64 MiB, 3 passes, 4 lanes). Only the
  hash is stored; verifying a wrong password takes as long as a right one.
- Password rules follow NIST SP 800-63B: length over complexity (at least 15 characters when a password is the
  only factor), anything printable allowed including spaces, no composition rules, no forced rotation, and a
  check against predictable choices (common words, the person's own name or email).
- Session and link tokens are 256 random bits. Only their SHA-256 is stored, so a leaked database can't be
  used to sign in: the token itself exists only in the person's cookie or link.
"""

import hashlib
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4)  # RFC 9106 profile 2, stated explicitly

MIN_LENGTH = 15  # NIST SP 800-63B-4: single-factor passwords
MAX_LENGTH = 128  # generous for passphrases, while keeping hashing cost bounded

# Hashed once at import, verified against when an email matches no one, so "no such person" takes as long as
# "wrong password" and response times don't reveal who has an account.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(24))

# Words that make a password predictable, however long. What's left after removing them (and digits and
# punctuation) must still be substantial.
_PREDICTABLE = (
    "password", "passw0rd", "qwerty", "asdfgh", "zxcvbn", "letmein", "welcome", "admin", "login", "iloveyou",
    "monkey", "dragon", "sunshine", "princess", "football", "baseball", "master", "shadow", "superman",
    "abc", "abcdef", "canyon", "state", "insurance", "arizona", "chandler", "gilbert", "phoenix", "summer",
    "winter", "spring", "autumn", "fall",
)  # fmt: skip


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """True if `password` matches. With no hash (no such person, or no password set yet), still does the work."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the stored hash used older, weaker settings: rehash it at the next successful sign-in."""
    return _hasher.check_needs_rehash(password_hash)


def password_problem(password: str, *, name: str, email: str) -> str | None:
    """Why this password isn't acceptable, in plain words, or None if it is."""
    if len(password) < MIN_LENGTH:
        return f"Use at least {MIN_LENGTH} characters. A few unrelated words make a strong, memorable password."
    if len(password) > MAX_LENGTH:
        return f"Use at most {MAX_LENGTH} characters."
    lowered = password.lower()
    if len(set(lowered)) < 6:
        return "That repeats too few characters. Try a few unrelated words."
    personal = [p for p in re.split(r"[^a-z0-9]+", f"{name} {email.split('@')[0]}".lower()) if len(p) >= 3]
    if any(p in lowered for p in personal):
        return "Don't include your name or email."
    remainder = lowered
    for word in sorted(_PREDICTABLE, key=len, reverse=True):
        remainder = remainder.replace(word, "")
    remainder = re.sub(r"[\d\W_]+", "", remainder)
    if len(remainder) < 8:
        return "That's too predictable (common words, dates or sequences). Try a few unrelated words."
    return None


def new_token() -> str:
    """A 256-bit random token, URL-safe."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    """What's stored: a fast hash is right here, because the token is already random and unguessable."""
    return hashlib.sha256(token.encode()).hexdigest()


def email_key(email: str) -> str:
    """How sign-in attempts are counted per account, without storing the email itself."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()
