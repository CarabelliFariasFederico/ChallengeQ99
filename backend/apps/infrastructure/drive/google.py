import io

from google.auth.exceptions import GoogleAuthError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from apps.infrastructure.drive.gateway import (
    DriveAuthError,
    DriveError,
    DriveGateway,
    DriveNotFound,
)
from apps.infrastructure.drive.strategies import DriveAuthStrategy

_LIST_FIELDS = "nextPageToken, files(id, name, mimeType, size, modifiedTime)"
_FILE_FIELDS = "id, name, mimeType, size, modifiedTime"
_DOWNLOAD_CHUNK = 1024 * 1024


def _normalize(raw: dict) -> dict:
    size = raw.get("size")
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "mime_type": raw.get("mimeType"),
        "size": int(size) if size is not None else None,
        "modified_at": raw.get("modifiedTime"),
    }


def _translate(exc: HttpError) -> DriveError:
    status = getattr(getattr(exc, "resp", None), "status", None)
    if status == 404:
        return DriveNotFound("File or folder not found in Drive.")
    if status in (401, 403):
        return DriveAuthError(f"Drive rejected the credentials or access (HTTP {status}).")
    return DriveError(f"Drive API error (HTTP {status}).")


class GoogleDriveGateway(DriveGateway):
    def __init__(self, auth_strategy: DriveAuthStrategy):
        self._auth = auth_strategy
        self._service = None

    def _svc(self):
        if self._service is None:
            try:
                credentials = self._auth.build_credentials()
                self._service = build(
                    "drive", "v3", credentials=credentials, cache_discovery=False
                )
            except GoogleAuthError as exc:
                raise DriveAuthError(f"Could not build Google credentials: {exc}") from exc
        return self._service

    def list_files(
        self, folder_id=None, page_token=None, page_size=DriveGateway.DEFAULT_PAGE_SIZE
    ):
        query = f"'{folder_id or 'root'}' in parents and trashed = false"
        try:
            response = (
                self._svc()
                .files()
                .list(q=query, pageSize=page_size, pageToken=page_token, fields=_LIST_FIELDS)
                .execute()
            )
        except HttpError as exc:
            raise _translate(exc) from exc
        except GoogleAuthError as exc:
            raise DriveAuthError(f"Drive authentication failed: {exc}") from exc
        items = [_normalize(f) for f in response.get("files", [])]
        return items, response.get("nextPageToken")

    def get_metadata(self, file_id):
        try:
            raw = self._svc().files().get(fileId=file_id, fields=_FILE_FIELDS).execute()
        except HttpError as exc:
            raise _translate(exc) from exc
        except GoogleAuthError as exc:
            raise DriveAuthError(f"Drive authentication failed: {exc}") from exc
        return _normalize(raw)

    def download(self, file_id):
        try:
            request = self._svc().files().get_media(fileId=file_id)
        except GoogleAuthError as exc:
            raise DriveAuthError(f"Drive authentication failed: {exc}") from exc

        def _chunks():
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request, chunksize=_DOWNLOAD_CHUNK)
            done = False
            while not done:
                try:
                    _, done = downloader.next_chunk()
                except HttpError as exc:
                    raise _translate(exc) from exc
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate(0)

        return _chunks()

    def upload(self, name, stream, mime_type, folder_id=None):
        body = {"name": name}
        if folder_id:
            body["parents"] = [folder_id]
        media = MediaIoBaseUpload(stream, mimetype=mime_type, resumable=True)
        try:
            raw = (
                self._svc()
                .files()
                .create(body=body, media_body=media, fields=_FILE_FIELDS)
                .execute()
            )
        except HttpError as exc:
            raise _translate(exc) from exc
        except GoogleAuthError as exc:
            raise DriveAuthError(f"Drive authentication failed: {exc}") from exc
        return _normalize(raw)
