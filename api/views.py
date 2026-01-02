import base64
import hashlib
import json
import os
import secrets
import struct
import logging
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

from .auth_tokens import issue_token, parse_bearer_token, verify_token
from .models import (
    AuthorCode,
    EventLog,
    EventType,
    Participation,
    ParticipationState,
    ParticipationStatus,
    PayoutRequest,
    PayoutStatus,
    TonProofPayload,
    UserProfile,
)
from .services.auth import require_user_or_401
from .services.payments import confirm_payment, create_payment_intent
from .services.toncenter import ToncenterError, get_jetton_wallet_address
from .services.telegram import verify_init_data

logger = logging.getLogger(__name__)


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


def _admin_secret() -> str:
    """
    Backward-compatible: accept either ADMIN_TOKEN or X_ADMIN_TOKEN env var.
    """
    return (os.getenv("X_ADMIN_TOKEN") or os.getenv("ADMIN_TOKEN") or "").strip()


def _cycle_start_dt(user: UserProfile) -> datetime:
    """
    Current cycle start = moment of last SENT payout (we map it to PayoutStatus.PAID).
    """
    last_paid = (
        PayoutRequest.objects.filter(user=user, status=PayoutStatus.PAID)
        .order_by("-updated_at")
        .only("updated_at")
        .first()
    )
    if last_paid and last_paid.updated_at:
        return last_paid.updated_at
    return datetime(1970, 1, 1, tzinfo=dt_timezone.utc)


def _active_participation(user: UserProfile) -> Optional[Participation]:
    start = _cycle_start_dt(user)
    return (
        Participation.objects.filter(
            user=user,
            created_at__gt=start,
            status__in=[ParticipationState.NEW, ParticipationState.PENDING, ParticipationState.CONFIRMED],
        )
        .order_by("-created_at")
        .first()
    )


def _referrer_used_slots(referrer: UserProfile) -> int:
    start = _cycle_start_dt(referrer)
    return (
        Participation.objects.filter(
            referrer=referrer,
            created_at__gt=start,
            status__in=[ParticipationState.NEW, ParticipationState.PENDING, ParticipationState.CONFIRMED],
        )
        .count()
    )


def _has_any_confirmed_participation() -> bool:
    """
    "First user" seed rule:
    - If there are no CONFIRMED participations in the whole system yet, allow creating an intent without referrer.
    - Once at least one CONFIRMED exists, referrer becomes mandatory for everyone.
    """
    return Participation.objects.filter(status=ParticipationState.CONFIRMED).exists()


def _referrer_cycle_l1_qs(referrer: UserProfile):
    """
    L1 participations that count towards 3/3 payout condition:
    - created after referrer's active participation started
    - status CONFIRMED
    """
    active = _active_participation(referrer)
    if not active or active.status != ParticipationState.CONFIRMED:
        return Participation.objects.none()
    return Participation.objects.filter(
        referrer=referrer,
        status=ParticipationState.CONFIRMED,
        created_at__gt=active.created_at,
    )


def _confirmed_l1_count(referrer: UserProfile) -> int:
    return _referrer_cycle_l1_qs(referrer).values("user_id").distinct().count()


def _create_intent(*, user: UserProfile, referrer_telegram_id: Optional[int], author_code: str):
    """
    Reserve a referrer slot (3/3) and create Participation(NEW) for user.
    Returns (participation, payment_intent, used_slots).
    """
    # TEST_MODE: skip strict checks for quick payment testing
    test_mode = os.getenv("TEST_MODE", "").strip().lower() in ("1", "true", "yes")
    
    if not test_mode and not user.telegram_id:
        raise ValueError("telegram_required")

    # Author code is optional; if provided, it can't conflict with already set one.
    author_code = (author_code or "").strip()
    if user.author_code and author_code and user.author_code != author_code:
        raise ValueError("author_code_already_set")

    # Active cycle check: user can't start a new cycle until payout is SENT/PAID.
    if not test_mode and _active_participation(user):
        raise ValueError("active_cycle")

    # If author code provided and not yet stored, persist and award points (optional).
    if author_code and not user.author_code:
        user.author_code = author_code
        user.author_code_applied_at = timezone.now()
        user.save(update_fields=["author_code", "author_code_applied_at", "updated_at"])
        ac = AuthorCode.objects.filter(code=author_code, active=True).select_related("owner").first()
        if ac:
            user.points = int(user.points or 0) + 10
            user.save(update_fields=["points", "updated_at"])
            ac.owner.points = int(ac.owner.points or 0) + 10
            ac.owner.save(update_fields=["points", "updated_at"])
        EventLog.objects.create(
            user=user,
            event_type=EventType.APPLY_CODE,
            payload={"code": author_code, "known": bool(ac), "author_wallet": ac.owner.wallet_address if ac else None},
        )

    # Create payment intent (stub today, TON/USDT later)
    pay_intent = create_payment_intent(user)

    # Slot reservation must be atomic with referrer lock
    referrer = None
    if referrer_telegram_id is None:
        # Seed rule: only allow missing referrer if the system has no CONFIRMED participations yet.
        if not test_mode and _has_any_confirmed_participation():
            raise ValueError("referrer_required")
        # Seed participation: ensure inviter fields are cleared.
        user.inviter_telegram_id = None
        user.inviter_wallet_address = None
        user.inviter_set_at = None
    else:
        referrer = (
            UserProfile.objects.select_for_update()
            .filter(telegram_id=referrer_telegram_id)
            .first()
        )
        if not referrer:
            raise ValueError("referrer_not_found")
        if referrer.id == user.id:
            raise ValueError("self_referral")
        # Referrer must have paid entry (at least one CONFIRMED participation).
        if not test_mode and not Participation.objects.filter(user=referrer, status=ParticipationState.CONFIRMED).exists():
            raise ValueError("referrer_not_confirmed")

        used_slots = _referrer_used_slots(referrer)
        if not test_mode and used_slots >= 3:
            raise RuntimeError("referrer_limit")
    used_slots = _referrer_used_slots(referrer) + 1 if referrer else 0

    part = Participation.objects.create(
        user=user,
        referrer=referrer,
        author_code=user.author_code,
        amount_usd_cents=pay_intent.amount_usd_cents,
        status=ParticipationState.NEW,
    )

    # Store candidate referrer on profile for UI (optional)
    if referrer:
        user.inviter_telegram_id = referrer.telegram_id
        user.inviter_wallet_address = None
        user.inviter_set_at = timezone.now()
    user.participation_status = ParticipationStatus.PENDING
    user.save(update_fields=["inviter_telegram_id", "inviter_wallet_address", "inviter_set_at", "participation_status", "updated_at"])

    return part, pay_intent, used_slots


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

    try:
        obj, created = UserProfile.objects.get_or_create(wallet_address=wallet_address)
        if not created:
            # Touch updated_at
            obj.save(update_fields=["updated_at"])

        return JsonResponse(
            {"success": True, "created": created, "wallet_address": obj.wallet_address},
            status=201 if created else 200,
        )
    except Exception as e:
        # Return JSON error instead of HTML 500, so we can debug on frontend
        logger.exception("register_wallet failed")
        return JsonResponse(
            {"error": "server_error", "error_type": e.__class__.__name__, "message": str(e)},
            status=500
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
        EventLog.objects.create(
            user=user,
            event_type=EventType.LOGIN,
            payload={"wallet_address": wallet_address},
        )
        return JsonResponse({"token": token})
    except Exception as e:
        # Never return HTML 500 to frontend; keep it JSON so UI can surface the failure.
        logger.exception("tonproof_verify failed")
        return JsonResponse({"error": "server_error", "error_type": e.__class__.__name__}, status=500)


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

    active = _active_participation(obj)
    cycle_start = _cycle_start_dt(obj)
    payout_window_start = active.created_at if active else None

    l1_qs = (
        Participation.objects.filter(referrer=obj, created_at__gt=cycle_start)
        .select_related("user")
        .order_by("-created_at")[:200]
    )
    l1_items = []
    for p in l1_qs:
        paid = p.status == ParticipationState.CONFIRMED and (payout_window_start is not None and p.created_at > payout_window_start)
        l1_items.append(
            {
                "participation_id": p.id,
                "status": p.status,
                "paid": bool(paid),
                "created_at": p.created_at.isoformat(),
                "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None,
                "user": {
                    "wallet_address": p.user.wallet_address,
                    "telegram_id": p.user.telegram_id,
                    "telegram_username": p.user.telegram_username,
                },
            }
        )

    confirmed_l1 = _confirmed_l1_count(obj)
    used_slots = _referrer_used_slots(obj)
    open_payout = (
        PayoutRequest.objects.filter(user=obj, status__in=[PayoutStatus.REQUESTED, PayoutStatus.APPROVED])
        .order_by("-created_at")
        .first()
    )
    eligible_payout = bool(active and active.status == ParticipationState.CONFIRMED and confirmed_l1 >= 3 and not open_payout)

    return JsonResponse(
        {
            "wallet_address": obj.wallet_address,
            "telegram": (
                {
                    "id": obj.telegram_id,
                    "username": obj.telegram_username,
                    "first_name": obj.telegram_first_name,
                }
                if obj.telegram_id
                else None
            ),
            "inviter": {
                "wallet_address": obj.inviter_wallet_address,
                "telegram_id": obj.inviter_telegram_id,
                "set_at": obj.inviter_set_at.isoformat() if obj.inviter_set_at else None,
            },
            "author_code": obj.author_code,
            "participation_status": obj.participation_status,
            "cycle": {
                "cycle_start": cycle_start.isoformat() if cycle_start else None,
                "active_participation": (
                    {
                        "id": active.id,
                        "status": active.status,
                        "created_at": active.created_at.isoformat(),
                        "confirmed_at": active.confirmed_at.isoformat() if active.confirmed_at else None,
                    }
                    if active
                    else None
                ),
                "payout_window_start": payout_window_start.isoformat() if payout_window_start else None,
            },
            "referrals": {
                "slots": {"used": used_slots, "limit": 3},
                "confirmed_l1": confirmed_l1,
                "eligible_payout": eligible_payout,
                "has_open_payout": bool(open_payout),
                "l1": l1_items,
            },
            "stats": {
                "invited_count": obj.invited_count,
                "paid_count": obj.paid_count,
                "payouts_count": obj.payouts_count,
                "points": obj.points,
            },
            "created_at": obj.created_at.isoformat(),
            "updated_at": obj.updated_at.isoformat(),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def telegram_verify(request):
    user_or_resp = require_user_or_401(request)
    if isinstance(user_or_resp, JsonResponse):
        return user_or_resp
    user = user_or_resp

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json"}, status=400)

    init_data = (body.get("initData") or "").strip()
    if not init_data:
        return JsonResponse({"error": "initData is required"}, status=400)

    bot_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not bot_token:
        return JsonResponse({"error": "server missing TELEGRAM_BOT_TOKEN"}, status=500)

    try:
        tg_user = verify_init_data(init_data, bot_token)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    user.telegram_id = tg_user.telegram_id
    user.telegram_username = tg_user.username
    user.telegram_first_name = tg_user.first_name
    user.save(update_fields=["telegram_id", "telegram_username", "telegram_first_name", "updated_at"])

    EventLog.objects.create(
        user=user,
        event_type=EventType.TELEGRAM_VERIFY,
        payload={"telegram_id": tg_user.telegram_id, "username": tg_user.username},
    )
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def inviter_apply(request):
    user_or_resp = require_user_or_401(request)
    if isinstance(user_or_resp, JsonResponse):
        return user_or_resp
    user = user_or_resp

    if user.participation_status not in {ParticipationStatus.NEW, ParticipationStatus.PENDING}:
        return JsonResponse({"error": "inviter can not be changed after activation"}, status=400)

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json"}, status=400)

    inviter = (body.get("inviter") or "").strip()
    if not inviter:
        return JsonResponse({"error": "inviter is required"}, status=400)

    # Referrer is REQUIRED and must be Telegram ID (per business rules).
    if not inviter.isdigit():
        return JsonResponse({"error": "referrer_telegram_id must be digits"}, status=400)
    inviter_wallet = None
    inviter_tg = int(inviter)
    if user.telegram_id and inviter_tg == int(user.telegram_id):
        return JsonResponse({"error": "self_referral"}, status=400)

    user.inviter_wallet_address = inviter_wallet
    user.inviter_telegram_id = inviter_tg
    user.inviter_set_at = timezone.now()
    user.save(update_fields=["inviter_wallet_address", "inviter_telegram_id", "inviter_set_at", "updated_at"])

    EventLog.objects.create(
        user=user,
        event_type=EventType.INVITER_SET,
        payload={"inviter": inviter},
    )
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def author_code_apply(request):
    user_or_resp = require_user_or_401(request)
    if isinstance(user_or_resp, JsonResponse):
        return user_or_resp
    user = user_or_resp

    if user.author_code:
        return JsonResponse({"error": "author_code already applied"}, status=400)

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json"}, status=400)

    code = (body.get("code") or "").strip()
    if not code:
        return JsonResponse({"error": "code is required"}, status=400)

    user.author_code = code
    user.author_code_applied_at = timezone.now()
    user.save(update_fields=["author_code", "author_code_applied_at", "updated_at"])

    # If code exists in registry, award points (optional). Unknown codes are still stored.
    ac = AuthorCode.objects.filter(code=code, active=True).select_related("owner").first()
    if ac:
        user.points = int(user.points or 0) + 10
        user.save(update_fields=["points", "updated_at"])
        ac.owner.points = int(ac.owner.points or 0) + 10
        ac.owner.save(update_fields=["points", "updated_at"])

    EventLog.objects.create(
        user=user,
        event_type=EventType.APPLY_CODE,
        payload={"code": code, "known": bool(ac), "author_wallet": ac.owner.wallet_address if ac else None},
    )
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def payments_create(request):
    user_or_resp = require_user_or_401(request)
    if isinstance(user_or_resp, JsonResponse):
        return user_or_resp
    user = user_or_resp

    try:
        intent = create_payment_intent(user)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    EventLog.objects.create(
        user=user,
        event_type=EventType.PAYMENT_CREATE,
        payload={
            "comment": intent.comment,
            "forward_ton_nanotons": intent.forward_ton_nanotons,
            "jetton_master": intent.jetton_master,
            "jetton_amount": intent.jetton_amount,
        },
    )

    return JsonResponse(
        {
            # backward-compatible
            "amount": intent.forward_ton_nanotons,
            "amount_usd_cents": intent.amount_usd_cents,
            # backward-compatible
            "receiver": intent.receiver_wallet,
            "forward_ton_nanotons": intent.forward_ton_nanotons,
            "receiver_wallet": intent.receiver_wallet,
            "jetton_master": intent.jetton_master,
            "jetton_amount": intent.jetton_amount,
            "comment": intent.comment,
            "valid_until": intent.valid_until,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def payments_confirm(request):
    user_or_resp = require_user_or_401(request)
    if isinstance(user_or_resp, JsonResponse):
        return user_or_resp
    user = user_or_resp

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json"}, status=400)

    tx_hash = (body.get("tx_hash") or "").strip()
    try:
        payment = confirm_payment(user, tx_hash)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    EventLog.objects.create(
        user=user,
        event_type=EventType.PAYMENT_CONFIRM,
        payload={"tx_hash": tx_hash, "payment_id": payment.id, "status": payment.status},
    )

    return JsonResponse({"ok": True, "status": payment.status})


@csrf_exempt
@require_http_methods(["POST"])
def intent(request):
    """
    SSOT: reserve referrer slot (3/3) and create Participation(PENDING).
    Referrer and author code are REQUIRED.
    """
    user_or_resp = require_user_or_401(request)
    if isinstance(user_or_resp, JsonResponse):
        return user_or_resp
    user = user_or_resp

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json"}, status=400)

    ref_tid = body.get("referrer_telegram_id")
    if ref_tid is None:
        ref_tid = user.inviter_telegram_id
    if ref_tid is not None and str(ref_tid).strip() != "":
        try:
            ref_tid = int(ref_tid)
        except Exception:
            return JsonResponse({"error": "referrer_telegram_id is invalid"}, status=400)
    else:
        ref_tid = None

    # Author code is optional.
    code = (body.get("author_code") or user.author_code or "").strip()

    try:
        with transaction.atomic():
            part, pay_intent, used_slots = _create_intent(user=user, referrer_telegram_id=ref_tid, author_code=code)
    except RuntimeError as e:
        if str(e) == "referrer_limit":
            return JsonResponse({"error": "referrer_limit", "used_slots": 3}, status=409)
        raise
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    EventLog.objects.create(
        user=user,
        event_type=EventType.INTENT_CREATE,
        payload={
            "participation_id": part.id,
            "comment": pay_intent.comment,
            "forward_ton_nanotons": pay_intent.forward_ton_nanotons,
            "jetton_master": pay_intent.jetton_master,
            "jetton_amount": pay_intent.jetton_amount,
        },
    )

    return JsonResponse(
        {
            "ok": True,
            "participation": {"id": part.id, "status": part.status},
            "referrer": {"telegram_id": ref_tid},
            "slots": {"used": used_slots, "limit": 3},
            "payment": {
                # backward-compatible
                "amount": pay_intent.forward_ton_nanotons,
                "amount_usd_cents": pay_intent.amount_usd_cents,
                # backward-compatible
                "receiver": pay_intent.receiver_wallet,
                "forward_ton_nanotons": pay_intent.forward_ton_nanotons,
                "receiver_wallet": pay_intent.receiver_wallet,
                "jetton_master": pay_intent.jetton_master,
                "jetton_amount": pay_intent.jetton_amount,
                "comment": pay_intent.comment,
                "valid_until": pay_intent.valid_until,
            },
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def participation_create(request):
    """
    SSOT: create Participation(PENDING) and return payment intent to send 15 USDT (MVP uses TON transfer placeholder).
    We reuse /payments/create logic for now, but also create a Participation record.
    """
    user_or_resp = require_user_or_401(request)
    if isinstance(user_or_resp, JsonResponse):
        return user_or_resp
    user = user_or_resp

    # Backward-compatible wrapper around /intent.
    # Referrer is required for everyone except seed-first user (handled inside _create_intent).
    try:
        with transaction.atomic():
            part, pay_intent, used_slots = _create_intent(
                user=user,
                referrer_telegram_id=int(user.inviter_telegram_id) if user.inviter_telegram_id else None,
                author_code=str(user.author_code or ""),
            )
    except RuntimeError:
        return JsonResponse({"error": "referrer_limit"}, status=409)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse(
        {
            # backward-compatible
            "amount": pay_intent.forward_ton_nanotons,
            "amount_usd_cents": pay_intent.amount_usd_cents,
            # backward-compatible
            "receiver": pay_intent.receiver_wallet,
            "forward_ton_nanotons": pay_intent.forward_ton_nanotons,
            "receiver_wallet": pay_intent.receiver_wallet,
            "jetton_master": pay_intent.jetton_master,
            "jetton_amount": pay_intent.jetton_amount,
            "comment": pay_intent.comment,
            "valid_until": pay_intent.valid_until,
            "status": part.status,
            "participation_id": part.id,
            "slots_used": used_slots,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def participation_confirm(request):
    """
    Admin-only: confirm participation (MVP manual).
    Auth via X-Admin-Token env var.
    """
    admin_token = _admin_secret()
    got = (request.headers.get("X-Admin-Token") or "").strip()
    if not admin_token or got != admin_token:
        return JsonResponse({"error": "forbidden"}, status=403)

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json"}, status=400)

    part_id = body.get("participation_id")
    wallet = (body.get("wallet_address") or "").strip()
    decision = (body.get("decision") or "confirm").strip().lower()
    note = (body.get("note") or "").strip()
    tx_hash = (body.get("tx_hash") or "").strip()
    if not wallet and not part_id:
        return JsonResponse({"error": "wallet_address or participation_id is required"}, status=400)

    part = None
    user = None
    if part_id is not None:
        try:
            part = Participation.objects.select_related("user").filter(id=int(part_id)).first()
        except Exception:
            part = None
        if not part:
            return JsonResponse({"error": "participation not found"}, status=404)
        user = part.user
        if part.status not in {ParticipationState.NEW, ParticipationState.PENDING}:
            return JsonResponse({"error": "participation is not pending"}, status=400)
    else:
        user = UserProfile.objects.filter(wallet_address=wallet).first()
        if not user:
            return JsonResponse({"error": "user not found"}, status=404)
        part = (
            Participation.objects.filter(user=user, status__in=[ParticipationState.NEW, ParticipationState.PENDING])
            .order_by("-created_at")
            .first()
        )
        if not part:
            return JsonResponse({"error": "no pending participation"}, status=400)

    if decision == "reject":
        part.status = ParticipationState.REJECTED
        part.admin_note = note
        if tx_hash:
            part.tx_hash = tx_hash
        part.confirmed_at = timezone.now()
        part.save(update_fields=["status", "admin_note", "tx_hash", "confirmed_at"])
        user.participation_status = ParticipationStatus.NEW
        user.save(update_fields=["participation_status", "updated_at"])
        EventLog.objects.create(
            user=user,
            event_type=EventType.PARTICIPATION_CONFIRM,
            payload={"decision": "reject", "participation_id": part.id, "tx_hash": tx_hash or None, "note": note},
        )
        return JsonResponse({"ok": True, "status": "REJECTED"})

    # confirm
    if tx_hash:
        dup = (
            Participation.objects.exclude(id=part.id)
            .filter(tx_hash=tx_hash, status__in=[ParticipationState.NEW, ParticipationState.PENDING, ParticipationState.CONFIRMED])
            .exists()
        )
        if dup:
            EventLog.objects.create(
                user=user,
                event_type=EventType.PARTICIPATION_CONFIRM,
                payload={"decision": "confirm", "error": "dup_tx", "tx_hash": tx_hash, "participation_id": part.id},
            )
            return JsonResponse({"error": "dup_tx"}, status=400)

    part.status = ParticipationState.CONFIRMED
    part.admin_note = note
    if tx_hash:
        part.tx_hash = tx_hash
    part.confirmed_at = timezone.now()
    part.save(update_fields=["status", "admin_note", "tx_hash", "confirmed_at"])

    user.participation_status = ParticipationStatus.ACTIVE
    user.save(update_fields=["participation_status", "updated_at"])

    # Update referrer stats (for UI only; SSOT remains Participation)
    if part.referrer_id:
        try:
            ref = UserProfile.objects.get(id=part.referrer_id)
            ref.paid_count = int(ref.paid_count or 0) + 1
            ref.save(update_fields=["paid_count", "updated_at"])
        except Exception:
            pass

    EventLog.objects.create(
        user=user,
        event_type=EventType.PARTICIPATION_CONFIRM,
        payload={"decision": "confirm", "participation_id": part.id, "tx_hash": tx_hash or None, "note": note},
    )
    return JsonResponse({"ok": True, "status": "CONFIRMED"})


@csrf_exempt
@require_http_methods(["GET"])
def referrals_l1(request):
    user_or_resp = require_user_or_401(request)
    if isinstance(user_or_resp, JsonResponse):
        return user_or_resp
    user = user_or_resp

    cycle_start = _cycle_start_dt(user)
    active = _active_participation(user)
    payout_window_start = active.created_at if active else None

    qs = (
        Participation.objects.filter(referrer=user, created_at__gt=cycle_start)
        .select_related("user")
        .order_by("-created_at")[:200]
    )

    items = []
    for p in qs:
        paid = p.status == ParticipationState.CONFIRMED and (payout_window_start is not None and p.created_at > payout_window_start)
        items.append(
            {
                "participation_id": p.id,
                "status": p.status,
                "paid": bool(paid),
                "created_at": p.created_at.isoformat(),
                "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None,
                "user": {
                    "wallet_address": p.user.wallet_address,
                    "telegram_id": p.user.telegram_id,
                    "telegram_username": p.user.telegram_username,
                    "participation_status": p.user.participation_status,
                },
            }
        )

    return JsonResponse({"items": items, "slots": {"used": _referrer_used_slots(user), "limit": 3}})


@csrf_exempt
@require_http_methods(["POST"])
def payout_request(request):
    """
    Create payout request (33 USDT stub) when user has:
    - active participation CONFIRMED
    - 3 L1 confirmed after active participation start
    - no open payout request
    """
    user_or_resp = require_user_or_401(request)
    if isinstance(user_or_resp, JsonResponse):
        return user_or_resp
    user = user_or_resp

    active = _active_participation(user)
    if not active or active.status != ParticipationState.CONFIRMED:
        return JsonResponse({"error": "participation_not_confirmed"}, status=400)

    confirmed_l1 = _confirmed_l1_count(user)
    if confirmed_l1 < 3:
        return JsonResponse({"error": "not_eligible", "confirmed_l1": confirmed_l1}, status=400)

    open_payout = PayoutRequest.objects.filter(user=user, status__in=[PayoutStatus.REQUESTED, PayoutStatus.APPROVED]).exists()
    if open_payout:
        return JsonResponse({"error": "payout_already_requested"}, status=409)

    # payout stub: 1 USDT
    pr = PayoutRequest.objects.create(
        user=user,
        amount_points=0,
        amount_usd_cents=int(os.getenv("PAYOUT_AMOUNT_USD_CENTS", "100")),
        status=PayoutStatus.REQUESTED,
    )
    EventLog.objects.create(
        user=user,
        event_type=EventType.PAYOUT_REQUEST,
        payload={"payout_request_id": pr.id, "amount_usd_cents": pr.amount_usd_cents},
    )
    return JsonResponse({"ok": True, "status": pr.status, "payout_request_id": pr.id})


@csrf_exempt
@require_http_methods(["GET"])
def payout_me(request):
    user_or_resp = require_user_or_401(request)
    if isinstance(user_or_resp, JsonResponse):
        return user_or_resp
    user = user_or_resp

    qs = PayoutRequest.objects.filter(user=user).order_by("-created_at")[:50]
    return JsonResponse(
        {
            "items": [
                {
                    "id": p.id,
                    "status": p.status,
                    "tx_hash": p.tx_hash,
                    "amount_usd_cents": p.amount_usd_cents,
                    "created_at": p.created_at.isoformat(),
                    "updated_at": p.updated_at.isoformat(),
                }
                for p in qs
            ]
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def payout_mark(request):
    """
    Admin-only: mark payout as SENT (we map to PayoutStatus.PAID) and close user's cycle.
    """
    admin_token = _admin_secret()
    got = (request.headers.get("X-Admin-Token") or "").strip()
    if not admin_token or got != admin_token:
        return JsonResponse({"error": "forbidden"}, status=403)

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json"}, status=400)

    payout_id = body.get("payout_request_id")
    wallet = (body.get("wallet_address") or "").strip()
    decision = (body.get("decision") or "sent").strip().lower()
    tx_hash = (body.get("tx_hash") or "").strip()
    note = (body.get("note") or "").strip()
    if not wallet and payout_id is None:
        return JsonResponse({"error": "wallet_address or payout_request_id is required"}, status=400)

    pr = None
    user = None
    if payout_id is not None:
        try:
            pr = PayoutRequest.objects.select_related("user").filter(id=int(payout_id)).first()
        except Exception:
            pr = None
        if not pr:
            return JsonResponse({"error": "payout_request not found"}, status=404)
        user = pr.user
        if pr.status not in {PayoutStatus.REQUESTED, PayoutStatus.APPROVED}:
            return JsonResponse({"error": "payout_request is not open"}, status=400)
    else:
        user = UserProfile.objects.filter(wallet_address=wallet).first()
        if not user:
            return JsonResponse({"error": "user not found"}, status=404)
        pr = (
            PayoutRequest.objects.filter(user=user, status__in=[PayoutStatus.REQUESTED, PayoutStatus.APPROVED])
            .order_by("-created_at")
            .first()
        )
        if not pr:
            return JsonResponse({"error": "no open payout request"}, status=400)

    if decision == "reject":
        pr.status = PayoutStatus.REJECTED
        pr.admin_note = note
        pr.save(update_fields=["status", "admin_note", "updated_at"])
        EventLog.objects.create(user=user, event_type=EventType.PAYOUT_MARK, payload={"decision": "reject", "payout_request_id": pr.id})
        return JsonResponse({"ok": True, "status": pr.status})

    if not tx_hash:
        return JsonResponse({"error": "tx_hash is required"}, status=400)

    pr.status = PayoutStatus.PAID  # SENT
    pr.tx_hash = tx_hash
    pr.admin_note = note
    pr.save(update_fields=["status", "tx_hash", "admin_note", "updated_at"])

    user.participation_status = ParticipationStatus.COMPLETED
    user.payouts_count = int(user.payouts_count or 0) + 1
    user.save(update_fields=["participation_status", "payouts_count", "updated_at"])

    EventLog.objects.create(
        user=user,
        event_type=EventType.PAYOUT_MARK,
        payload={"decision": "sent", "payout_request_id": pr.id, "tx_hash": tx_hash},
    )
    return JsonResponse({"ok": True, "status": pr.status})


@csrf_exempt
@require_http_methods(["GET"])
def jetton_wallet(request):
    """
    Returns user's jetton-wallet address for given jetton master (USDT by default).
    Needed to send JettonTransfer via TonConnect (Tonkeeper).
    """
    user_or_resp = require_user_or_401(request)
    if isinstance(user_or_resp, JsonResponse):
        return user_or_resp
    user = user_or_resp

    master = (request.GET.get("master") or os.getenv("USDT_JETTON_MASTER") or "").strip()
    if not master:
        return JsonResponse({"error": "missing USDT_JETTON_MASTER"}, status=500)

    try:
        jw = get_jetton_wallet_address(owner_address=user.wallet_address, jetton_master_address=master)
        return JsonResponse({"wallet_address": jw, "jetton_master": master})
    except ToncenterError as e:
        return JsonResponse({"error": str(e)}, status=502)


def _require_admin(request):
    admin_token = _admin_secret()
    got = (request.headers.get("X-Admin-Token") or "").strip()
    if not admin_token or got != admin_token:
        return JsonResponse({"error": "forbidden"}, status=403)
    return True


@csrf_exempt
@require_http_methods(["GET"])
def admin_participations_pending(request):
    ok = _require_admin(request)
    if ok is not True:
        return ok
    qs = (
        Participation.objects.filter(status__in=[ParticipationState.NEW, ParticipationState.PENDING])
        .select_related("user", "referrer")
        .order_by("created_at")[:200]
    )
    return JsonResponse(
        {
            "items": [
                {
                    "id": p.id,
                    "created_at": p.created_at.isoformat(),
                    "amount_usd_cents": p.amount_usd_cents,
                    "author_code": p.author_code,
                    "user": {
                        "wallet_address": p.user.wallet_address,
                        "telegram_id": p.user.telegram_id,
                        "telegram_username": p.user.telegram_username,
                    },
                    "referrer": {
                        "wallet_address": p.referrer.wallet_address if p.referrer else None,
                        "telegram_id": p.referrer.telegram_id if p.referrer else None,
                        "telegram_username": p.referrer.telegram_username if p.referrer else None,
                    },
                }
                for p in qs
            ]
        }
    )


@csrf_exempt
@require_http_methods(["GET"])
def admin_payouts_open(request):
    ok = _require_admin(request)
    if ok is not True:
        return ok
    qs = (
        PayoutRequest.objects.filter(status__in=[PayoutStatus.REQUESTED, PayoutStatus.APPROVED])
        .select_related("user")
        .order_by("created_at")[:200]
    )
    return JsonResponse(
        {
            "items": [
                {
                    "id": p.id,
                    "created_at": p.created_at.isoformat(),
                    "status": p.status,
                    "amount_usd_cents": p.amount_usd_cents,
                    "tx_hash": p.tx_hash,
                    "user": {
                        "wallet_address": p.user.wallet_address,
                        "telegram_id": p.user.telegram_id,
                        "telegram_username": p.user.telegram_username,
                    },
                }
                for p in qs
            ]
        }
    )


