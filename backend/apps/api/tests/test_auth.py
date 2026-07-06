import pytest

from apps.api.tests.conftest import PASSWORD
from apps.domain.models import AuditLog

pytestmark = pytest.mark.django_db


class TestLogin:
    def test_login_returns_token_pair(self, api_client, member):
        response = api_client.post(
            "/api/auth/login", {"email": member.email, "password": PASSWORD}
        )
        assert response.status_code == 200
        assert "access" in response.data and "refresh" in response.data

    def test_login_wrong_password_is_401_with_envelope(self, api_client, member):
        response = api_client.post("/api/auth/login", {"email": member.email, "password": "wrong"})
        assert response.status_code == 401
        assert response.data["code"] == "no_active_account"
        assert "request_id" in response.data

    def test_successful_login_is_audited_with_ip(self, api_client, member):
        api_client.post("/api/auth/login", {"email": member.email, "password": PASSWORD})
        log = AuditLog.objects.get(action=AuditLog.Action.LOGIN)
        assert log.actor == member
        assert log.ip is not None

    def test_failed_login_is_audited_as_login_failed(self, api_client, member):
        api_client.post("/api/auth/login", {"email": member.email, "password": "wrong"})
        assert not AuditLog.objects.filter(action=AuditLog.Action.LOGIN).exists()
        failed = AuditLog.objects.get(action=AuditLog.Action.LOGIN_FAILED)
        assert failed.actor is None
        assert failed.metadata["email"] == member.email
        assert "password" not in failed.metadata

    def test_login_is_throttled(self, api_client, member, settings):
        for _ in range(10):
            api_client.post("/api/auth/login", {"email": member.email, "password": "wrong"})
        response = api_client.post("/api/auth/login", {"email": member.email, "password": "wrong"})
        assert response.status_code == 429
        assert response.data["code"] == "throttled"
        assert response.has_header("Retry-After")

    def test_audit_ip_ignores_forged_x_forwarded_for(self, api_client, member):
        from apps.api.tests.conftest import PASSWORD as pw

        api_client.post(
            "/api/auth/login",
            {"email": member.email, "password": pw},
            HTTP_X_FORWARDED_FOR="6.6.6.6",
        )
        log = AuditLog.objects.get(action=AuditLog.Action.LOGIN)
        assert log.ip == "127.0.0.1"

    def test_refresh_rotates_tokens(self, api_client, member):
        login = api_client.post("/api/auth/login", {"email": member.email, "password": PASSWORD})
        refresh = login.data["refresh"]
        response = api_client.post("/api/auth/refresh", {"refresh": refresh})
        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["refresh"] != refresh

        replay = api_client.post("/api/auth/refresh", {"refresh": refresh})
        assert replay.status_code == 401


class TestMe:
    def test_requires_authentication(self, api_client):
        assert api_client.get("/api/me").status_code == 401

    def test_profile_and_capabilities_for_viewer(
        self, api_client, member, active_credential, grant
    ):
        grant(member, active_credential, view=True)
        api_client.force_authenticate(member)
        response = api_client.get("/api/me")
        assert response.status_code == 200
        assert response.data["email"] == member.email
        assert response.data["role"] == "member"
        assert response.data["capabilities"] == {
            "can_view": True,
            "can_download": False,
            "can_upload": False,
        }

    def test_admin_without_grants_has_no_capabilities(
        self, api_client, admin_user, active_credential
    ):
        api_client.force_authenticate(admin_user)
        response = api_client.get("/api/me")
        assert response.data["role"] == "admin"
        assert response.data["capabilities"] == {
            "can_view": False,
            "can_download": False,
            "can_upload": False,
        }

    def test_no_active_credential_means_no_capabilities(self, api_client, member):
        api_client.force_authenticate(member)
        response = api_client.get("/api/me")
        assert response.status_code == 200
        assert response.data["capabilities"] == {
            "can_view": False,
            "can_download": False,
            "can_upload": False,
        }
        assert response.data["active_credential"] == {
            "present": False,
            "account_label": None,
        }

    def test_me_reports_the_active_credential(self, api_client, member, active_credential):
        api_client.force_authenticate(member)
        response = api_client.get("/api/me")
        assert response.data["active_credential"] == {
            "present": True,
            "account_label": active_credential.account_label,
        }
        assert response.data["drive_gateway"] == "fake"
