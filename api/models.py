from django.db import models
from django.utils import timezone


class ParticipationStatus(models.TextChoices):
    NEW = "NEW", "NEW"
    PENDING = "PENDING", "PENDING"
    ACTIVE = "ACTIVE", "ACTIVE"
    COMPLETED = "COMPLETED", "COMPLETED"
    BLOCKED = "BLOCKED", "BLOCKED"


class UserProfile(models.Model):
    wallet_address = models.CharField(max_length=128, unique=True, db_index=True)
    # Telegram WebApp binding (optional)
    telegram_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    telegram_username = models.CharField(max_length=64, null=True, blank=True)
    telegram_first_name = models.CharField(max_length=64, null=True, blank=True)

    # Referral / inviter (pending until user confirms / pays)
    inviter_wallet_address = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    inviter_telegram_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    inviter_set_at = models.DateTimeField(null=True, blank=True)

    # Author code (one-time)
    author_code = models.CharField(max_length=64, null=True, blank=True)
    author_code_applied_at = models.DateTimeField(null=True, blank=True)

    # Participation / stats
    participation_status = models.CharField(
        max_length=16,
        choices=ParticipationStatus.choices,
        default=ParticipationStatus.NEW,
        db_index=True,
    )
    invited_count = models.IntegerField(default=0)
    paid_count = models.IntegerField(default=0)
    payouts_count = models.IntegerField(default=0)
    points = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_profiles"
        indexes = [
            models.Index(fields=["wallet_address"]),
        ]

    def __str__(self) -> str:
        return self.wallet_address


class TonProofPayload(models.Model):
    """
    Stores issued TON Proof payloads (nonces) for short-lived, single-use verification.
    Simplest reliable storage: DB.
    """

    payload = models.CharField(max_length=255, unique=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ton_proof_payloads"
        indexes = [
            models.Index(fields=["payload"]),
            models.Index(fields=["expires_at"]),
        ]

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at


class PaymentStatus(models.TextChoices):
    CREATED = "CREATED", "CREATED"
    PENDING_REVIEW = "PENDING_REVIEW", "PENDING_REVIEW"
    CONFIRMED = "CONFIRMED", "CONFIRMED"
    FAILED = "FAILED", "FAILED"


class Payment(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="payments")
    amount_usd_cents = models.IntegerField(default=1500)
    amount_nanotons = models.CharField(max_length=32)  # sendTransaction expects string
    receiver_wallet = models.CharField(max_length=128)
    comment = models.CharField(max_length=128, unique=True, db_index=True)
    valid_until = models.DateTimeField()
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.CREATED, db_index=True)
    tx_hash = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["comment"]),
        ]


class PayoutStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "REQUESTED"
    APPROVED = "APPROVED", "APPROVED"
    PAID = "PAID", "PAID"
    REJECTED = "REJECTED", "REJECTED"


class PayoutRequest(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="payout_requests")
    amount_points = models.IntegerField()
    status = models.CharField(max_length=16, choices=PayoutStatus.choices, default=PayoutStatus.REQUESTED, db_index=True)
    admin_note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payout_requests"
        indexes = [
            models.Index(fields=["user", "status"]),
        ]


class EventType(models.TextChoices):
    LOGIN = "login", "login"
    CONNECT = "connect", "connect"
    TELEGRAM_VERIFY = "telegram_verify", "telegram_verify"
    APPLY_CODE = "apply_code", "apply_code"
    INVITER_SET = "inviter_set", "inviter_set"
    PAYMENT_CREATE = "payment_create", "payment_create"
    PAYMENT_CONFIRM = "payment_confirm", "payment_confirm"


class EventLog(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "event_logs"
        indexes = [
            models.Index(fields=["event_type", "created_at"]),
        ]


