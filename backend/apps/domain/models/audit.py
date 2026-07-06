from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        LOGIN = "login", "Login"
        LOGIN_FAILED = "login.failed", "Login failed"
        CREDENTIAL_OAUTH_INITIATE = "credential.oauth.initiate", "OAuth connection initiated"
        CREDENTIAL_CREATE = "credential.create", "Credential created"
        CREDENTIAL_ACTIVATE = "credential.activate", "Credential activated"
        PERMISSION_UPDATE = "permission.update", "Permission updated"
        MEMBERSHIP_CHANGE = "membership.change", "Membership changed"
        TEAM_CHANGE = "team.change", "Team changed"
        FILE_VIEW = "file.view", "File listed/viewed"
        FILE_DOWNLOAD = "file.download", "File downloaded"
        FILE_UPLOAD = "file.upload", "File uploaded"
        ACCESS_DENIED = "access.denied", "Access denied"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=64, choices=Action.choices)

    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"], name="idx_auditlog_created_at"),
            models.Index(fields=["target_type", "target_id"], name="idx_auditlog_target"),
        ]

    def __str__(self):
        ts = f"{self.created_at:%Y-%m-%d %H:%M:%S}" if self.created_at else "unsaved"
        return f"[{ts}] {self.action} by {self.actor or 'system'}"
