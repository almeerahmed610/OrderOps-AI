# app/core/security.py

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext


# =========================================================
# SETTINGS
# =========================================================

SECRET_KEY = "orderops-ai-super-secret-key-change-this-later"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


# =========================================================
# PASSWORD HASHING
# =========================================================

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def get_password_hash(password: str) -> str:
    """
    Create a secure password hash.
    """
    return pwd_context.hash(password)


def hash_password(password: str) -> str:
    """
    Alias for compatibility.
    """
    return get_password_hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Verify password against stored hash.
    """
    try:
        return pwd_context.verify(
            plain_password,
            hashed_password,
        )
    except Exception:
        return False


# =========================================================
# JWT TOKEN
# =========================================================

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create JWT access token.
    """

    to_encode = data.copy()

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    expire = datetime.now(timezone.utc) + expires_delta

    to_encode.update(
        {
            "exp": expire,
        }
    )

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return encoded_jwt


# =========================================================
# DECODE JWT TOKEN
# =========================================================

def decode_access_token(
    token: str,
) -> Optional[dict]:
    """
    Validate and decode JWT token.

    Returns payload when valid.
    Returns None when invalid/expired.
    """

    if not token:
        return None

    # Remove Bearer if accidentally passed here
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    # Remove accidental quotation marks
    token = token.strip().strip('"').strip("'")

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        if not payload.get("sub"):
            return None

        return payload

    except JWTError:
        return None

    except Exception:
        return None


# =========================================================
# BACKWARD COMPATIBILITY
# =========================================================

def decode_token(
    token: str,
) -> Optional[dict]:
    """
    Compatibility alias.
    """
    return decode_access_token(token)