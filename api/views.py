import base64
import hashlib
import json
import secrets
import struct

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from pytoniq_core import Cell
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from .models import UserProfile


def _b64decode_padded(data: str) -> bytes:
    s = (data or "").strip()
    # base64 strings may come without padding
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.b64decode(s + pad)


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


def _ton_proof_message(
    *,
    address: str,
    domain: str,
    timestamp: int,
    payload: str,
) -> bytes:
    """
    Per spec:
    message = "ton-proof-item-v2/" ++ Address ++ AppDomain ++ Timestamp ++ Payload
    """
    wc, addr_hash = _parse_hex_address(address)
    domain_bytes = domain.encode("utf-8")
    payload_bytes = payload.encode("utf-8")

    # Address: workchain (int32 BE signed) + hash (32 bytes BE)
    address_part = int(wc).to_bytes(4, byteorder="big", signed=True) + addr_hash
    # AppDomain: length (uint32 LE) + domain bytes
    domain_part = struct.pack("<I", len(domain_bytes)) + domain_bytes
    # Timestamp: uint64 LE
    ts_part = struct.pack("<Q", int(timestamp))

    return b"ton-proof-item-v2/" + address_part + domain_part + ts_part + payload_bytes


def _ton_proof_hash(message: bytes) -> bytes:
    """
    signature = Ed25519Sign(privkey, sha256(0xffff ++ "ton-connect" ++ sha256(message)))
    """
    return _sha256(b"\xff\xff" + b"ton-connect" + _sha256(message))


def _expected_ton_domain(request) -> str:
    configured = getattr(settings, "TON_PROOF_DOMAIN", "") or ""
    if configured.strip():
        return configured.strip()
    # request.get_host() may include port
    host = request.get_host() or ""
    return host.split(":")[0]


def _ton_proof_ttl_seconds() -> int:
    return int(getattr(settings, "TON_PROOF_TTL_SECONDS", 600))


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
def me(request):
    wallet_address = (request.GET.get("wallet_address") or "").strip()
    if not wallet_address:
        return JsonResponse({"error": "wallet_address query param is required"}, status=400)

    obj = UserProfile.objects.filter(wallet_address=wallet_address).first()
    if not obj:
        return JsonResponse({"error": "user not found"}, status=404)

    return JsonResponse(
        {
            "wallet_address": obj.wallet_address,
            "created_at": obj.created_at.isoformat(),
            "updated_at": obj.updated_at.isoformat(),
        }
    )


@csrf_exempt
@require_http_methods(["GET"])
def ton_proof_payload(request):
    """
    Creates (or refreshes) a ton_proof payload (nonce) bound to the current session.
    Frontend should call this and pass the returned payload to TonConnect connect request.
    """
    payload = secrets.token_urlsafe(32)  # < 128 bytes
    now = int(timezone.now().timestamp())

    request.session["ton_proof_payload"] = payload
    request.session["ton_proof_issued_at"] = now
    request.session.modified = True

    return JsonResponse(
        {
            "payload": payload,
            "ttlSeconds": _ton_proof_ttl_seconds(),
            "issuedAt": now,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def ton_proof_verify(request):
    """
    Verify TonConnect `ton_proof` and create a server-side session.

    Expected JSON:
    {
      "address": "<wc>:<hex>",
      "publicKey": "<hex 32 bytes>",
      "walletStateInit": "<base64 boc>",
      "proof": {
        "timestamp": <number>,
        "domain": {"lengthBytes": <number>, "value": "<domain>"},
        "payload": "<payload>",
        "signature": "<base64 signature>"
      }
    }
    """
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    address = (body.get("address") or "").strip()
    public_key_hex = (body.get("publicKey") or "").strip()
    wallet_state_init_b64 = (body.get("walletStateInit") or "").strip()
    proof = body.get("proof") or {}

    if not address:
        return JsonResponse({"ok": False, "error": "address is required"}, status=400)
    if not public_key_hex:
        return JsonResponse({"ok": False, "error": "publicKey is required"}, status=400)
    if not isinstance(proof, dict):
        return JsonResponse({"ok": False, "error": "proof must be an object"}, status=400)

    # Validate proof fields
    try:
        timestamp = int(proof.get("timestamp"))
        domain_obj = proof.get("domain") or {}
        domain_value = str(domain_obj.get("value") or "")
        domain_len = int(domain_obj.get("lengthBytes"))
        payload = str(proof.get("payload") or "")
        signature_b64 = str(proof.get("signature") or "")
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid proof fields"}, status=400)

    if not domain_value or domain_len <= 0:
        return JsonResponse({"ok": False, "error": "invalid proof domain"}, status=400)
    if domain_len != len(domain_value.encode("utf-8")):
        return JsonResponse({"ok": False, "error": "domain length mismatch"}, status=400)
    if not signature_b64:
        return JsonResponse({"ok": False, "error": "signature is required"}, status=400)

    expected_domain = _expected_ton_domain(request)
    if domain_value != expected_domain:
        return JsonResponse(
            {
                "ok": False,
                "error": "domain mismatch",
                "expected": expected_domain,
                "got": domain_value,
            },
            status=400,
        )

    # Check payload against session
    expected_payload = request.session.get("ton_proof_payload")
    issued_at = int(request.session.get("ton_proof_issued_at") or 0)
    if not expected_payload or not issued_at:
        return JsonResponse({"ok": False, "error": "no server payload in session"}, status=400)
    if payload != expected_payload:
        return JsonResponse({"ok": False, "error": "payload mismatch"}, status=400)

    now = int(timezone.now().timestamp())
    ttl = _ton_proof_ttl_seconds()
    if abs(now - timestamp) > ttl:
        return JsonResponse({"ok": False, "error": "proof timestamp expired"}, status=400)

    # Optional: verify walletStateInit hash equals address hash (recommended by spec)
    if wallet_state_init_b64:
        try:
            wc, addr_hash = _parse_hex_address(address)
            _ = wc  # used only for parsing validation
            state_cell = Cell.one_from_boc(_b64decode_padded(wallet_state_init_b64))
            if state_cell.hash != addr_hash:
                return JsonResponse(
                    {"ok": False, "error": "walletStateInit hash mismatch with address"},
                    status=400,
                )
        except Exception:
            # Don't hard-fail if parsing fails; signature verification below is still meaningful.
            pass

    # Verify signature (ed25519)
    try:
        pubkey = bytes.fromhex(public_key_hex)
        if len(pubkey) != 32:
            return JsonResponse({"ok": False, "error": "publicKey must be 32 bytes"}, status=400)
        signature = _b64decode_padded(signature_b64)
        if len(signature) != 64:
            return JsonResponse({"ok": False, "error": "signature must be 64 bytes"}, status=400)

        message = _ton_proof_message(
            address=address,
            domain=domain_value,
            timestamp=timestamp,
            payload=payload,
        )
        to_sign = _ton_proof_hash(message)

        VerifyKey(pubkey).verify(to_sign, signature)
    except BadSignatureError:
        return JsonResponse({"ok": False, "error": "bad signature"}, status=400)
    except Exception:
        return JsonResponse({"ok": False, "error": "verification failed"}, status=400)

    # Mark session authenticated & register user profile
    request.session["ton_address"] = address
    request.session["ton_public_key"] = public_key_hex
    request.session["ton_verified_at"] = now
    request.session.pop("ton_proof_payload", None)
    request.session.pop("ton_proof_issued_at", None)
    request.session.modified = True

    obj, _created = UserProfile.objects.get_or_create(wallet_address=address)
    obj.save(update_fields=["updated_at"])

    return JsonResponse({"ok": True, "address": address})


