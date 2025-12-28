import base64
import hashlib
import json
import secrets
import struct

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from .auth_tokens import issue_token, parse_bearer_token, verify_token
from .models import TonProofPayload, UserProfile


def _b64decode_padded(data: str) -> bytes:
    s = (data or "").strip()
    pad = "=" * ((4 - len(s) % 4) % 4)
    # urlsafe covers both base64 and base64url
    return base64.urlsafe_b64decode(s + pad)


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _parse_hex_address(address: str) -> tuple[int, bytes]:
    """
    Parse raw TON address in format "<workchain>:<64-hex>" (TON Connect Account.address).
    """
    if ":" not in address:
        raise ValueError("address must be in '<wc>:<hex>' format")
    wc_s, hex_s = address.split(":", 1)
    wc = int(wc_s)
    addr_hash = bytes.fromhex(hex_s)
    if len(addr_hash) != 32:
        raise ValueError("address hash must be 32 bytes")
    return wc, addr_hash


def _ton_proof_message(*, address: str, domain: str, timestamp: int, payload: str) -> bytes:
    """
    Per spec:
    message = "ton-proof-item-v2/" ++ Address ++ AppDomain ++ Timestamp ++ Payload
    """
    wc, addr_hash = _parse_hex_address(address)
    domain_bytes = domain.encode("utf-8")
    payload_bytes = payload.encode("utf-8")

    address_part = int(wc).to_bytes(4, byteorder="big", signed=True) + addr_hash
    domain_part = struct.pack("<I", len(domain_bytes)) + domain_bytes
    ts_part = struct.pack("<Q", int(timestamp))

    return b"ton-proof-item-v2/" + address_part + domain_part + ts_part + payload_bytes


def _ton_proof_hash(message: bytes) -> bytes:
    # signature over sha256(0xffff ++ "ton-connect" ++ sha256(message))
    return _sha256(b"\xff\xff" + b"ton-connect" + _sha256(message))


def _decode_pubkey(public_key: str) -> bytes:
    s = (public_key or "").strip()
    # Hex (most common)
    try:
        if len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s):
            b = bytes.fromhex(s)
            if len(b) == 32:
                return b
    except Exception:
        pass
    # Base64 / base64url
    b = _b64decode_padded(s)
    if len(b) != 32:
        raise ValueError("public_key must be 32 bytes")
    return b


def _expected_domain() -> str:
    # Hard requirement in task
    return "refnet.click"


def _auth_secret() -> str:
    return str(getattr(settings, "SECRET_KEY", ""))


def _auth_ttl_seconds() -> int:
    return int(getattr(settings, "AUTH_TOKEN_TTL_SECONDS", 24 * 60 * 60))


@csrf_exempt
@require_http_methods(["GET"])
def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "host": request.get_host(),
            "debug": bool(settings.DEBUG),
            "time": timezone.now().isoformat(),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def register_wallet(request):
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json"}, status=400)

    wallet_address = (payload.get("wallet_address") or "").strip()
    if not wallet_address:
        return JsonResponse({"error": "wallet_address is required"}, status=400)

    obj, created = UserProfile.objects.get_or_create(wallet_address=wallet_address)
    if not created:
        # Touch updated_at
        obj.save(update_fields=["updated_at"])

    return JsonResponse(
        {"success": True, "created": created, "wallet_address": obj.wallet_address},
        status=201 if created else 200,
    )


@csrf_exempt
@require_http_methods(["GET"])
def tonproof_payload(request):
    """
    Issues a random payload (nonce) for TON Proof signature. TTL: 5 minutes.
    Stored in DB for reliability.
    """
    payload = secrets.token_urlsafe(32)  # safe < 255
    expires_at = timezone.now() + timezone.timedelta(minutes=5)
    TonProofPayload.objects.create(payload=payload, expires_at=expires_at)
    return JsonResponse({"payload": payload})


@csrf_exempt
@require_http_methods(["POST"])
def tonproof_verify(request):
    """
    Verifies TON Proof and returns Bearer token.
    """
    try:
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid json"}, status=400)

        wallet_address = (body.get("wallet_address") or "").strip()
        public_key_raw = (body.get("public_key") or "").strip()
        proof = body.get("proof") or {}

        if not wallet_address:
            return JsonResponse({"error": "wallet_address is required"}, status=400)
        if not public_key_raw:
            return JsonResponse({"error": "public_key is required"}, status=400)
        if not isinstance(proof, dict):
            return JsonResponse({"error": "proof must be an object"}, status=400)

        try:
            timestamp = int(proof.get("timestamp"))
            domain_obj = proof.get("domain") or {}
            domain_value = str(domain_obj.get("value") or "")
            domain_len = int(domain_obj.get("lengthBytes"))
            payload = str(proof.get("payload") or "")
            signature_b64 = str(proof.get("signature") or "")
        except (TypeError, ValueError):
            return JsonResponse({"error": "invalid proof fields"}, status=400)

        if not payload:
            return JsonResponse({"error": "proof.payload is required"}, status=400)
        if not signature_b64:
            return JsonResponse({"error": "proof.signature is required"}, status=400)
        if domain_value != _expected_domain():
            return JsonResponse(
                {"error": "domain mismatch", "expected": _expected_domain(), "got": domain_value},
                status=400,
            )
        if domain_len != len(domain_value.encode("utf-8")):
            return JsonResponse({"error": "domain length mismatch"}, status=400)

        # Validate payload (DB, TTL, single-use) with minimal locking.
        now_dt = timezone.now()
        rec = (
            TonProofPayload.objects.filter(
                payload=payload,
                used_at__isnull=True,
                expires_at__gt=now_dt,
            )
            .only("id")
            .first()
        )
        if not rec:
            # Could be unknown, expired, or already used. Keep message simple.
            return JsonResponse({"error": "invalid or expired payload"}, status=400)

        # Verify signature
        try:
            pubkey = _decode_pubkey(public_key_raw)
            signature = _b64decode_padded(signature_b64)
            if len(signature) != 64:
                return JsonResponse({"error": "signature must be 64 bytes"}, status=400)
            message = _ton_proof_message(
                address=wallet_address,
                domain=domain_value,
                timestamp=timestamp,
                payload=payload,
            )
            to_sign = _ton_proof_hash(message)
            VerifyKey(pubkey).verify(to_sign, signature)
        except BadSignatureError:
            return JsonResponse({"error": "bad signature"}, status=400)
        except Exception:
            return JsonResponse({"error": "verification failed"}, status=400)

        # Mark payload used (single-use). If concurrent request already used it, this becomes a clean 400.
        updated = TonProofPayload.objects.filter(id=rec.id, used_at__isnull=True).update(used_at=now_dt)
        if updated != 1:
            return JsonResponse({"error": "payload already used"}, status=400)

        user, _created = UserProfile.objects.get_or_create(wallet_address=wallet_address)
        user.save(update_fields=["updated_at"])

        token = issue_token(secret=_auth_secret(), wallet_address=wallet_address, ttl_seconds=_auth_ttl_seconds())
        return JsonResponse({"token": token})
    except Exception:
        # Never return HTML 500 to frontend; keep it JSON so UI can surface the failure.
        return JsonResponse({"error": "server_error"}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def me(request):
    token = parse_bearer_token(request.headers.get("Authorization"))
    claims = verify_token(secret=_auth_secret(), token=token or "")
    if not claims:
        return JsonResponse({"error": "unauthorized"}, status=401)

    obj = UserProfile.objects.filter(wallet_address=claims.wallet_address).first()
    if not obj:
        return JsonResponse({"error": "user not found"}, status=404)

    return JsonResponse(
        {
            "wallet_address": obj.wallet_address,
            "created_at": obj.created_at.isoformat(),
            "updated_at": obj.updated_at.isoformat(),
        }
    )


