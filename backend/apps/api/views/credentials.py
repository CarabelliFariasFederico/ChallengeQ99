from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.api.permissions import ADMIN_PERMISSIONS
from apps.api.serializers import (
    DriveCredentialSerializer,
    PermissionMatrixSerializer,
    ServiceAccountCredentialCreateSerializer,
)
from apps.application import audit, credentials
from apps.domain.models import AuditLog, DriveCredential


class CredentialViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = DriveCredential.objects.defer("secret_ciphertext").order_by("id")
    permission_classes = ADMIN_PERMISSIONS

    def get_serializer_class(self):
        if self.action == "create":
            return ServiceAccountCredentialCreateSerializer
        return DriveCredentialSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = serializer.save()
        audit.record(
            request,
            AuditLog.Action.CREDENTIAL_CREATE,
            target_type="drive_credential",
            target_id=credential.pk,
            metadata={
                "account_label": credential.account_label,
                "auth_method": credential.auth_method,
                "key_version": credential.key_version,
            },
        )
        return Response(DriveCredentialSerializer(credential).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        credential = credentials.activate_credential(request, self.get_object())
        return Response(DriveCredentialSerializer(credential).data)

    @action(detail=True, methods=["get", "put"])
    def permissions(self, request, pk=None):
        if request.method == "GET":
            return Response({"permissions": credentials.permissions_matrix(self.get_object())})

        serializer = PermissionMatrixSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        after = credentials.set_permissions_matrix(
            request, self.get_object(), serializer.validated_data["permissions"]
        )
        return Response({"permissions": after})
