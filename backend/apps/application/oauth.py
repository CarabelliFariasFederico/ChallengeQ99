import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.application import audit
from apps.domain.models import AuditLog, DriveCredential, OAuthState
from apps.infrastructure.drive import oauth_flow
from apps.infrastructure.drive.oauth_flow import InvalidOAuthState, OAuthMissingRefreshToken

DEFAULT_ACCOUNT_LABEL = "Google Drive (OAuth)"


def start_connection(request, account_label):
    account_label = str(account_label or DEFAULT_ACCOUNT_LABEL)[:255]
    ttl = settings.OAUTH_STATE_TTL_SECONDS

    OAuthState.objects.filter(expires_at__lt=timezone.now()).delete()

    state = secrets.token_urlsafe(32)
    authorization_url = oauth_flow.build_consent_url(state)
    OAuthState.objects.create(
        state=state,
        initiated_by=request.user,
        account_label=account_label,
        expires_at=timezone.now() + timedelta(seconds=ttl),
    )
    audit.record(
        request,
        AuditLog.Action.CREDENTIAL_OAUTH_INITIATE,
        target_type="drive_credential",
        metadata={"account_label": account_label},
    )
    return {"authorization_url": authorization_url, "state_expires_in": ttl}


def consume_state(value: str) -> OAuthState:
    if not value:
        raise InvalidOAuthState("Missing OAuth state.")
    with transaction.atomic():
        state = (
            OAuthState.objects.select_for_update()
            .select_related("initiated_by")
            .filter(state=value)
            .first()
        )
        if state is None:
            raise InvalidOAuthState(
                "Unknown or already-used OAuth state. Restart the connection from the admin panel."
            )
        expired = state.expires_at <= timezone.now()
        state.delete()
    if expired:
        raise InvalidOAuthState(
            "The OAuth state expired. Restart the connection from the admin panel."
        )
    return state


def complete_connection(request, state, code):
    tokens = oauth_flow.exchange_code(code)
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise OAuthMissingRefreshToken(
            "Google did not return a refresh token, so the account cannot be "
            "stored. Restart the connection: the consent screen must be shown "
            "again (prompt=consent) and offline access granted."
        )

    credential = DriveCredential(
        account_label=state.account_label,
        auth_method=DriveCredential.AuthMethod.OAUTH,
        is_active=False,
    )
    credential.set_secret(refresh_token)
    credential.save()
    audit.record(
        request,
        AuditLog.Action.CREDENTIAL_CREATE,
        actor=state.initiated_by,
        target_type="drive_credential",
        target_id=credential.pk,
        metadata={
            "via": "oauth",
            "account_label": credential.account_label,
            "key_version": credential.key_version,
        },
    )
    return credential
