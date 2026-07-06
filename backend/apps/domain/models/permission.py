from django.db import models

from apps.domain.models.credential import DriveCredential
from apps.domain.models.team import Team


class GroupDrivePermission(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="drive_permissions")
    credential = models.ForeignKey(
        DriveCredential, on_delete=models.CASCADE, related_name="team_permissions"
    )
    can_view = models.BooleanField(default=False)
    can_download = models.BooleanField(default=False)
    can_upload = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["team", "credential"], name="uniq_permission_team_credential"
            ),
        ]

    def __str__(self):
        return f"{self.team} -> {self.credential}"
