import json

from rest_framework import serializers

from apps.domain.models import DriveCredential, Team, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "role"]
        read_only_fields = fields


class TeamSerializer(serializers.ModelSerializer):
    members = UserSerializer(many=True, read_only=True)

    class Meta:
        model = Team
        fields = ["id", "name", "description", "members"]


class MembershipChangeSerializer(serializers.Serializer):
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source="user")


class DriveCredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriveCredential
        fields = [
            "id",
            "account_label",
            "auth_method",
            "is_active",
            "key_version",
            "rotated_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ServiceAccountCredentialCreateSerializer(serializers.Serializer):
    account_label = serializers.CharField(max_length=255)
    secret = serializers.JSONField(write_only=True)

    def validate_secret(self, value):
        if not isinstance(value, dict) or value.get("type") != "service_account":
            raise serializers.ValidationError(
                "Expected a service account JSON object with type='service_account'."
            )
        return value

    def create(self, validated_data):
        credential = DriveCredential(
            account_label=validated_data["account_label"],
            auth_method=DriveCredential.AuthMethod.SERVICE_ACCOUNT,
        )
        credential.set_secret(json.dumps(validated_data["secret"]))
        credential.save()
        return credential


class PermissionRowSerializer(serializers.Serializer):
    team_id = serializers.PrimaryKeyRelatedField(queryset=Team.objects.all(), source="team")
    can_view = serializers.BooleanField(default=False)
    can_download = serializers.BooleanField(default=False)
    can_upload = serializers.BooleanField(default=False)


class PermissionMatrixSerializer(serializers.Serializer):
    permissions = PermissionRowSerializer(many=True)

    def validate_permissions(self, rows):
        team_ids = [row["team"].pk for row in rows]
        if len(team_ids) != len(set(team_ids)):
            raise serializers.ValidationError("Duplicate team in permission matrix.")
        return rows
