import json
import logging

import pytest

from config.observability import JsonFormatter, redact, request_id_var


def _record(message):
    return logging.LogRecord("apps.api", logging.INFO, __file__, 1, message, None, None)


class TestRedaction:
    def test_known_secrets_never_reach_log_output(self):
        out = JsonFormatter().format(
            _record(
                'login password=SUPER-SECRET-PW refresh="RT-abc123" '
                "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
            )
        )
        assert "SUPER-SECRET-PW" not in out
        assert "RT-abc123" not in out
        assert "eyJhbGciOiJIUzI1NiJ9" not in out
        assert "[REDACTED]" in out

    def test_output_is_one_valid_json_object(self):
        payload = json.loads(JsonFormatter().format(_record("hello world")))
        assert payload["level"] == "INFO"
        assert payload["logger"] == "apps.api"
        assert payload["message"] == "hello world"

    def test_request_id_lands_in_the_payload(self):
        token = request_id_var.set("rid-123")
        try:
            payload = json.loads(JsonFormatter().format(_record("with context")))
        finally:
            request_id_var.reset(token)
        assert payload["request_id"] == "rid-123"

    def test_redact_helper_keeps_non_sensitive_text(self):
        assert redact("user=admin@demo.local action=login") == (
            "user=admin@demo.local action=login"
        )


@pytest.mark.django_db
class TestRequestId:
    def test_every_response_carries_a_request_id(self, api_client, member):
        api_client.force_authenticate(member)
        response = api_client.get("/api/me")
        assert response["X-Request-ID"]

    def test_client_provided_id_is_echoed_and_correlates_with_envelope(self, api_client):
        response = api_client.get("/api/me", HTTP_X_REQUEST_ID="my-trace-id")
        assert response.status_code == 401

        assert response["X-Request-ID"] == "my-trace-id"
        assert response.data["request_id"] == "my-trace-id"


@pytest.mark.django_db
class TestHealth:
    def test_healthz_is_pure_liveness(self, api_client):
        response = api_client.get("/healthz")
        assert response.status_code == 200

    def test_readyz_ok_with_db_and_crypto(self, api_client):
        response = api_client.get("/readyz")
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body == {"status": "ok", "database": "up", "crypto": "configured"}

    def test_readyz_503_without_crypto_config(self, api_client, settings):
        settings.FERNET_KEY = ""
        settings.FERNET_KEYS = ""
        response = api_client.get("/readyz")
        assert response.status_code == 503
        assert json.loads(response.content)["crypto"] == "unconfigured"
