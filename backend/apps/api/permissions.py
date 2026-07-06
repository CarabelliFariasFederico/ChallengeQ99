from rest_framework.permissions import BasePermission, IsAuthenticated

from apps.domain.policies import Action, PermissionPolicy
from apps.infrastructure.drive.factory import NoActiveCredentialError


class IsAdministrator(BasePermission):
    message = "Administrator role required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_administrator)


def HasDrivePermission(action):
    action = Action(action)

    class _HasDrivePermission(BasePermission):
        message = f"Missing '{action.value}' permission on the active Drive credential."

        def has_permission(self, request, view):
            credential = PermissionPolicy.active_credential()
            if credential is None:
                raise NoActiveCredentialError(
                    "No active Drive credential; an administrator must activate one."
                )
            return PermissionPolicy.can(request.user, action, credential)

    _HasDrivePermission.__name__ = f"HasDrivePermission_{action.value}"
    return _HasDrivePermission


ADMIN_PERMISSIONS = [IsAuthenticated, IsAdministrator]
