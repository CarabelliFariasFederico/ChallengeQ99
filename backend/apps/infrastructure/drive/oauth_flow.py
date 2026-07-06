from urllib.parse import urlencode

import requests
from django.conf import settings

from apps.infrastructure.drive.gateway import DriveError
from apps.infrastructure.drive.strategies import GOOGLE_TOKEN_URI, SCOPES

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_EXCHANGE_TIMEOUT_SECONDS = 15


class OAuthConfigError(DriveError):
    pass


class OAuthExchangeError(DriveError):
    pass


class OAuthMissingRefreshToken(DriveError):
    pass


class InvalidOAuthState(DriveError):
    pass


def _require_config():
    if not (
        settings.GOOGLE_OAUTH_CLIENT_ID
        and settings.GOOGLE_OAUTH_CLIENT_SECRET
        and settings.GOOGLE_OAUTH_REDIRECT_URI
    ):
        raise OAuthConfigError(
            "Google OAuth is not configured: set GOOGLE_OAUTH_CLIENT_ID, "
            "GOOGLE_OAUTH_CLIENT_SECRET and GOOGLE_OAUTH_REDIRECT_URI."
        )


def build_consent_url(state: str) -> str:
    _require_config()
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    _require_config()
    try:
        response = requests.post(
            GOOGLE_TOKEN_URI,
            data={
                "code": code,
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=_EXCHANGE_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise OAuthExchangeError(f"Google token endpoint unreachable: {exc}") from exc
    if response.status_code != 200:
        raise OAuthExchangeError(
            f"Google token endpoint returned {response.status_code}: {response.text[:300]}"
        )
    return response.json()
