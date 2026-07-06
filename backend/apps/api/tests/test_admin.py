import pytest

from apps.domain.models import (
    AuditLog,
    DriveCredential,
    GroupDrivePermission,
    Membership,
    Team,
)

pytestmark = pytest.mark.django_db

SERVICE_ACCOUNT_JSON = {
    "type": "service_account",
    "project_id": "p",
    "client_email": "svc@p.iam.gserviceaccount.com",
    "private_key": "-----BEGIN PRIVATE KEY-----\nSECRET-KEY-MATERIAL\n-----END PRIVATE KEY-----\n",
}


class TestMemberIsLockedOut:
    @pytest.mark.parametrize(
        "method,url,body",
        [
            ("get", "/api/admin/teams", None),
            ("post", "/api/admin/teams", {"name": "X"}),
            ("get", "/api/admin/users", None),
            ("get", "/api/admin/credentials", None),
            (
                "post",
                "/api/admin/credentials",
                {"account_label": "X", "secret": SERVICE_ACCOUNT_JSON},
            ),
        ],
        ids=["list-teams", "create-team", "list-users", "list-credentials", "create-credential"],
    )
    def test_member_gets_403_on_admin_routes(self, api_client, member, method, url, body):
        api_client.force_authenticate(member)
        response = getattr(api_client, method)(url, body, format="json")
        assert response.status_code == 403
        assert response.data["code"] == "permission_denied"

    def test_member_gets_403_on_admin_detail_routes(self, api_client, member):
        team = Team.objects.create(name="T")
        credential = DriveCredential.objects.create(
            account_label="C", auth_method=DriveCredential.AuthMethod.SERVICE_ACCOUNT
        )
        api_client.force_authenticate(member)
        calls = [
            api_client.patch(f"/api/admin/teams/{team.pk}", {"name": "Z"}, format="json"),
            api_client.delete(f"/api/admin/teams/{team.pk}"),
            api_client.post(
                f"/api/admin/teams/{team.pk}/members", {"user_id": member.pk}, format="json"
            ),
            api_client.post(f"/api/admin/credentials/{credential.pk}/activate"),
            api_client.put(
                f"/api/admin/credentials/{credential.pk}/permissions",
                {"permissions": []},
                format="json",
            ),
        ]
        assert all(r.status_code == 403 for r in calls)

    def test_403_writes_denied_audit_and_leaves_no_side_effects(self, api_client, member):
        api_client.force_authenticate(member)
        response = api_client.post("/api/admin/teams", {"name": "Sneaky"}, format="json")
        assert response.status_code == 403

        assert Team.objects.count() == 0

        log = AuditLog.objects.get(action=AuditLog.Action.ACCESS_DENIED)
        assert log.actor == member
        assert log.target_id == "/api/admin/teams"
        assert log.metadata["method"] == "POST"


class TestTeamsAndMembers:
    def test_team_crud(self, api_client, admin_user):
        api_client.force_authenticate(admin_user)
        created = api_client.post(
            "/api/admin/teams", {"name": "Marketing", "description": "d"}, format="json"
        )
        assert created.status_code == 201
        team_id = created.data["id"]

        assert any(t["name"] == "Marketing" for t in api_client.get("/api/admin/teams").data)
        renamed = api_client.patch(f"/api/admin/teams/{team_id}", {"name": "Mkt"}, format="json")
        assert renamed.status_code == 200 and renamed.data["name"] == "Mkt"
        assert api_client.delete(f"/api/admin/teams/{team_id}").status_code == 204

    def test_team_lifecycle_is_audited(self, api_client, admin_user, member, active_credential):
        api_client.force_authenticate(admin_user)
        created = api_client.post("/api/admin/teams", {"name": "Audited"}, format="json")
        team_id = created.data["id"]
        api_client.patch(f"/api/admin/teams/{team_id}", {"name": "Renamed"}, format="json")

        team = Team.objects.get(pk=team_id)
        Membership.objects.create(user=member, team=team)
        GroupDrivePermission.objects.create(
            team=team, credential=active_credential, can_download=True
        )
        api_client.delete(f"/api/admin/teams/{team_id}")

        changes = list(AuditLog.objects.filter(action=AuditLog.Action.TEAM_CHANGE).order_by("pk"))
        assert [c.metadata["change"] for c in changes] == ["created", "updated", "deleted"]
        deleted = changes[-1].metadata
        assert deleted["cascaded"]["members"] == [member.email]
        assert deleted["cascaded"]["grants"][str(active_credential.pk)]["can_download"] is True

    def test_add_and_remove_member_with_audit(self, api_client, admin_user, member):
        api_client.force_authenticate(admin_user)
        team = Team.objects.create(name="Ops")

        added = api_client.post(
            f"/api/admin/teams/{team.pk}/members", {"user_id": member.pk}, format="json"
        )
        assert added.status_code == 201
        assert Membership.objects.filter(user=member, team=team).exists()
        assert any(u["email"] == member.email for u in added.data["members"])

        removed = api_client.delete(
            f"/api/admin/teams/{team.pk}/members", {"user_id": member.pk}, format="json"
        )
        assert removed.status_code == 200
        assert not Membership.objects.filter(user=member, team=team).exists()

        changes = AuditLog.objects.filter(action=AuditLog.Action.MEMBERSHIP_CHANGE)
        assert [c.metadata["change"] for c in changes.order_by("pk")] == ["added", "removed"]

    def test_users_listing(self, api_client, admin_user, member):
        api_client.force_authenticate(admin_user)
        response = api_client.get("/api/admin/users")
        assert response.status_code == 200
        emails = [u["email"] for u in response.data]
        assert member.email in emails and admin_user.email in emails


class TestCredentials:
    def test_create_encrypts_and_never_returns_the_secret(self, api_client, admin_user):
        api_client.force_authenticate(admin_user)
        response = api_client.post(
            "/api/admin/credentials",
            {"account_label": "SA Drive", "secret": SERVICE_ACCOUNT_JSON},
            format="json",
        )
        assert response.status_code == 201
        assert "secret" not in response.data
        assert "secret_ciphertext" not in response.data

        credential = DriveCredential.objects.get(pk=response.data["id"])
        stored = bytes(credential.secret_ciphertext)
        assert stored
        assert b"SECRET-KEY-MATERIAL" not in stored
        assert credential.auth_method == DriveCredential.AuthMethod.SERVICE_ACCOUNT

        listing = api_client.get("/api/admin/credentials")
        assert all(
            "secret" not in item and "secret_ciphertext" not in item for item in listing.data
        )

        log = AuditLog.objects.get(action=AuditLog.Action.CREDENTIAL_CREATE)
        assert log.actor == admin_user
        assert log.metadata["account_label"] == "SA Drive"
        assert "SECRET-KEY-MATERIAL" not in str(log.metadata)

    def test_create_without_fernet_key_is_actionable_503(self, api_client, admin_user, settings):
        settings.FERNET_KEY = ""
        settings.FERNET_KEYS = ""
        api_client.force_authenticate(admin_user)
        response = api_client.post(
            "/api/admin/credentials",
            {"account_label": "X", "secret": SERVICE_ACCOUNT_JSON},
            format="json",
        )
        assert response.status_code == 503
        assert response.data["code"] == "credential_encryption_not_configured"
        assert "generate_fernet_key" in response.data["message"]
        assert DriveCredential.objects.count() == 0

    def test_activate_is_a_unit_of_work(self, api_client, admin_user, active_credential):
        api_client.force_authenticate(admin_user)
        other = DriveCredential.objects.create(
            account_label="Second", auth_method=DriveCredential.AuthMethod.SERVICE_ACCOUNT
        )
        response = api_client.post(f"/api/admin/credentials/{other.pk}/activate")
        assert response.status_code == 200
        assert response.data["is_active"] is True

        actives = DriveCredential.objects.filter(is_active=True)
        assert list(actives.values_list("pk", flat=True)) == [other.pk]
        other.refresh_from_db()
        assert other.rotated_by == admin_user and other.rotated_at is not None

        log = AuditLog.objects.get(action=AuditLog.Action.CREDENTIAL_ACTIVATE)
        assert log.actor == admin_user
        assert log.metadata["previous_active_id"] == active_credential.pk

    def test_permissions_get_returns_current_matrix(
        self, api_client, admin_user, active_credential
    ):
        api_client.force_authenticate(admin_user)
        team = Team.objects.create(name="Ops")
        GroupDrivePermission.objects.create(
            team=team, credential=active_credential, can_view=True, can_upload=True
        )
        response = api_client.get(f"/api/admin/credentials/{active_credential.pk}/permissions")
        assert response.status_code == 200
        assert response.data["permissions"] == {
            str(team.pk): {"can_view": True, "can_download": False, "can_upload": True}
        }

    def test_permissions_get_requires_admin(self, api_client, member, active_credential):
        api_client.force_authenticate(member)
        response = api_client.get(f"/api/admin/credentials/{active_credential.pk}/permissions")
        assert response.status_code == 403

    def test_permissions_put_replaces_matrix_and_audits_diff(
        self, api_client, admin_user, active_credential
    ):
        api_client.force_authenticate(admin_user)
        team_old = Team.objects.create(name="Old")
        team_new = Team.objects.create(name="New")
        GroupDrivePermission.objects.create(
            team=team_old, credential=active_credential, can_view=True
        )

        response = api_client.put(
            f"/api/admin/credentials/{active_credential.pk}/permissions",
            {"permissions": [{"team_id": team_new.pk, "can_view": True, "can_upload": True}]},
            format="json",
        )
        assert response.status_code == 200

        rows = GroupDrivePermission.objects.filter(credential=active_credential)
        assert rows.count() == 1
        row = rows.get()
        assert (row.team, row.can_view, row.can_download, row.can_upload) == (
            team_new,
            True,
            False,
            True,
        )

        log = AuditLog.objects.get(action=AuditLog.Action.PERMISSION_UPDATE)
        assert str(team_old.pk) in log.metadata["before"]
        assert str(team_new.pk) in log.metadata["after"]
