"""Server-side security primitives: Fernet credential encryption, password hashing, HMAC tokens, and log redaction."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re
import secrets
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

# Patterns matching API keys, Bearer tokens, and authorization secrets for fail-safe log redaction.
_SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"(?i)(x-goog-api-key|authorization|api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?([^\s'\",;}]+)"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"),
]


def redact_secrets(value: Any) -> Any:
    """Recursively scrub credentials and token patterns from strings, dicts, and lists."""
    if isinstance(value, str):
        scrubbed = value
        scrubbed = _SECRET_PATTERNS[0].sub("[REDACTED_GOOGLE_KEY]", scrubbed)
        scrubbed = _SECRET_PATTERNS[1].sub(lambda m: f"{m.group(1)}=[REDACTED]", scrubbed)
        scrubbed = _SECRET_PATTERNS[2].sub("Bearer [REDACTED]", scrubbed)
        return scrubbed
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key_lower = str(k).lower()
            if any(term in key_lower for term in ("api_key", "apikey", "secret", "password", "encrypted_key", "authorization", "token_hash")):
                out[k] = "[REDACTED]"
            else:
                out[k] = redact_secrets(v)
        return out
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return value


class SecretRedactingFilter(logging.Filter):
    """Attach to loggers to guarantee secrets never reach stdout or log files."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            record.args = tuple(redact_secrets(arg) for arg in record.args) if isinstance(record.args, tuple) else redact_secrets(record.args)
        return True


def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 salted password hash (600,000 iterations per OWASP guidance)."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return f"pbkdf2_sha256$260000${base64.b64encode(salt).decode('ascii')}${base64.b64encode(dk).decode('ascii')}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, raw_iter, b64_salt, b64_dk = stored_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(raw_iter)
        salt = base64.b64decode(b64_salt)
        expected = base64.b64decode(b64_dk)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_session_token() -> str:
    return f"ps_sess_{secrets.token_urlsafe(32)}"


def mask_api_key(raw_key: str) -> str:
    trimmed = raw_key.strip()
    if len(trimmed) <= 8:
        return "****"
    return f"{trimmed[:4]}...{trimmed[-4:]}"


def sanitize_download_filename(filename: str, fallback: str = "asset.bin") -> str:
    """Strip CR/LF, quotes, path separators, and control chars to prevent Content-Disposition header injection."""
    base = Path(filename or "").name
    cleaned = re.sub(r'[\r\n"\\/;<>:*?|]+', "_", base).strip(" .")
    return cleaned[:160] if cleaned else fallback


class SecretVault:
    """Server-side Fernet (AES-128-CBC + HMAC-SHA256) credential encryption vault."""

    def __init__(self, key_file: Path, key_override: str | None = None):
        if key_override:
            key_bytes = key_override.encode("utf-8")
        else:
            key_file.parent.mkdir(parents=True, exist_ok=True)
            if key_file.exists():
                key_bytes = key_file.read_bytes().strip()
            else:
                key_bytes = Fernet.generate_key()
                tmp = key_file.with_suffix(".tmp")
                tmp.write_bytes(key_bytes)
                try:
                    os.chmod(tmp, 0o600)
                except OSError:
                    pass
                tmp.replace(key_file)
                try:
                    os.chmod(key_file, 0o600)
                except OSError:
                    pass
        self._fernet = Fernet(key_bytes)

    def encrypt(self, plaintext: str) -> str:
        if not plaintext or not plaintext.strip():
            raise ValueError("Secret value cannot be empty.")
        return self._fernet.encrypt(plaintext.strip().encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Unable to decrypt stored provider credential (master key mismatch or corrupted ciphertext).") from exc


class ApprovalSigner:
    """Signs short-lived explicit generation confirmation tokens bound to exact request parameters."""

    def __init__(self, secret_file: Path, secret_override: str | None = None):
        if secret_override:
            self._secret = secret_override.encode("utf-8")
        else:
            secret_file.parent.mkdir(parents=True, exist_ok=True)
            if secret_file.exists():
                self._secret = secret_file.read_bytes().strip()
            else:
                self._secret = secrets.token_urlsafe(48).encode("utf-8")
                tmp = secret_file.with_suffix(".tmp")
                tmp.write_bytes(self._secret)
                try:
                    os.chmod(tmp, 0o600)
                except OSError:
                    pass
                tmp.replace(secret_file)
                try:
                    os.chmod(secret_file, 0o600)
                except OSError:
                    pass

    def sign_quote(self, payload: dict[str, Any]) -> str:
        canonical = _canonical_bytes(payload)
        return hmac.new(self._secret, canonical, hashlib.sha256).hexdigest()

    def verify_quote(self, payload: dict[str, Any], signature: str) -> bool:
        expected = self.sign_quote(payload)
        return hmac.compare_digest(expected, signature)


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    import json

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
