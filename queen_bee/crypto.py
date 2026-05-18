"""密钥加密 — Fernet (AES-128 + HMAC)"""
import os, json
from pathlib import Path
try:
    from cryptography.fernet import Fernet
    HAS_FERNET = True
except ImportError:
    HAS_FERNET = False

_KEY_FILE = Path.home() / ".eva" / "secret.key"

def _get_key() -> bytes:
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    return key

def encrypt(text: str) -> str:
    if not text or not HAS_FERNET: return text
    return Fernet(_get_key()).encrypt(text.encode()).decode()

def decrypt(token: str) -> str:
    if not token or not HAS_FERNET: return token
    try:
        return Fernet(_get_key()).decrypt(token.encode()).decode()
    except Exception:
        return token
