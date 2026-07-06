from django.core.checks import Tags, Warning, register

from apps.infrastructure.crypto.secret_box import CryptoConfigError, SecretBox


@register(Tags.security)
def fernet_key_check(app_configs, **kwargs):
    try:
        SecretBox.from_settings()
    except CryptoConfigError as exc:
        return [
            Warning(
                f"Credential encryption is not usable: {exc}",
                hint="python manage.py generate_fernet_key  ->  FERNET_KEY in .env",
                id="infrastructure.W001",
            )
        ]
    return []
