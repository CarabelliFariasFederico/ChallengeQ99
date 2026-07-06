from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.application import audit
from apps.domain.models import AuditLog
from apps.domain.policies import Action, PermissionPolicy


class LoginView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed:
            attempted = str(request.data.get("email", ""))[:254]
            audit.record(
                request,
                AuditLog.Action.LOGIN_FAILED,
                actor=None,
                target_type="user",
                target_id=attempted,
                metadata={"email": attempted},
            )
            raise
        audit.record(
            request,
            AuditLog.Action.LOGIN,
            actor=serializer.user,
            target_type="user",
            target_id=serializer.user.pk,
        )
        return Response(serializer.validated_data)


class MeView(APIView):
    def get(self, request):
        credential = PermissionPolicy.active_credential()
        allowed = (
            PermissionPolicy.allowed_actions(request.user, credential) if credential else set()
        )
        return Response(
            {
                "id": request.user.pk,
                "email": request.user.email,
                "role": request.user.role,
                "capabilities": {
                    "can_view": Action.VIEW in allowed,
                    "can_download": Action.DOWNLOAD in allowed,
                    "can_upload": Action.UPLOAD in allowed,
                },
                "active_credential": {
                    "present": credential is not None,
                    "account_label": credential.account_label if credential else None,
                },
                "drive_gateway": "fake" if settings.DRIVE_GATEWAY_PROVIDER else "real",
            }
        )
