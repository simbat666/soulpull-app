import os
import secrets
from dataclasses import dataclass

from django.utils import timezone

from api.models import Payment, PaymentStatus, ParticipationStatus, UserProfile


@dataclass(frozen=True)
class PaymentIntent:
    # TON to attach to transaction when sending jetton transfer (gas / forward TON)
    forward_ton_nanotons: str
    # Receiver OWNER wallet address (not jetton wallet). Jetton transfer will send to this owner.
    receiver_wallet: str
    jetton_master: str
    jetton_amount: str  # in jetton units (USDT has 6 decimals)
    comment: str
    valid_until: int  # unix seconds
    amount_usd_cents: int


def _receiver_wallet() -> str:
    return (os.getenv("RECEIVER_WALLET") or "").strip()


def _ticket_amount_usd_cents() -> int:
    # 15 USDT = 1500 cents
    return int(os.getenv("TICKET_AMOUNT_USD_CENTS", "1500"))


def _ticket_jetton_amount() -> str:
    # 15 USDT (6 decimals) => 15_000_000
    return (os.getenv("TICKET_JETTON_AMOUNT") or "").strip() or "15000000"


def _forward_ton_nanotons() -> str:
    # Safe default for Jetton transfer: 0.05 TON
    return (os.getenv("PAY_FORWARD_TON_NANOTONS") or "").strip() or "50000000"


def _jetton_master() -> str:
    return (os.getenv("USDT_JETTON_MASTER") or "").strip()


def create_payment_intent(user: UserProfile) -> PaymentIntent:
    receiver_wallet = _receiver_wallet()
    if not receiver_wallet:
        raise ValueError("missing RECEIVER_WALLET")
    master = _jetton_master()
    if not master:
        raise ValueError("missing USDT_JETTON_MASTER")

    now = timezone.now()
    valid_until_dt = now + timezone.timedelta(minutes=15)
    comment = f"ticket:{secrets.token_urlsafe(12)}"

    payment = Payment.objects.create(
        user=user,
        amount_usd_cents=_ticket_amount_usd_cents(),
        amount_nanotons=_forward_ton_nanotons(),
        receiver_wallet=receiver_wallet,
        comment=comment,
        valid_until=valid_until_dt,
        status=PaymentStatus.CREATED,
    )

    return PaymentIntent(
        forward_ton_nanotons=payment.amount_nanotons,
        receiver_wallet=payment.receiver_wallet,
        jetton_master=master,
        jetton_amount=_ticket_jetton_amount(),
        comment=payment.comment,
        valid_until=int(valid_until_dt.timestamp()),
        amount_usd_cents=payment.amount_usd_cents,
    )


def confirm_payment(user: UserProfile, tx_hash: str) -> Payment:
    tx_hash = (tx_hash or "").strip()
    if not tx_hash:
        raise ValueError("missing tx_hash")

    payment = (
        Payment.objects.filter(user=user)
        .exclude(status=PaymentStatus.FAILED)
        .order_by("-created_at")
        .first()
    )
    if not payment:
        raise ValueError("no payment intent")

    payment.tx_hash = tx_hash
    payment.status = PaymentStatus.PENDING_REVIEW
    payment.save(update_fields=["tx_hash", "status", "updated_at"])

    if user.participation_status == ParticipationStatus.NEW:
        user.participation_status = ParticipationStatus.PENDING
        user.save(update_fields=["participation_status", "updated_at"])

    return payment


