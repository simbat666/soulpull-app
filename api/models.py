from django.db import models
from django.core.validators import MinValueValidator


class UserProfile(models.Model):
    """
    Профиль пользователя, связанный с Telegram ID.
    """
    telegram_id = models.BigIntegerField(unique=True, db_index=True, help_text="Telegram user ID")
    wallet_address = models.CharField(max_length=64, blank=True, null=True, help_text="TON wallet address")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profiles'
        indexes = [
            models.Index(fields=['telegram_id']),
            models.Index(fields=['wallet_address']),
        ]

    def __str__(self):
        return f"UserProfile(telegram_id={self.telegram_id})"


class AuthorCode(models.Model):
    """
    Код автора для регистрации пользователей.
    """
    code = models.CharField(max_length=32, unique=True, db_index=True, help_text="Unique author code")
    is_active = models.BooleanField(default=True, help_text="Whether the code is active")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Optional expiration date")

    class Meta:
        db_table = 'author_codes'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"AuthorCode(code={self.code}, active={self.is_active})"


class Participation(models.Model):
    """
    Участие пользователя в системе.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('FAILED', 'Failed'),
    ]

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='participations')
    tx_hash = models.CharField(max_length=64, unique=True, db_index=True, help_text="Transaction hash")
    amount = models.DecimalField(max_digits=20, decimal_places=9, validators=[MinValueValidator(0)], help_text="Amount in USDT")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'participations'
        indexes = [
            models.Index(fields=['tx_hash']),
            models.Index(fields=['status']),
            models.Index(fields=['user', 'status']),
        ]
        # Уникальность tx_hash обеспечивается через unique=True

    def __str__(self):
        return f"Participation(user={self.user.telegram_id}, tx_hash={self.tx_hash[:16]}..., status={self.status})"


class PayoutRequest(models.Model):
    """
    Запрос на выплату пользователю.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PAID', 'Paid'),
    ]

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='payout_requests')
    amount = models.DecimalField(max_digits=20, decimal_places=9, validators=[MinValueValidator(0)], help_text="Amount to payout")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    wallet_address = models.CharField(max_length=64, help_text="Wallet address for payout")
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, help_text="Admin notes about the payout")

    class Meta:
        db_table = 'payout_requests'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"PayoutRequest(user={self.user.telegram_id}, amount={self.amount}, status={self.status})"


class RiskEvent(models.Model):
    """
    Событие риска, связанное с пользователем или транзакцией.
    """
    EVENT_TYPE_CHOICES = [
        ('SUSPICIOUS_TX', 'Suspicious Transaction'),
        ('MULTIPLE_ACCOUNTS', 'Multiple Accounts'),
        ('FRAUD', 'Fraud'),
        ('OTHER', 'Other'),
    ]

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='risk_events', null=True, blank=True)
    participation = models.ForeignKey(Participation, on_delete=models.CASCADE, related_name='risk_events', null=True, blank=True)
    event_type = models.CharField(max_length=32, choices=EVENT_TYPE_CHOICES, db_index=True)
    description = models.TextField(help_text="Description of the risk event")
    severity = models.IntegerField(default=1, help_text="Severity level (1-10)")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'risk_events'
        indexes = [
            models.Index(fields=['event_type']),
            models.Index(fields=['resolved']),
            models.Index(fields=['user', 'resolved']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"RiskEvent(type={self.event_type}, user={self.user.telegram_id if self.user else 'N/A'}, severity={self.severity})"
