from urllib.parse import parse_qs, urlparse

import pytest

from apps.domain.models import AuditLog, DriveCredential, OAuthState
from apps.infrastructure.drive import oauth_flow
from apps.infrastructure.drive.gateway import DriveAuthError

pytestmark = pytest.mark.django_db

REFRESH_TOKEN = "RT-SUPER-SECRET-refresh-token"


@pytest.fixture(autouse=True)
def oauth_settings(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "client-id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "client-secret-value"
    settings.GOOGLE_OAUTH_REDIRECT_URI = (
        "http://localhost:8000/api/admin/credentials/oauth/callback"
    )


def initiate(api_client, admin_user, label="Marketing Drive"):
    api_client.force_authenticate(admin_user)
    response = api_client.post(
        "/api/admin/credentials/oauth/initiate", {"account_label": label}, format="json"
    )
    api_client.force_authenticate(None)
    return response


def mock_exchange(monkeypatch, tokens):
    calls = []

    def _fake_exchange(code):
        calls.append(code)
        return dict(tokens)

    monkeypatch.setattr(oauth_flow, "exchange_code", _fake_exchange)
    return calls


class TestInitiate:
    def test_requires_admin(self, api_client, member):
        api_client.force_authenticate(member)
        response = api_client.post("/api/admin/credentials/oauth/initiate", {}, format="json")
        assert response.status_code == 403

    def test_returns_consent_url_with_state_and_forced_consent(self, api_client, admin_user):
        response = initiate(api_client, admin_user)
        assert response.status_code == 200

        url = urlparse(response.data["authorization_url"])
        params = parse_qs(url.query)
        assert url.hostname == "accounts.google.com"
        assert params["access_type"] == ["offline"]
        assert params["prompt"] == ["consent"]
        assert params["client_id"] == ["client-id"]

        stored = OAuthState.objects.get()
        assert params["state"] == [stored.state]
        assert stored.initiated_by == admin_user
        assert stored.account_label == "Marketing Drive"
        assert AuditLog.objects.filter(action=AuditLog.Action.CREDENTIAL_OAUTH_INITIATE).exists()

    def test_client_secret_never_in_response(self, api_client, admin_user):
        response = initiate(api_client, admin_user)
        assert "client-secret-value" not in str(response.data)

    def test_missing_config_is_a_clear_503(self, api_client, admin_user, settings):
        settings.GOOGLE_OAUTH_CLIENT_ID = ""
        response = initiate(api_client, admin_user)
        assert response.status_code == 503
        assert response.data["code"] == "oauth_not_configured"
        assert OAuthState.objects.count() == 0


class TestCallback:
    def test_happy_path_encrypts_and_redirects(
        self, api_client, admin_user, monkeypatch, settings
    ):
        initiate(api_client, admin_user)
        state = OAuthState.objects.get().state
        mock_exchange(monkeypatch, {"refresh_token": REFRESH_TOKEN, "access_token": "AT"})

        response = api_client.get(
            f"/api/admin/credentials/oauth/callback?code=the-code&state={state}"
        )
        assert response.status_code == 302
        assert response["Location"].startswith(f"{settings.FRONTEND_URL}/admin?drive_connected=1")
        assert REFRESH_TOKEN not in response["Location"]

        credential = DriveCredential.objects.get()
        assert credential.auth_method == DriveCredential.AuthMethod.OAUTH
        assert credential.is_active is False
        stored = bytes(credential.secret_ciphertext)
        assert stored and REFRESH_TOKEN.encode() not in stored
        assert credential.get_secret() == REFRESH_TOKEN.encode()

        log = AuditLog.objects.get(action=AuditLog.Action.CREDENTIAL_CREATE)
        assert log.actor == admin_user
        assert log.metadata["via"] == "oauth"
        assert REFRESH_TOKEN not in str(log.metadata)

    def test_invalid_state_is_400_and_never_exchanges(self, api_client, monkeypatch):
        calls = mock_exchange(monkeypatch, {"refresh_token": REFRESH_TOKEN})
        response = api_client.get(
            "/api/admin/credentials/oauth/callback?code=the-code&state=forged"
        )
        assert response.status_code == 400
        assert response.data["code"] == "invalid_oauth_state"
        assert calls == []
        assert DriveCredential.objects.count() == 0

    def test_expired_state_is_400_and_consumed(self, api_client, admin_user, monkeypatch):
        initiate(api_client, admin_user)
        OAuthState.objects.update(expires_at=OAuthState.objects.get().created_at)
        state = OAuthState.objects.get().state
        calls = mock_exchange(monkeypatch, {"refresh_token": REFRESH_TOKEN})

        response = api_client.get(f"/api/admin/credentials/oauth/callback?code=c&state={state}")
        assert response.status_code == 400
        assert calls == []
        assert OAuthState.objects.count() == 0

    def test_state_is_single_use(self, api_client, admin_user, monkeypatch):
        initiate(api_client, admin_user)
        state = OAuthState.objects.get().state
        mock_exchange(monkeypatch, {"refresh_token": REFRESH_TOKEN})

        first = api_client.get(f"/api/admin/credentials/oauth/callback?code=c&state={state}")
        replay = api_client.get(f"/api/admin/credentials/oauth/callback?code=c&state={state}")
        assert first.status_code == 302
        assert replay.status_code == 400
        assert replay.data["code"] == "invalid_oauth_state"
        assert DriveCredential.objects.count() == 1

    def test_missing_refresh_token_is_actionable_400(self, api_client, admin_user, monkeypatch):
        initiate(api_client, admin_user)
        state = OAuthState.objects.get().state
        mock_exchange(monkeypatch, {"access_token": "AT-only"})

        response = api_client.get(f"/api/admin/credentials/oauth/callback?code=c&state={state}")
        assert response.status_code == 400
        assert response.data["code"] == "refresh_token_missing"
        assert "consent" in response.data["message"]
        assert DriveCredential.objects.count() == 0

    def test_user_denied_consent_is_400_without_credential(
        self, api_client, admin_user, monkeypatch
    ):
        initiate(api_client, admin_user)
        state = OAuthState.objects.get().state
        calls = mock_exchange(monkeypatch, {"refresh_token": REFRESH_TOKEN})

        response = api_client.get(
            f"/api/admin/credentials/oauth/callback?error=access_denied&state={state}"
        )
        assert response.status_code == 400
        assert calls == []
        assert DriveCredential.objects.count() == 0
        assert OAuthState.objects.count() == 0


class TestRotation:
    def test_full_connect_then_activate_flow(
        self, api_client, admin_user, member, grant, monkeypatch
    ):
        DriveCredential.objects.create(
            account_label="Old", auth_method=DriveCredential.AuthMethod.OAUTH, is_active=True
        )

        initiate(api_client, admin_user, label="New Drive")
        state = OAuthState.objects.get().state
        mock_exchange(monkeypatch, {"refresh_token": REFRESH_TOKEN})
        api_client.get(f"/api/admin/credentials/oauth/callback?code=c&state={state}")
        new = DriveCredential.objects.get(account_label="New Drive")

        api_client.force_authenticate(admin_user)
        response = api_client.post(f"/api/admin/credentials/{new.pk}/activate")
        assert response.status_code == 200
        actives = list(DriveCredential.objects.filter(is_active=True))
        assert [c.pk for c in actives] == [new.pk]
        assert AuditLog.objects.filter(action=AuditLog.Action.CREDENTIAL_ACTIVATE).exists()

        grant(member, new, view=True)
        api_client.force_authenticate(member)
        assert api_client.get("/api/files").status_code == 200

    def test_revoked_refresh_token_maps_to_actionable_502(
        self, api_client, member, active_credential, grant, settings
    ):
        grant(member, active_credential, view=True)
        settings.DRIVE_GATEWAY_PROVIDER = "apps.api.tests.test_oauth.revoked_gateway_provider"
        api_client.force_authenticate(member)

        response = api_client.get("/api/files")
        assert response.status_code == 502
        assert response.data["code"] == "drive_auth_failed"
        assert "reconnect" in response.data["message"]

        assert "invalid_grant" not in response.data["message"]


class _RevokedGateway:
    def list_files(self, **kwargs):
        raise DriveAuthError("invalid_grant: Token has been expired or revoked.")

    def get_metadata(self, file_id):
        raise DriveAuthError("invalid_grant: Token has been expired or revoked.")

    def download(self, file_id):
        raise DriveAuthError("invalid_grant: Token has been expired or revoked.")

    def upload(self, *args, **kwargs):
        raise DriveAuthError("invalid_grant: Token has been expired or revoked.")


def revoked_gateway_provider():
    return _RevokedGateway()
