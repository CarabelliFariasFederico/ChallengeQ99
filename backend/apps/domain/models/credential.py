from django.conf import settings
from django.db import models
from django.db.models import Q


class DriveCredential(models.Model):
    class AuthMethod(models.TextChoices):
        OAUTH = "oauth", "OAuth"
        SERVICE_ACCOUNT = "service_account", "Service account"

    account_label = models.CharField(max_length=255)
    auth_method = models.CharField(max_length=32, choices=AuthMethod.choices)

    secret_ciphertext = models.BinaryField(blank=True, default=b"")
    key_version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=False)
    rotated_at = models.DateTimeField(null=True, blank=True)
    rotated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rotated_credentials",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=Q(is_active=True),
                name="uniq_single_active_drive_credential",
            ),
        ]

    def __str__(self):
        return f"{self.account_label} ({self.get_auth_method_display()})"

    def set_secret(self, plaintext):
        from apps.infrastructure.crypto.secret_box import SecretBox

        box = SecretBox.from_settings()
        self.secret_ciphertext = box.encrypt(plaintext)
        self.key_version = box.current_version

    def get_secret(self) -> bytes:
        from apps.infrastructure.crypto.secret_box import DecryptionError, SecretBox

        if not self.secret_ciphertext:
            raise DecryptionError(f"Credential '{self.account_label}' has no stored secret.")
        box = SecretBox.from_settings()
        return box.decrypt(self.secret_ciphertext, key_version=self.key_version)
