import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command

from apps.domain.models import (
    DriveCredential,
    GroupDrivePermission,
    Membership,
    Team,
    User,
)
from apps.domain.policies import Action, PermissionPolicy

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _crypto(settings):
    settings.FERNET_KEY = ""
    settings.FERNET_KEYS = f"1:{Fernet.generate_key().decode()}"


def seed():
    call_command("seed_demo", "--force", verbosity=0)


def counts():
    return (
        User.objects.count(),
        Team.objects.count(),
        Membership.objects.count(),
        DriveCredential.objects.count(),
        GroupDrivePermission.objects.count(),
    )


class TestSeedDemo:
    def test_skips_quietly_when_not_debug_and_not_forced(self):
        call_command("seed_demo", verbosity=0)
        assert User.objects.count() == 0

    def test_creates_the_documented_world(self):
        seed()
        assert counts() == (4, 3, 3, 1, 3)

        credential = DriveCredential.objects.get()
        assert credential.is_active is True
        assert credential.auth_method == DriveCredential.AuthMethod.OAUTH
        assert bytes(credential.secret_ciphertext)
        assert b"demo-refresh-token" not in bytes(credential.secret_ciphertext)

        admin = User.objects.get(email="admin@demo.local")
        assert admin.is_administrator and admin.is_staff and admin.is_superuser

        provider = User.objects.get(email="provider@demo.local")
        assert PermissionPolicy.allowed_actions(provider, credential) == {Action.UPLOAD}
        analyst = User.objects.get(email="analyst@demo.local")
        assert PermissionPolicy.allowed_actions(analyst, credential) == {
            Action.VIEW,
            Action.DOWNLOAD,
        }
        editor = User.objects.get(email="editor@demo.local")
        assert PermissionPolicy.allowed_actions(editor, credential) == {
            Action.VIEW,
            Action.DOWNLOAD,
            Action.UPLOAD,
        }

    def test_running_twice_changes_nothing(self):
        seed()
        first = counts()
        seed()
        assert counts() == first

    def test_does_not_steal_the_active_slot(self):
        other = DriveCredential.objects.create(
            account_label="Real one",
            auth_method=DriveCredential.AuthMethod.OAUTH,
            is_active=True,
        )
        seed()
        assert DriveCredential.objects.get(is_active=True) == other
