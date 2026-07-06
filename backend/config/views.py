from django.db import connection
from django.db.utils import OperationalError
from django.http import JsonResponse


def healthz(request):
    return JsonResponse({"status": "ok"})


def readyz(request):
    from apps.infrastructure.crypto.secret_box import CryptoConfigError, SecretBox

    checks = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "up"
    except OperationalError:
        checks["database"] = "down"
    try:
        SecretBox.from_settings()
        checks["crypto"] = "configured"
    except CryptoConfigError:
        checks["crypto"] = "unconfigured"

    ready = checks["database"] == "up" and checks["crypto"] == "configured"
    return JsonResponse(
        {"status": "ok" if ready else "unavailable", **checks},
        status=200 if ready else 503,
    )
