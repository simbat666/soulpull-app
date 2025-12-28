import os
import secrets
from dataclasses import dataclass

from django.utils import timezone

from api.models import Payment, PaymentStatus, ParticipationStatus, UserProfile


@dataclass(frozen=True)
class PaymentIntent:
    amount_nanotons: str
    receiver: str
    comment: str
    valid_until: int  # unix seconds
    amount_usd_cents: int


def _receiver_wallet() -> str:
    return (os.getenv("RECEIVER_WALLET") or "").strip()


def _ticket_amount_usd_cents() -> int:
    return int(os.getenv("TICKET_AMOUNT_USD_CENTS", "1500"))


def _ticket_amount_nanotons() -> str:
    return (os.getenv("TICKET_AMOUNT_NANOTONS") or "").strip() or "1500000000"


def create_payment_intent(user: UserProfile) -> PaymentIntent:
    receiver = _receiver_wallet()
    if not receiver:
        raise ValueError("missing RECEIVER_WALLET")

    now = timezone.now()
    valid_until_dt = now + timezone.timedelta(minutes=15)
    comment = f"ticket:{secrets.token_urlsafe(12)}"

    payment = Payment.objects.create(
        user=user,
        amount_usd_cents=_ticket_amount_usd_cents(),
        amount_nanotons=_ticket_amount_nanotons(),
        receiver_wallet=receiver,
        comment=comment,
        valid_until=valid_until_dt,
        status=PaymentStatus.CREATED,
    )

    return PaymentIntent(
        amount_nanotons=payment.amount_nanotons,
        receiver=payment.receiver_wallet,
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


