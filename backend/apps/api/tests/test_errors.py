from apps.api.exceptions import exception_handler
from apps.infrastructure.drive.factory import NoActiveCredentialError
from apps.infrastructure.drive.gateway import DriveAuthError, DriveError


class TestSanitization:
    def test_drive_auth_error_never_leaks_upstream_detail(self):
        exc = DriveAuthError(
            "Could not build Google credentials: invalid_grant: token endpoint said X"
        )
        response = exception_handler(exc, {"request": None})
        assert response.status_code == 502
        assert response.data["code"] == "drive_auth_failed"
        assert "token endpoint" not in response.data["message"]

        assert "reconnect" in response.data["message"]

    def test_generic_drive_error_is_sanitized_too(self):
        response = exception_handler(DriveError("raw SDK internals here"), {"request": None})
        assert response.status_code == 502
        assert "raw SDK internals" not in response.data["message"]

    def test_our_own_409_message_passes_through(self):
        exc = NoActiveCredentialError("No active Drive credential; activate one first.")
        response = exception_handler(exc, {"request": None})
        assert response.status_code == 409
        assert response.data["code"] == "no_active_credential"
        assert "active" in response.data["message"]

    def test_envelope_carries_request_id(self):
        response = exception_handler(DriveError("x"), {"request": None})
        assert response.data["request_id"]
        assert response["X-Request-ID"] == response.data["request_id"]
