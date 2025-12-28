from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    wallet_address = models.CharField(max_length=128, unique=True, db_index=True)
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


