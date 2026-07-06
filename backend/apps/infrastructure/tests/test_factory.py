import json

import pytest
from cryptography.fernet import Fernet

from apps.domain.models import DriveCredential
from apps.infrastructure.drive.factory import DriveClientFactory, NoActiveCredentialError
from apps.infrastructure.drive.fake import FakeDriveGateway, reset_default_fake_gateway
from apps.infrastructure.drive.google import GoogleDriveGateway
from apps.infrastructure.drive.strategies import OAuthStrategy, ServiceAccountStrategy

pytestmark = pytest.mark.django_db

KEY = Fernet.generate_key().decode()

SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "test-project",
    "client_email": "svc@test-project.iam.gserviceaccount.com",
    "private_key": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n",
}


@pytest.fixture(autouse=True)
def _settings(settings):
    settings.FERNET_KEY = ""
    settings.FERNET_KEYS = f"1:{KEY}"
    settings.GOOGLE_OAUTH_CLIENT_ID = "test-client-id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "test-client-secret"
    settings.DRIVE_GATEWAY_PROVIDER = ""


def make_active_credential(auth_method, secret):
    credential = DriveCredential.objects.create(
        account_label="Test Drive",
        auth_method=auth_method,
        is_active=True,
    )
    credential.set_secret(secret)
    credential.save()
    return credential


class TestStrategySelection:
    def test_oauth_credential_selects_oauth_strategy(self):
        credential = make_active_credential(DriveCredential.AuthMethod.OAUTH, "refresh-token-xyz")
        strategy = DriveClientFactory.strategy_for(credential)
        assert isinstance(strategy, OAuthStrategy)
        gateway = DriveClientFactory.build()
        assert isinstance(gateway, GoogleDriveGateway)

    def test_service_account_credential_selects_sa_strategy(self):
        credential = make_active_credential(
            DriveCredential.AuthMethod.SERVICE_ACCOUNT,
            json.dumps(SERVICE_ACCOUNT_INFO),
        )
        strategy = DriveClientFactory.strategy_for(credential)
        assert isinstance(strategy, ServiceAccountStrategy)
        assert isinstance(DriveClientFactory.build(), GoogleDriveGateway)


class TestNoActiveCredential:
    def test_build_without_active_credential_raises_typed_error(self):
        inactive = DriveCredential.objects.create(
            account_label="Dormant",
            auth_method=DriveCredential.AuthMethod.OAUTH,
            is_active=False,
        )
        inactive.set_secret("s")
        inactive.save()
        with pytest.raises(NoActiveCredentialError):
            DriveClientFactory.build()


class TestFakeInjection:
    def test_provider_swap_returns_the_fake_gateway(self, settings):
        reset_default_fake_gateway()
        settings.DRIVE_GATEWAY_PROVIDER = "apps.infrastructure.drive.fake.default_fake_gateway"
        gateway = DriveClientFactory.build()
        assert isinstance(gateway, FakeDriveGateway)

        assert DriveClientFactory.build() is gateway
