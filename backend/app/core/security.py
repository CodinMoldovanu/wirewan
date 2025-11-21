from datetime import datetime, timedelta
from typing import Optional
import base64
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class EncryptionConfigError(Exception):
    """Raised when encryption configuration is missing or invalid."""
    pass


def validate_encryption_config() -> None:
    """Validate that required encryption settings are configured.

    Raises:
        EncryptionConfigError: If ENCRYPTION_KEY or ENCRYPTION_SALT is not set.
    """
    if not settings.ENCRYPTION_KEY:
        raise EncryptionConfigError(
            "ENCRYPTION_KEY is not configured. "
            "Set the ENCRYPTION_KEY environment variable or add it to your .env file. "
            "You can generate a secure key with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    if not settings.ENCRYPTION_SALT:
        raise EncryptionConfigError(
            "ENCRYPTION_SALT is not configured. "
            "Set the ENCRYPTION_SALT environment variable or add it to your .env file. "
            "You can generate a secure salt with: python -c \"import secrets; print(secrets.token_urlsafe(16))\""
        )


def get_encryption_key() -> bytes:
    """Get encryption key for sensitive data.

    Derives a Fernet-compatible key from the configured ENCRYPTION_KEY and ENCRYPTION_SALT
    using PBKDF2 with SHA256.

    Raises:
        EncryptionConfigError: If encryption settings are not configured.
    """
    validate_encryption_config()

    # Derive a proper Fernet key from the provided key and salt
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=settings.ENCRYPTION_SALT.encode(),
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.ENCRYPTION_KEY.encode()))
    return key


_fernet: Optional[Fernet] = None


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_encryption_key())
    return _fernet


def encrypt_value(value: str) -> str:
    """Encrypt a string value."""
    if not value:
        return value
    f = get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str) -> str:
    """Decrypt an encrypted string value."""
    if not encrypted_value:
        return encrypted_value
    f = get_fernet()
    return f.decrypt(encrypted_value.encode()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
