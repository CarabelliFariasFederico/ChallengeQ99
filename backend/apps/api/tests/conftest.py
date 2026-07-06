import pytest
from cryptography.fernet import Fernet
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.domain.models import DriveCredential, Team, User
from apps.domain.tests import factories
from apps.infrastructure.drive.fake import reset_default_fake_gateway

FERNET_TEST_KEY = Fernet.generate_key().decode()

PASSWORD = "test-password-123"


@pytest.fixture(autouse=True)
def api_env(settings):
    settings.DRIVE_GATEWAY_PROVIDER = "apps.infrastructure.drive.fake.default_fake_gateway"
    settings.DRIVE_FAKE_SEED_FILES = False
    settings.FERNET_KEY = ""
    settings.FERNET_KEYS = f"1:{FERNET_TEST_KEY}"
    reset_default_fake_gateway()
    cache.clear()
    yield
    reset_default_fake_gateway()
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return factories.make_user("admin@example.com", role=User.Role.ADMIN, password=PASSWORD)


@pytest.fixture
def member(db):
    return factories.make_user("member@example.com", password=PASSWORD)


@pytest.fixture
def active_credential(db):
    return factories.make_credential(
        auth_method=DriveCredential.AuthMethod.SERVICE_ACCOUNT, active=True
    )


@pytest.fixture
def grant(db):
    def _grant(user, credential, *, view=False, download=False, upload=False):
        team = factories.make_team(f"team-{user.pk}-{Team.objects.count()}")
        factories.join(user, team)
        factories.grant(team, credential, view=view, download=download, upload=upload)
        return team

    return _grant
