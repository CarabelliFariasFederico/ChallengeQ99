from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils.http import content_disposition_header
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.api.permissions import HasDrivePermission
from apps.application import files
from apps.domain.policies import Action

CanView = HasDrivePermission(Action.VIEW)
CanDownload = HasDrivePermission(Action.DOWNLOAD)
CanUpload = HasDrivePermission(Action.UPLOAD)

MAX_PAGE_SIZE = 100


def _int_param(request, name, default):
    raw = request.query_params.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValidationError({name: "Must be an integer."}) from exc


class FilesView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), CanUpload()]
        return [IsAuthenticated(), CanView()]

    def get_throttles(self):
        self.throttle_scope = "drive_upload" if self.request.method == "POST" else "drive_list"
        return [ScopedRateThrottle()]

    def get(self, request):
        page_size = min(max(_int_param(request, "page_size", 50), 1), MAX_PAGE_SIZE)
        items, next_page_token = files.list_files(
            folder_id=request.query_params.get("folder_id") or None,
            page_token=request.query_params.get("page_token") or None,
            page_size=page_size,
        )
        return Response({"items": items, "next_page_token": next_page_token})

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "A multipart 'file' field is required."})

        max_bytes = settings.DRIVE_UPLOAD_MAX_BYTES
        if upload.size > max_bytes:
            raise ValidationError(
                {"file": f"File exceeds the {max_bytes} byte limit."}, code="file_too_large"
            )
        mime_type = upload.content_type or "application/octet-stream"
        allowed = settings.DRIVE_UPLOAD_ALLOWED_MIME_TYPES
        if allowed and mime_type not in allowed:
            raise ValidationError(
                {"file": f"MIME type '{mime_type}' is not allowed."}, code="mime_not_allowed"
            )

        metadata = files.upload_file(
            request, upload, mime_type, request.data.get("folder_id") or None
        )
        return Response(metadata, status=201)


class FileContentView(APIView):
    permission_classes = [IsAuthenticated, CanDownload]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "drive_download"

    def get(self, request, file_id):
        metadata, stream = files.open_download(request, file_id)
        response = StreamingHttpResponse(
            stream, content_type=metadata["mime_type"] or "application/octet-stream"
        )
        safe_name = "".join(ch for ch in (metadata["name"] or "download") if ch >= " ")
        response["Content-Disposition"] = content_disposition_header(
            as_attachment=True, filename=safe_name or "download"
        )
        if metadata["size"] is not None:
            response["Content-Length"] = str(metadata["size"])
        return response
