from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.domain.models import (
    DriveCredential,
    GroupDrivePermission,
    Membership,
    Team,
    User,
)
from apps.infrastructure.crypto.secret_box import CryptoConfigError

DEMO_PASSWORD = "demo12345"

USERS = (
    ("admin@demo.local", User.Role.ADMIN),
    ("editor@demo.local", User.Role.MEMBER),
    ("analyst@demo.local", User.Role.MEMBER),
    ("provider@demo.local", User.Role.MEMBER),
)


MATRIX = {
    "Editores": (
        "editor@demo.local",
        {"can_view": True, "can_download": True, "can_upload": True},
    ),
    "Analistas": (
        "analyst@demo.local",
        {"can_view": True, "can_download": True, "can_upload": False},
    ),
    "Proveedores": (
        "provider@demo.local",
        {"can_view": False, "can_download": False, "can_upload": True},
    ),
}

CREDENTIAL_LABEL = "Demo Drive (OAuth)"


class Command(BaseCommand):
    help = "Seed idempotent demo data (users/teams/credential/permissions). Local demo only."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even with DEBUG=False.")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stdout.write("seed_demo skipped (DEBUG=False; use --force to override).")
            return

        users = {}
        for email, role in USERS:
            user, created = User.objects.get_or_create(email=email, defaults={"role": role})
            if created:
                user.set_password(DEMO_PASSWORD)
                if role == User.Role.ADMIN:
                    user.is_staff = True
                    user.is_superuser = True
                user.save()
            users[email] = user

        credential, created = DriveCredential.objects.get_or_create(
            account_label=CREDENTIAL_LABEL,
            defaults={"auth_method": DriveCredential.AuthMethod.OAUTH},
        )
        if created or not bytes(credential.secret_ciphertext):
            try:
                credential.set_secret("demo-refresh-token-NOT-REAL")
                credential.save(update_fields=["secret_ciphertext", "key_version", "updated_at"])
            except CryptoConfigError:
                self.stdout.write(
                    self.style.WARNING(
                        "No Fernet key configured: demo credential stored without a "
                        "secret (fine while the fake gateway is in use)."
                    )
                )

        if not DriveCredential.objects.filter(is_active=True).exists():
            credential.is_active = True
            credential.save(update_fields=["is_active", "updated_at"])

        for team_name, (email, flags) in MATRIX.items():
            team, _ = Team.objects.get_or_create(name=team_name)
            Membership.objects.get_or_create(user=users[email], team=team)
            GroupDrivePermission.objects.update_or_create(
                team=team, credential=credential, defaults=flags
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready: {len(USERS)} users (password '{DEMO_PASSWORD}'), "
                f"{len(MATRIX)} teams and the '{CREDENTIAL_LABEL}' credential."
            )
        )
