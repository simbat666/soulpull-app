"""
Soulpull MVP — API Views (согласно ТЗ §5, §13)

Endpoints:
- POST /api/v1/register — регистрация по telegram_id
- POST /api/v1/wallet — привязка кошелька
- POST /api/v1/intent — резерв слота 3/3 и создание Participation
- POST /api/v1/confirm — админ подтверждение платежа
- GET /api/v1/me — профиль и дерево L1
- POST /api/v1/payout — запрос выплаты 33 USDT
- POST /api/v1/payout/mark — админ отметка SENT
- GET /api/v1/jetton/wallet — jetton-wallet адрес
- GET /api/v1/health — healthcheck
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import struct
from datetime import datetime, timezone as dt_timezone
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from .models import (
    AuthorCode,
    IdempotencyKey,
    Participation,
    ParticipationStatus,
    PayoutRequest,
    PayoutStatus,
    RiskEvent,
    RiskEventKind,
    TonProofPayload,
    UserProfile,
)
from .services.toncenter import ToncenterError, get_jetton_wallet_address

logger = logging.getLogger(__name__)


# ============================================================================
# HELPERS
# ============================================================================

def _json_response(data: dict, status: int = 200) -> JsonResponse:
    """Unified JSON response."""
    return JsonResponse(data, status=status)


def _error_response(error: str, message: str = "", status: int = 400) -> JsonResponse:
    """Unified error response."""
    resp = {"ok": False, "error": error}
    if message:
        resp["message"] = message
    return JsonResponse(resp, status=status)


def _parse_json_body(request) -> tuple[Optional[dict], Optional[JsonResponse]]:
    """Parse JSON body, return (body, None) or (None, error_response)."""
    try:
        return json.loads(request.body or b"{}"), None
    except json.JSONDecodeError:
        return None, _error_response("invalid_json", "Request body must be valid JSON")


def _admin_token() -> str:
    """Get admin token from env."""
    return (os.getenv("X_ADMIN_TOKEN") or os.getenv("ADMIN_TOKEN") or "").strip()


def _require_admin(request) -> Optional[JsonResponse]:
    """Check admin token header."""
    token = _admin_token()
    got = (request.headers.get("X-Admin-Token") or "").strip()
    if not token or got != token:
        return _error_response("forbidden", "Admin token required", 403)
    return None


def _get_user_by_telegram_id(telegram_id: int) -> Optional[UserProfile]:
    """Get user by telegram_id."""
    return UserProfile.objects.filter(telegram_id=telegram_id).first()


def _get_user_by_wallet(wallet: str) -> Optional[UserProfile]:
    """Get user by wallet address."""
    return UserProfile.objects.filter(wallet=wallet).first()


# ============================================================================
# BUSINESS LOGIC
# ============================================================================

def _active_participation(user: UserProfile) -> Optional[Participation]:
    """
    Get active participation for user (NEW, PENDING, or CONFIRMED).
    """
    return (
        Participation.objects.filter(
            user=user,
            status__in=[ParticipationStatus.NEW, ParticipationStatus.PENDING, ParticipationStatus.CONFIRMED],
        )
        .order_by("-created_at")
        .first()
    )


def _referrer_used_slots(referrer: UserProfile) -> int:
    """
    Count occupied slots for referrer (NEW, PENDING, CONFIRMED participations).
    """
    return Participation.objects.filter(
            referrer=referrer,
        status__in=[ParticipationStatus.NEW, ParticipationStatus.PENDING, ParticipationStatus.CONFIRMED],
    ).count()


def _confirmed_l1_count(referrer: UserProfile) -> int:
    """
    Count CONFIRMED L1 referrals created after referrer's active participation.
    """
    active = _active_participation(referrer)
    if not active or active.status != ParticipationStatus.CONFIRMED:
        return 0
    return Participation.objects.filter(
        referrer=referrer,
        status=ParticipationStatus.CONFIRMED,
        created_at__gt=active.created_at,
    ).values("user_id").distinct().count()


def _create_intent(
    user: UserProfile,
    referrer_telegram_id: Optional[int],
    author_code: Optional[str]
) -> tuple[Participation, int]:
    """
    Create participation intent with slot reservation.
    Returns (participation, used_slots).
    Raises ValueError or RuntimeError on failure.
    """
    # Check active cycle
    if _active_participation(user):
        RiskEvent.objects.create(user=user, kind=RiskEventKind.ACTIVE_CYCLE, meta={"action": "intent"})
        raise ValueError("active_cycle")

    # Find referrer
    referrer = None
    if referrer_telegram_id is not None:
        referrer = UserProfile.objects.select_for_update().filter(telegram_id=referrer_telegram_id).first()
    if not referrer:
        raise ValueError("referrer_not_found")
    if referrer.id == user.id:
            RiskEvent.objects.create(user=user, kind=RiskEventKind.SELF_REFERRAL, meta={"referrer_tid": referrer_telegram_id})
        raise ValueError("self_referral")

        # Check referrer has CONFIRMED participation
        if not Participation.objects.filter(user=referrer, status=ParticipationStatus.CONFIRMED).exists():
            raise ValueError("referrer_not_confirmed")
        
        # Check 3/3 slots
    used_slots = _referrer_used_slots(referrer)
    if used_slots >= 3:
            RiskEvent.objects.create(user=user, kind=RiskEventKind.REF_LIMIT, meta={"referrer_tid": referrer_telegram_id, "slots": used_slots})
        raise RuntimeError("referrer_limit")
    else:
        used_slots = 0

    # Handle author code
    code = (author_code or "").strip() or None
    if code:
        ac = AuthorCode.objects.filter(code=code).select_related("owner").first()
        if ac:
            # Award points
            user.points = (user.points or 0) + 10
            user.save(update_fields=["points", "updated_at"])
            ac.owner.points = (ac.owner.points or 0) + 10
            ac.owner.save(update_fields=["points", "updated_at"])

    # Create participation
    participation = Participation.objects.create(
        user=user,
        referrer=referrer,
        author_code=code,
        status=ParticipationStatus.NEW,
    )

    return participation, used_slots + 1 if referrer else 0


# ============================================================================
# TON PROOF
# ============================================================================

def _b64decode_padded(data: str) -> bytes:
    s = (data or "").strip()
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _parse_hex_address(address: str) -> tuple[int, bytes]:
    if ":" not in address:
        raise ValueError("address must be in '<wc>:<hex>' format")
    wc_s, hex_s = address.split(":", 1)
    wc = int(wc_s)
    addr_hash = bytes.fromhex(hex_s)
    if len(addr_hash) != 32:
        raise ValueError("address hash must be 32 bytes")
    return wc, addr_hash


def _ton_proof_message(*, address: str, domain: str, timestamp: int, payload: str) -> bytes:
    wc, addr_hash = _parse_hex_address(address)
    domain_bytes = domain.encode("utf-8")
    payload_bytes = payload.encode("utf-8")
    address_part = int(wc).to_bytes(4, byteorder="big", signed=True) + addr_hash
    domain_part = struct.pack("<I", len(domain_bytes)) + domain_bytes
    ts_part = struct.pack("<Q", int(timestamp))
    return b"ton-proof-item-v2/" + address_part + domain_part + ts_part + payload_bytes


def _ton_proof_hash(message: bytes) -> bytes:
    return _sha256(b"\xff\xff" + b"ton-connect" + _sha256(message))


def _decode_pubkey(public_key: str) -> bytes:
    s = (public_key or "").strip()
    try:
        if len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s):
            return bytes.fromhex(s)
        except Exception:
        pass
    b = _b64decode_padded(s)
    if len(b) != 32:
        raise ValueError("public_key must be 32 bytes")
    return b


def _expected_domain() -> str:
    return os.getenv("APP_DOMAIN", "refnet.click")


# ============================================================================
# API ENDPOINTS
# ============================================================================

@csrf_exempt
@require_http_methods(["GET"])
def health(request):
    """Health check endpoint."""
    return _json_response({
        "status": "ok",
        "time": timezone.now().isoformat(),
        "debug": bool(settings.DEBUG),
    })


@csrf_exempt
@require_http_methods(["POST"])
def register(request):
    """
    POST /api/v1/register
    Req: { "telegram_id": int, "username": "str?" }
    Res: { "ok": true, "user": {...} }
    """
    body, err = _parse_json_body(request)
    if err:
        return err

    telegram_id = body.get("telegram_id")
    if telegram_id is None:
        return _error_response("validation_error", "telegram_id is required")
    try:
        telegram_id = int(telegram_id)
    except (TypeError, ValueError):
        return _error_response("validation_error", "telegram_id must be integer")

    username = (body.get("username") or "").strip() or None

    user, created = UserProfile.objects.update_or_create(
        telegram_id=telegram_id,
        defaults={"username": username},
    )

    return _json_response({
        "ok": True,
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "wallet": user.wallet,
        },
    }, status=201 if created else 200)


@csrf_exempt
@require_http_methods(["POST"])
def wallet(request):
    """
    POST /api/v1/wallet
    Req: { "telegram_id": int, "wallet": "tonaddr" }
    Res: { "ok": true }
    """
    body, err = _parse_json_body(request)
    if err:
        return err

    telegram_id = body.get("telegram_id")
    wallet_addr = (body.get("wallet") or "").strip()

    if telegram_id is None:
        return _error_response("validation_error", "telegram_id is required")
    if not wallet_addr:
        return _error_response("validation_error", "wallet is required")

    try:
        telegram_id = int(telegram_id)
    except (TypeError, ValueError):
        return _error_response("validation_error", "telegram_id must be integer")

    # Validate wallet format (basic check)
    if len(wallet_addr) < 32:
        return _error_response("validation_error", "Invalid wallet address")

    user = _get_user_by_telegram_id(telegram_id)
    if not user:
        return _error_response("not_found", "User not found", 404)

    # Check wallet not already used by another user
    existing = UserProfile.objects.filter(wallet=wallet_addr).exclude(id=user.id).first()
    if existing:
        RiskEvent.objects.create(
        user=user,
            kind=RiskEventKind.WALLET_REUSED,
            meta={"wallet": wallet_addr, "existing_user_id": existing.id}
        )
        return _error_response("wallet_reused", "Wallet already linked to another account", 409)

    user.wallet = wallet_addr
    user.save(update_fields=["wallet", "updated_at"])

    return _json_response({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def intent(request):
    """
    POST /api/v1/intent
    Req: { "telegram_id": int, "referrer_telegram_id": int, "author_code": "str?" }
    Res: 201 { "ok": true, "participation": {"id": int, "status": "NEW"} }
    
    Errors: 400 (active_cycle, validation), 404 (referrer_not_found), 409 (referrer_limit)
    """
    body, err = _parse_json_body(request)
    if err:
        return err

    telegram_id = body.get("telegram_id")
    referrer_telegram_id = body.get("referrer_telegram_id")
    author_code = body.get("author_code")

    # Idempotency
    idem_key = (request.headers.get("Idempotency-Key") or "").strip()
    if idem_key:
        existing = IdempotencyKey.objects.filter(key=idem_key).first()
        if existing:
            return _json_response(existing.result, status=201)

    if telegram_id is None:
        return _error_response("validation_error", "telegram_id is required")
    try:
        telegram_id = int(telegram_id)
    except (TypeError, ValueError):
        return _error_response("validation_error", "telegram_id must be integer")

    if referrer_telegram_id is not None:
        try:
            referrer_telegram_id = int(referrer_telegram_id)
        except (TypeError, ValueError):
            return _error_response("validation_error", "referrer_telegram_id must be integer")

    user = _get_user_by_telegram_id(telegram_id)
    if not user:
        return _error_response("not_found", "User not found. Call /register first.", 404)

    try:
        with transaction.atomic():
            participation, used_slots = _create_intent(user, referrer_telegram_id, author_code)
    except RuntimeError as e:
        if str(e) == "referrer_limit":
            return _error_response("referrer_limit", "Referrer has no free slots (3/3)", 409)
        raise
    except ValueError as e:
        error_map = {
            "active_cycle": ("active_cycle", "User already has active participation", 400),
            "referrer_not_found": ("referrer_not_found", "Referrer not found", 404),
            "self_referral": ("self_referral", "Cannot refer yourself", 400),
            "referrer_not_confirmed": ("referrer_not_confirmed", "Referrer must have confirmed participation", 400),
        }
        err_info = error_map.get(str(e), (str(e), str(e), 400))
        return _error_response(err_info[0], err_info[1], err_info[2])

    result = {
            "ok": True,
        "participation": {
            "id": participation.id,
            "status": participation.status,
        },
        "slots": {
            "used": used_slots,
            "limit": 3,
        },
    }

    # Save idempotency
    if idem_key:
        IdempotencyKey.objects.create(key=idem_key, result=result)

    return _json_response(result, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def confirm(request):
    """
    POST /api/v1/confirm (admin)
    Req: { "participation_id": int, "tx_hash": "str" }
    Res: { "ok": true, "status": "CONFIRMED" }
    """
    admin_err = _require_admin(request)
    if admin_err:
        return admin_err

    body, err = _parse_json_body(request)
    if err:
        return err

    participation_id = body.get("participation_id")
    tx_hash = (body.get("tx_hash") or "").strip()
    decision = (body.get("decision") or "confirm").strip().lower()

    if participation_id is None:
        return _error_response("validation_error", "participation_id is required")

    try:
        participation = Participation.objects.select_related("user").get(id=int(participation_id))
    except (Participation.DoesNotExist, ValueError):
        return _error_response("not_found", "Participation not found", 404)

    if participation.status not in [ParticipationStatus.NEW, ParticipationStatus.PENDING]:
        return _error_response("invalid_status", f"Participation already {participation.status}")

    if decision == "reject":
        participation.status = ParticipationStatus.REJECTED
        if tx_hash:
            participation.tx_hash = tx_hash
        participation.confirmed_at = timezone.now()
        participation.save(update_fields=["status", "tx_hash", "confirmed_at"])
        return _json_response({"ok": True, "status": "REJECTED"})

    # Check for duplicate tx_hash
    if tx_hash:
        dup = Participation.objects.filter(tx_hash=tx_hash).exclude(id=participation.id).exists()
        if dup:
            RiskEvent.objects.create(
                user=participation.user,
                kind=RiskEventKind.DUP_TX,
                meta={"tx_hash": tx_hash, "participation_id": participation.id}
            )
            return _error_response("dup_tx", "Transaction hash already used", 400)

    # TODO: Call verify_usdt_tx(tx_hash) here for real verification

    participation.status = ParticipationStatus.CONFIRMED
    participation.tx_hash = tx_hash or None
    participation.confirmed_at = timezone.now()
    participation.save(update_fields=["status", "tx_hash", "confirmed_at"])

    return _json_response({"ok": True, "status": "CONFIRMED"})


@csrf_exempt
@require_http_methods(["GET"])
def me(request):
    """
    GET /api/v1/me?telegram_id=...
    Res: { "user": {...}, "participation": {...|null}, "l1": [...] }
    """
    telegram_id = request.GET.get("telegram_id")
    if not telegram_id:
        return _error_response("validation_error", "telegram_id query param required")

    try:
        telegram_id = int(telegram_id)
    except ValueError:
        return _error_response("validation_error", "telegram_id must be integer")

    user = _get_user_by_telegram_id(telegram_id)
    if not user:
        return _error_response("not_found", "User not found", 404)

    active = _active_participation(user)
    confirmed_l1 = _confirmed_l1_count(user)
    used_slots = _referrer_used_slots(user)

    # L1 list
    l1_list = []
    if active:
        l1_qs = Participation.objects.filter(
            referrer=user,
            created_at__gt=active.created_at,
        ).select_related("user").order_by("-created_at")[:50]

        for p in l1_qs:
            l1_list.append({
                "telegram_id": p.user.telegram_id,
                "username": p.user.username,
                "paid": p.status == ParticipationStatus.CONFIRMED,
                "created_at": p.created_at.isoformat(),
            })

    # Check payout eligibility
    open_payout = PayoutRequest.objects.filter(
        user=user,
        status=PayoutStatus.REQUESTED
    ).exists()
    eligible_payout = (
        active is not None and
        active.status == ParticipationStatus.CONFIRMED and
        confirmed_l1 >= 3 and
        not open_payout
    )

    return _json_response({
                "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "wallet": user.wallet,
            "points": user.points,
        },
        "participation": {
            "id": active.id,
            "status": active.status,
            "created_at": active.created_at.isoformat(),
            "confirmed_at": active.confirmed_at.isoformat() if active.confirmed_at else None,
        } if active else None,
        "l1": l1_list,
        "slots": {
            "used": used_slots,
            "limit": 3,
        },
        "confirmed_l1": confirmed_l1,
        "eligible_payout": eligible_payout,
        "has_open_payout": open_payout,
    })


@csrf_exempt
@require_http_methods(["POST"])
def payout(request):
    """
    POST /api/v1/payout
    Req: { "telegram_id": int }
    Res: { "ok": true, "request": {"id": int, "status": "REQUESTED"} }
    """
    body, err = _parse_json_body(request)
    if err:
        return err

    telegram_id = body.get("telegram_id")
    if telegram_id is None:
        return _error_response("validation_error", "telegram_id is required")

    try:
        telegram_id = int(telegram_id)
    except (TypeError, ValueError):
        return _error_response("validation_error", "telegram_id must be integer")

    user = _get_user_by_telegram_id(telegram_id)
    if not user:
        return _error_response("not_found", "User not found", 404)

    active = _active_participation(user)
    if not active or active.status != ParticipationStatus.CONFIRMED:
        return _error_response("not_eligible", "No confirmed participation", 400)

    confirmed_l1 = _confirmed_l1_count(user)
    if confirmed_l1 < 3:
        return _error_response("not_eligible", f"Need 3 confirmed L1 referrals, have {confirmed_l1}", 400)

    # Check existing request
    existing = PayoutRequest.objects.filter(user=user, status=PayoutStatus.REQUESTED).exists()
    if existing:
        return _error_response("already_requested", "Payout already requested", 409)

    payout_req = PayoutRequest.objects.create(user=user, status=PayoutStatus.REQUESTED)

    return _json_response({
        "ok": True,
        "request": {
            "id": payout_req.id,
            "status": payout_req.status,
        },
    })


@csrf_exempt
@require_http_methods(["POST"])
def payout_mark(request):
    """
    POST /api/v1/payout/mark (admin)
    Req: { "user_id": int, "tx_hash": "str" }
    Res: { "ok": true, "status": "SENT" }
    """
    admin_err = _require_admin(request)
    if admin_err:
        return admin_err

    body, err = _parse_json_body(request)
    if err:
        return err

    user_id = body.get("user_id")
    payout_id = body.get("payout_request_id")
    tx_hash = (body.get("tx_hash") or "").strip()

    if not tx_hash:
        return _error_response("validation_error", "tx_hash is required")

    if payout_id:
        try:
            payout_req = PayoutRequest.objects.get(id=int(payout_id))
        except (PayoutRequest.DoesNotExist, ValueError):
            return _error_response("not_found", "Payout request not found", 404)
    elif user_id:
        try:
            user = UserProfile.objects.get(id=int(user_id))
        except (UserProfile.DoesNotExist, ValueError):
            return _error_response("not_found", "User not found", 404)
        payout_req = PayoutRequest.objects.filter(user=user, status=PayoutStatus.REQUESTED).first()
        if not payout_req:
            return _error_response("not_found", "No open payout request", 404)
    else:
        return _error_response("validation_error", "user_id or payout_request_id required")

    if payout_req.status != PayoutStatus.REQUESTED:
        return _error_response("invalid_status", f"Payout already {payout_req.status}")

    payout_req.status = PayoutStatus.SENT
    payout_req.tx_hash = tx_hash
    payout_req.save(update_fields=["status", "tx_hash", "updated_at"])

    return _json_response({"ok": True, "status": "SENT"})


@csrf_exempt
@require_http_methods(["GET"])
def jetton_wallet(request):
    """
    GET /api/v1/jetton/wallet?owner=<addr>&master=<USDT_MASTER>
    Res: { "wallet_address": "str" }
    """
    owner = (request.GET.get("owner") or "").strip()
    master = (request.GET.get("master") or os.getenv("USDT_JETTON_MASTER") or "").strip()

    if not owner:
        return _error_response("validation_error", "owner query param required")
    if not master:
        return _error_response("server_error", "USDT_JETTON_MASTER not configured", 500)

    try:
        jw = get_jetton_wallet_address(owner_address=owner, jetton_master_address=master)
        return _json_response({"wallet_address": jw})
    except ToncenterError as e:
        return _error_response("toncenter_error", str(e), 502)
    except Exception as e:
        logger.exception("jetton_wallet failed")
        return _error_response("server_error", str(e), 500)


# ============================================================================
# TON PROOF ENDPOINTS
# ============================================================================

@csrf_exempt
@require_http_methods(["GET"])
def tonproof_payload(request):
    """Issue TON Proof nonce (TTL 5 min)."""
    payload = secrets.token_urlsafe(32)
    expires_at = timezone.now() + timezone.timedelta(minutes=5)
    TonProofPayload.objects.create(payload=payload, expires_at=expires_at)
    return _json_response({"payload": payload})


@csrf_exempt
@require_http_methods(["POST"])
def tonproof_verify(request):
    """Verify TON Proof and link wallet to user."""
    body, err = _parse_json_body(request)
    if err:
        return err

    wallet_address = (body.get("wallet_address") or "").strip()
    public_key_raw = (body.get("public_key") or "").strip()
    telegram_id = body.get("telegram_id")
    proof = body.get("proof") or {}

    if not wallet_address:
        return _error_response("validation_error", "wallet_address is required")
    if not public_key_raw:
        return _error_response("validation_error", "public_key is required")
    if not isinstance(proof, dict):
        return _error_response("validation_error", "proof must be an object")

    try:
        timestamp = int(proof.get("timestamp"))
        domain_obj = proof.get("domain") or {}
        domain_value = str(domain_obj.get("value") or "")
        payload = str(proof.get("payload") or "")
        signature_b64 = str(proof.get("signature") or "")
    except (TypeError, ValueError):
        return _error_response("validation_error", "Invalid proof fields")

    if not payload:
        return _error_response("validation_error", "proof.payload is required")
    if not signature_b64:
        return _error_response("validation_error", "proof.signature is required")
    if domain_value != _expected_domain():
        return _error_response("domain_mismatch", f"Expected {_expected_domain()}, got {domain_value}")

    # Validate payload
    rec = TonProofPayload.objects.filter(
        payload=payload,
        used_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if not rec:
        return _error_response("invalid_payload", "Invalid or expired payload")

    # Verify signature
    try:
        pubkey = _decode_pubkey(public_key_raw)
        signature = _b64decode_padded(signature_b64)
        if len(signature) != 64:
            return _error_response("validation_error", "Signature must be 64 bytes")
        message = _ton_proof_message(
            address=wallet_address,
            domain=domain_value,
            timestamp=timestamp,
            payload=payload,
        )
        to_sign = _ton_proof_hash(message)
        VerifyKey(pubkey).verify(to_sign, signature)
    except BadSignatureError:
        return _error_response("bad_signature", "Signature verification failed")
    except Exception as e:
        return _error_response("verification_failed", str(e))

    # Mark payload used
    updated = TonProofPayload.objects.filter(id=rec.id, used_at__isnull=True).update(used_at=timezone.now())
    if updated != 1:
        return _error_response("payload_used", "Payload already used")

    # Link wallet to user if telegram_id provided
    if telegram_id:
        try:
            telegram_id = int(telegram_id)
            user = _get_user_by_telegram_id(telegram_id)
            if user:
                # Check wallet not used by another
                existing = UserProfile.objects.filter(wallet=wallet_address).exclude(id=user.id).first()
                if existing:
                    RiskEvent.objects.create(user=user, kind=RiskEventKind.WALLET_REUSED, meta={"wallet": wallet_address})
                    return _error_response("wallet_reused", "Wallet linked to another user", 409)
                user.wallet = wallet_address
                user.save(update_fields=["wallet", "updated_at"])
        except (TypeError, ValueError):
            pass

    return _json_response({"ok": True, "wallet_address": wallet_address})


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@csrf_exempt
@require_http_methods(["GET"])
def admin_participations_pending(request):
    """List pending participations for admin."""
    admin_err = _require_admin(request)
    if admin_err:
        return admin_err

    qs = Participation.objects.filter(
        status__in=[ParticipationStatus.NEW, ParticipationStatus.PENDING]
    ).select_related("user", "referrer").order_by("created_at")[:200]

    return _json_response({
            "items": [
                {
                    "id": p.id,
                "status": p.status,
                    "created_at": p.created_at.isoformat(),
                    "author_code": p.author_code,
                    "user": {
                    "id": p.user.id,
                        "telegram_id": p.user.telegram_id,
                    "username": p.user.username,
                    "wallet": p.user.wallet,
                    },
                    "referrer": {
                    "id": p.referrer.id if p.referrer else None,
                        "telegram_id": p.referrer.telegram_id if p.referrer else None,
                    "username": p.referrer.username if p.referrer else None,
                } if p.referrer else None,
                }
                for p in qs
            ]
    })


@csrf_exempt
@require_http_methods(["GET"])
def admin_payouts_open(request):
    """List open payout requests for admin."""
    admin_err = _require_admin(request)
    if admin_err:
        return admin_err

    qs = PayoutRequest.objects.filter(
        status=PayoutStatus.REQUESTED
    ).select_related("user").order_by("created_at")[:200]

    return _json_response({
            "items": [
                {
                    "id": p.id,
                    "status": p.status,
                "created_at": p.created_at.isoformat(),
                    "user": {
                    "id": p.user.id,
                        "telegram_id": p.user.telegram_id,
                    "username": p.user.username,
                    "wallet": p.user.wallet,
                    },
                }
                for p in qs
            ]
    })
