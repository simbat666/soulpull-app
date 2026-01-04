"""
Soulpull MVP — Models (согласно ТЗ §4, §13.1)

Модели:
- UserProfile: telegram_id (PK-like), wallet, username
- AuthorCode: owner → UserProfile, code unique
- Participation: user, referrer, author_code, tx_hash, status
- PayoutRequest: user, status, tx_hash
- RiskEvent: аудит событий безопасности
- TonProofPayload: nonce для TON Proof
"""

from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    """
    Профиль пользователя. telegram_id = уникальный идентификатор.
    wallet = TON адрес (nullable, unique когда установлен).
    """
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=64, blank=True, null=True)
    first_name = models.CharField(max_length=64, blank=True, null=True)
    wallet = models.CharField(max_length=128, blank=True, null=True, unique=True, db_index=True)
    points = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_profiles"
        indexes = [
            models.Index(fields=["telegram_id"]),
            models.Index(fields=["wallet"]),
        ]

    def __str__(self) -> str:
        return f"User({self.telegram_id})"


class AuthorCode(models.Model):
    """
    Авторские коды. Владелец получает $2 с каждого реферала, использующего код.
    """
    code = models.CharField(max_length=32, unique=True, db_index=True)
    owner = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="author_codes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "author_codes"
        indexes = [
            models.Index(fields=["code"]),
        ]

    def __str__(self) -> str:
        return f"AuthorCode({self.code})"


class ParticipationStatus(models.TextChoices):
    NEW = "NEW", "NEW"
    PENDING = "PENDING", "PENDING"
    CONFIRMED = "CONFIRMED", "CONFIRMED"
    REJECTED = "REJECTED", "REJECTED"


class Participation(models.Model):
    """
    Участие пользователя в текущем цикле.
    
    Инварианты:
    - На пользователя одновременно ≤1 записи в состояниях NEW|PENDING|CONFIRMED
    - tx_hash уникален среди всех Participation
    """
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="participations")
    referrer = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals"
    )
    author_code = models.CharField(max_length=32, blank=True, null=True)
    tx_hash = models.CharField(max_length=128, blank=True, null=True, unique=True, db_index=True)
    status = models.CharField(
        max_length=16,
        choices=ParticipationStatus.choices,
        default=ParticipationStatus.NEW,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "participations"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["referrer", "status"]),
            models.Index(fields=["referrer", "created_at"]),
            models.Index(fields=["tx_hash"]),
        ]

    def __str__(self) -> str:
        return f"Participation({self.id}, {self.status})"


class PayoutStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "REQUESTED"
    SENT = "SENT", "SENT"


class PayoutRequest(models.Model):
    """
    Заявка на выплату 33 USDT.
    Условия: user.status=CONFIRMED + 3 L1 paid=true.
    """
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="payout_requests")
    status = models.CharField(
        max_length=16,
        choices=PayoutStatus.choices,
        default=PayoutStatus.REQUESTED,
        db_index=True
    )
    tx_hash = models.CharField(max_length=128, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payout_requests"
        indexes = [
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return f"PayoutRequest({self.id}, {self.status})"


class RiskEventKind(models.TextChoices):
    RATE_LIMIT = "RATE_LIMIT", "RATE_LIMIT"
    DUP_TX = "DUP_TX", "DUP_TX"
    WALLET_REUSED = "WALLET_REUSED", "WALLET_REUSED"
    ACTIVE_CYCLE = "ACTIVE_CYCLE", "ACTIVE_CYCLE"
    REF_LIMIT = "REF_LIMIT", "REF_LIMIT"
    SELF_REFERRAL = "SELF_REFERRAL", "SELF_REFERRAL"
    BAD_TX = "BAD_TX", "BAD_TX"


class RiskEvent(models.Model):
    """
    Аудит событий безопасности. Хранить 90 дней.
    """
    user = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="risk_events")
    kind = models.CharField(max_length=32, choices=RiskEventKind.choices, db_index=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "risk_events"
        indexes = [
            models.Index(fields=["kind", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"RiskEvent({self.kind})"


class TonProofPayload(models.Model):
    """
    Nonce для TON Proof верификации. TTL: 5 минут, single-use.
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


class IdempotencyKey(models.Model):
    """
    Идемпотентность для /intent и /confirm.
    """
    key = models.CharField(max_length=64, unique=True, db_index=True)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "idempotency_keys"


class PaymentOrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    EXPIRED = "expired", "Expired"


class PaymentOrder(models.Model):
    """
    Заказ на оплату через TonConnect.
    
    Флоу:
    1. Frontend вызывает create_order → получает order_id + tx для TonConnect
    2. Frontend вызывает tonConnectUI.sendTransaction(tx)
    3. Frontend поллит order_status
    4. Backend проверяет через TonAPI и помечает paid
    """
    import uuid
    
    public_id = models.CharField(max_length=32, unique=True, db_index=True)
    
    # Связь с пользователем и участием
    user = models.ForeignKey(
        UserProfile, 
        on_delete=models.CASCADE, 
        related_name="payment_orders",
        null=True, blank=True
    )
    participation = models.ForeignKey(
        'Participation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="payment_orders"
    )
    
    # Адрес кошелька отправителя (из TonConnect)
    wallet_address = models.CharField(max_length=128, blank=True, default="")
    
    # Сумма в нанотонах (1 TON = 1e9 nanoTON)
    amount_nano = models.BigIntegerField()
    
    # Комментарий для идентификации платежа
    comment = models.CharField(max_length=128, blank=True, default="")
    
    # Статус
    status = models.CharField(
        max_length=16, 
        choices=PaymentOrderStatus.choices, 
        default=PaymentOrderStatus.PENDING,
        db_index=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    paid_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # TonAPI event ID (для аудита)
    paid_event_id = models.CharField(max_length=128, blank=True, default="")
    paid_tx_hash = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        db_table = "payment_orders"
        indexes = [
            models.Index(fields=["public_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["wallet_address"]),
            models.Index(fields=["created_at"]),
        ]

    @staticmethod
    def new_public_id() -> str:
        import uuid
        return uuid.uuid4().hex[:20]

    def mark_paid(self, event_id: str = "", tx_hash: str = ""):
        """Отметить заказ как оплаченный"""
        self.status = PaymentOrderStatus.PAID
        self.paid_at = timezone.now()
        if event_id:
            self.paid_event_id = event_id
        if tx_hash:
            self.paid_tx_hash = tx_hash
        self.save(update_fields=["status", "paid_at", "paid_event_id", "paid_tx_hash"])
        
        # Если есть связанное участие — обновить его статус
        if self.participation:
            self.participation.status = ParticipationStatus.PENDING
            self.participation.tx_hash = tx_hash or event_id
            self.participation.save(update_fields=["status", "tx_hash"])

    def is_expired(self) -> bool:
        if self.expires_at:
            return timezone.now() >= self.expires_at
        # По умолчанию заказ живёт 30 минут
        return timezone.now() >= self.created_at + timezone.timedelta(minutes=30)

    def __str__(self) -> str:
        return f"PaymentOrder({self.public_id}, {self.status})"
