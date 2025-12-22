"""Encryption utilities for securing user API keys."""

from cryptography.fernet import Fernet

from app.config import get_settings


def get_fernet() -> Fernet:
    """Get Fernet instance with configured key."""
    settings = get_settings()
    if not settings.encryption_key:
        raise ValueError("ENCRYPTION_KEY not configured")
    return Fernet(settings.encryption_key.encode())


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for storage."""
    fernet = get_fernet()
    return fernet.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key for use."""
    fernet = get_fernet()
    return fernet.decrypt(encrypted_key.encode()).decode()
