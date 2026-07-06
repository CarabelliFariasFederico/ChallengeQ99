from django.core.management.base import BaseCommand

from apps.infrastructure.crypto.secret_box import generate_key


class Command(BaseCommand):
    help = (
        "Generate a valid Fernet key for credential encryption. "
        "Put the output in .env as FERNET_KEY=<key> (or append it to the "
        "FERNET_KEYS rotation map as '<next-version>:<key>')."
    )

    def handle(self, *args, **options):
        self.stdout.write(generate_key())
