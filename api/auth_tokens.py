import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Optional


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    s = (data or "").strip()
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(secret: str, msg: bytes) -> bytes:
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()


@dataclass(frozen=True)
class AuthClaims:
    wallet_address: str
    iat: int
    exp: int


def issue_token(*, secret: str, wallet_address: str, ttl_seconds: int) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {"sub": wallet_address, "iat": now, "exp": now + int(ttl_seconds)}
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload_b64 = _b64url_encode(payload_bytes)
    sig = _sign(secret, payload_b64.encode("ascii"))
    sig_b64 = _b64url_encode(sig)
    return f"{payload_b64}.{sig_b64}"


def verify_token(*, secret: str, token: str) -> Optional[AuthClaims]:
    raw = (token or "").strip()
    if not raw or "." not in raw:
        return None
    payload_b64, sig_b64 = raw.split(".", 1)
    try:
        expected_sig = _sign(secret, payload_b64.encode("ascii"))
        got_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, got_sig):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        wallet_address = str(payload.get("sub") or "").strip()
        iat = int(payload.get("iat") or 0)
        exp = int(payload.get("exp") or 0)
        if not wallet_address or not iat or not exp:
            return None
        now = int(time.time())
        if now >= exp:
            return None
        return AuthClaims(wallet_address=wallet_address, iat=iat, exp=exp)
    except Exception:
        return None


def parse_bearer_token(auth_header: Optional[str]) -> Optional[str]:
    if not auth_header:
        return None
    s = str(auth_header).strip()
    if not s.lower().startswith("bearer "):
        return None
    return s.split(" ", 1)[1].strip() or None


