from abc import ABC, abstractmethod

from apps.infrastructure.drive.gateway import DriveAuthError

SCOPES = ["https://www.googleapis.com/auth/drive"]

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


class DriveAuthStrategy(ABC):
    @abstractmethod
    def build_credentials(self):
        pass


class OAuthStrategy(DriveAuthStrategy):
    def __init__(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        token_uri: str = GOOGLE_TOKEN_URI,
    ):
        if not refresh_token:
            raise DriveAuthError("OAuth strategy needs a non-empty refresh token.")
        if not client_id or not client_secret:
            raise DriveAuthError(
                "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET are not configured."
            )
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_uri = token_uri

    def build_credentials(self):
        from google.oauth2.credentials import Credentials

        return Credentials(
            token=None,
            refresh_token=self._refresh_token,
            token_uri=self._token_uri,
            client_id=self._client_id,
            client_secret=self._client_secret,
            scopes=SCOPES,
        )


class ServiceAccountStrategy(DriveAuthStrategy):
    def __init__(self, service_account_info: dict):
        if not isinstance(service_account_info, dict):
            raise DriveAuthError("Service account strategy needs the parsed JSON dict.")
        self._info = service_account_info

    def build_credentials(self):
        from google.oauth2 import service_account

        try:
            return service_account.Credentials.from_service_account_info(self._info, scopes=SCOPES)
        except (ValueError, KeyError) as exc:
            raise DriveAuthError(f"Invalid service account JSON: {exc}") from exc
