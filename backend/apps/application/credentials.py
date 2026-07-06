from django.db import transaction
from django.utils import timezone

from apps.application import audit
from apps.domain.models import AuditLog, DriveCredential, GroupDrivePermission


def activate_credential(request, credential):
    with transaction.atomic():
        credential = DriveCredential.objects.select_for_update().get(pk=credential.pk)
        previous = (
            DriveCredential.objects.select_for_update()
            .filter(is_active=True)
            .exclude(pk=credential.pk)
            .first()
        )
        if previous:
            previous.is_active = False
            previous.save(update_fields=["is_active", "updated_at"])
        credential.is_active = True
        credential.rotated_at = timezone.now()
        credential.rotated_by = request.user
        credential.save(update_fields=["is_active", "rotated_at", "rotated_by", "updated_at"])
        audit.record(
            request,
            AuditLog.Action.CREDENTIAL_ACTIVATE,
            target_type="drive_credential",
            target_id=credential.pk,
            metadata={
                "activated": credential.account_label,
                "previous_active_id": previous.pk if previous else None,
            },
        )
    return credential


def permissions_matrix(credential):
    return {
        str(p.team_id): {
            "can_view": p.can_view,
            "can_download": p.can_download,
            "can_upload": p.can_upload,
        }
        for p in credential.team_permissions.all()
    }


def set_permissions_matrix(request, credential, rows):
    with transaction.atomic():
        before = permissions_matrix(credential)
        credential.team_permissions.all().delete()
        GroupDrivePermission.objects.bulk_create(
            GroupDrivePermission(
                credential=credential,
                team=row["team"],
                can_view=row["can_view"],
                can_download=row["can_download"],
                can_upload=row["can_upload"],
            )
            for row in rows
        )
        after = permissions_matrix(credential)
        audit.record(
            request,
            AuditLog.Action.PERMISSION_UPDATE,
            target_type="drive_credential",
            target_id=credential.pk,
            metadata={"before": before, "after": after},
        )
    return after
