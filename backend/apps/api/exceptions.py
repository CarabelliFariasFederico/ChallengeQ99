import logging
import uuid

from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.application.audit import record_access_denied
from apps.infrastructure.crypto.secret_box import CryptoConfigError
from apps.infrastructure.drive.factory import NoActiveCredentialError
from apps.infrastructure.drive.gateway import DriveAuthError, DriveError, DriveNotFound
from apps.infrastructure.drive.oauth_flow import (
    InvalidOAuthState,
    OAuthConfigError,
    OAuthExchangeError,
    OAuthMissingRefreshToken,
)

logger = logging.getLogger("apps.api")


_INFRA_MAP = (
    (
        CryptoConfigError,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "credential_encryption_not_configured",
        None,
    ),
    (NoActiveCredentialError, status.HTTP_409_CONFLICT, "no_active_credential", None),
    (DriveNotFound, status.HTTP_404_NOT_FOUND, "drive_file_not_found", None),
    (InvalidOAuthState, status.HTTP_400_BAD_REQUEST, "invalid_oauth_state", None),
    (OAuthMissingRefreshToken, status.HTTP_400_BAD_REQUEST, "refresh_token_missing", None),
    (
        OAuthExchangeError,
        status.HTTP_400_BAD_REQUEST,
        "oauth_exchange_failed",
        "Could not exchange the authorization code with Google. Restart the connection.",
    ),
    (OAuthConfigError, status.HTTP_503_SERVICE_UNAVAILABLE, "oauth_not_configured", None),
    (
        DriveAuthError,
        status.HTTP_502_BAD_GATEWAY,
        "drive_auth_failed",
        "Upstream Drive authentication failed. If the active account was revoked, "
        "reconnect it (OAuth) and activate it again.",
    ),
    (DriveError, status.HTTP_502_BAD_GATEWAY, "drive_error", "Upstream Drive request failed."),
)


def _envelope(code, message, details, request_id, http_status):
    response = Response(
        {"code": code, "message": message, "details": details, "request_id": request_id},
        status=http_status,
    )
    response["X-Request-ID"] = request_id
    return response


def exception_handler(exc, context):
    request = context.get("request")

    request_id = getattr(request, "request_id", None) or uuid.uuid4().hex

    for exc_type, http_status, code, client_message in _INFRA_MAP:
        if isinstance(exc, exc_type):
            if client_message is not None:
                logger.warning("drive failure [request_id=%s]: %s", request_id, exc)
            return _envelope(code, client_message or str(exc), None, request_id, http_status)

    if isinstance(exc, PermissionDenied) and request is not None:
        record_access_denied(request, exc)

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    detail = getattr(exc, "detail", None)
    code = getattr(detail, "code", None) or getattr(exc, "default_code", "error")
    if isinstance(exc, APIException) and isinstance(exc.detail, str):
        message = str(exc.detail)
    elif isinstance(exc, APIException):
        message = str(exc.default_detail)
    else:
        message = "Request failed."
    envelope = _envelope(code, message, response.data, request_id, response.status_code)

    for header, value in response.items():
        if header.lower() not in ("content-type",):
            envelope[header] = value
    return envelope
