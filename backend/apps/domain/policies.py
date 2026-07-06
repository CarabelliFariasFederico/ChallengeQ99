from enum import Enum

from apps.domain.models import DriveCredential, GroupDrivePermission


class Action(Enum):
    VIEW = "view"
    DOWNLOAD = "download"
    UPLOAD = "upload"


_ACTION_FLAG = {
    Action.VIEW: "can_view",
    Action.DOWNLOAD: "can_download",
    Action.UPLOAD: "can_upload",
}


def _is_eligible(user) -> bool:
    return (
        user is not None
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
    )


class PermissionPolicy:
    @staticmethod
    def can(user, action, credential) -> bool:
        if credential is None or not _is_eligible(user):
            return False
        flag = _ACTION_FLAG[Action(action)]
        return GroupDrivePermission.objects.filter(
            credential=credential,
            team__memberships__user=user,
            **{flag: True},
        ).exists()

    @staticmethod
    def allowed_actions(user, credential) -> set[Action]:
        if credential is None or not _is_eligible(user):
            return set()
        rows = GroupDrivePermission.objects.filter(
            credential=credential,
            team__memberships__user=user,
        ).values_list("can_view", "can_download", "can_upload")
        allowed = set()
        for can_view, can_download, can_upload in rows:
            if can_view:
                allowed.add(Action.VIEW)
            if can_download:
                allowed.add(Action.DOWNLOAD)
            if can_upload:
                allowed.add(Action.UPLOAD)
        return allowed

    @staticmethod
    def active_credential():
        return DriveCredential.objects.filter(is_active=True).first()

    @classmethod
    def can_on_active(cls, user, action) -> bool:
        credential = cls.active_credential()
        if credential is None:
            return False
        return cls.can(user, action, credential)

    @classmethod
    def allowed_actions_on_active(cls, user) -> set[Action]:
        credential = cls.active_credential()
        if credential is None:
            return set()
        return cls.allowed_actions(user, credential)
