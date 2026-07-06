from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.api.permissions import ADMIN_PERMISSIONS
from apps.api.serializers import MembershipChangeSerializer, TeamSerializer
from apps.application import audit
from apps.domain.models import AuditLog, Membership, Team


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.prefetch_related("members").order_by("name")
    serializer_class = TeamSerializer
    permission_classes = ADMIN_PERMISSIONS
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_create(self, serializer):
        team = serializer.save()
        audit.record(
            self.request,
            AuditLog.Action.TEAM_CHANGE,
            target_type="team",
            target_id=team.pk,
            metadata={"change": "created", "name": team.name},
        )

    def perform_update(self, serializer):
        previous_name = serializer.instance.name
        team = serializer.save()
        audit.record(
            self.request,
            AuditLog.Action.TEAM_CHANGE,
            target_type="team",
            target_id=team.pk,
            metadata={"change": "updated", "name": team.name, "previous_name": previous_name},
        )

    def perform_destroy(self, instance):
        with transaction.atomic():
            cascaded = {
                "members": list(instance.members.values_list("email", flat=True)),
                "grants": {
                    str(p.credential_id): {
                        "can_view": p.can_view,
                        "can_download": p.can_download,
                        "can_upload": p.can_upload,
                    }
                    for p in instance.drive_permissions.all()
                },
            }
            team_pk, team_name = instance.pk, instance.name
            instance.delete()
            audit.record(
                self.request,
                AuditLog.Action.TEAM_CHANGE,
                target_type="team",
                target_id=team_pk,
                metadata={"change": "deleted", "name": team_name, "cascaded": cascaded},
            )

    @action(detail=True, methods=["post", "delete"], url_path="members")
    def members(self, request, pk=None):
        team = self.get_object()
        serializer = MembershipChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        if request.method == "POST":
            _, changed = Membership.objects.get_or_create(user=user, team=team)
            change, status_code = (
                "added",
                status.HTTP_201_CREATED if changed else status.HTTP_200_OK,
            )
        else:
            deleted, _ = Membership.objects.filter(user=user, team=team).delete()
            changed = bool(deleted)
            change, status_code = "removed", status.HTTP_200_OK

        if changed:
            audit.record(
                request,
                AuditLog.Action.MEMBERSHIP_CHANGE,
                target_type="team",
                target_id=team.pk,
                metadata={
                    "team": team.name,
                    "user_id": user.pk,
                    "user": user.email,
                    "change": change,
                },
            )

        team = Team.objects.prefetch_related("members").get(pk=team.pk)
        return Response(TeamSerializer(team).data, status=status_code)
