"""
ForecastIQ Authentication & Security Utilities
Password hashing with bcrypt and secure session token generation.
"""
import hashlib
import secrets
from datetime import datetime, timedelta
import bcrypt


def hash_password(password: str) -> str:
    """Hash plaintext password using bcrypt with salt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def generate_session_token() -> str:
    """Generate a high-entropy cryptographically secure random session token."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Hash the session token using SHA-256 before saving to MongoDB."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
