from django.conf import settings
from django.db import models


class OAuthState(models.Model):
    state = models.CharField(max_length=64, unique=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="oauth_states"
    )
    account_label = models.CharField(max_length=255, default="Google Drive (OAuth)")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"oauth-state for {self.initiated_by} (expires {self.expires_at:%H:%M:%S})"
