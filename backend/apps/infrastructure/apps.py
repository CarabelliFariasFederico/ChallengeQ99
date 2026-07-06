import logging

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger("apps.infrastructure")


class InfrastructureConfig(AppConfig):
    name = "apps.infrastructure"
    label = "infrastructure"

    def ready(self):
        from apps.infrastructure import checks
        from apps.infrastructure.crypto.secret_box import CryptoConfigError, SecretBox

        provider = getattr(settings, "DRIVE_GATEWAY_PROVIDER", "")
        try:
            SecretBox.from_settings()
            crypto_configured = True
        except CryptoConfigError:
            crypto_configured = False

        logger.info(
            "startup: drive_gateway=%s crypto_configured=%s debug=%s",
            f"fake({provider})" if provider else "real(google)",
            crypto_configured,
            settings.DEBUG,
        )
