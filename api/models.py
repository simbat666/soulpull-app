from django.db import models


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


