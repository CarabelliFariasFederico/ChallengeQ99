from django.conf import settings

from apps.domain.models import AuditLog

_DERIVE = object()


def client_ip(request):
    if getattr(settings, "AUDIT_TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR")


def record(request, action, *, actor=_DERIVE, target_type="", target_id="", metadata=None):
    if actor is _DERIVE:
        user = getattr(request, "user", None)
        actor = user if getattr(user, "is_authenticated", False) else None
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        metadata=metadata or {},
        ip=client_ip(request),
    )


def record_access_denied(request, exc):
    detail = getattr(exc, "detail", None)
    return record(
        request,
        AuditLog.Action.ACCESS_DENIED,
        target_type="endpoint",
        target_id=request.path,
        metadata={"method": request.method, "reason": str(detail) if detail else str(exc)},
    )
