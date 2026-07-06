import json

from django.conf import settings
from django.utils.module_loading import import_string

from apps.domain.models import DriveCredential
from apps.infrastructure.drive.gateway import DriveAuthError, DriveError, DriveGateway
from apps.infrastructure.drive.google import GoogleDriveGateway
from apps.infrastructure.drive.strategies import (
    DriveAuthStrategy,
    OAuthStrategy,
    ServiceAccountStrategy,
)


class NoActiveCredentialError(DriveError):
    pass


class DriveClientFactory:
    @staticmethod
    def strategy_for(credential: DriveCredential) -> DriveAuthStrategy:
        secret = credential.get_secret()
        if credential.auth_method == DriveCredential.AuthMethod.OAUTH:
            return OAuthStrategy(
                refresh_token=secret.decode(),
                client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
                client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            )
        if credential.auth_method == DriveCredential.AuthMethod.SERVICE_ACCOUNT:
            try:
                info = json.loads(secret)
            except ValueError as exc:
                raise DriveAuthError("Stored service account secret is not valid JSON.") from exc
            return ServiceAccountStrategy(info)
        raise DriveError(f"Unsupported auth method: {credential.auth_method!r}.")

    @classmethod
    def build(cls) -> DriveGateway:
        provider_path = getattr(settings, "DRIVE_GATEWAY_PROVIDER", "")
        if provider_path:
            provider = import_string(provider_path)
            return provider()
        credential = DriveCredential.objects.filter(is_active=True).first()
        if credential is None:
            raise NoActiveCredentialError(
                "No active Drive credential. Activate one before using Drive."
            )
        return GoogleDriveGateway(cls.strategy_for(credential))
