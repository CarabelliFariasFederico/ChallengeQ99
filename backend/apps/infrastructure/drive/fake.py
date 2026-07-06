import itertools

from apps.infrastructure.drive.gateway import DriveGateway, DriveNotFound

_CHUNK = 64 * 1024


class FakeDriveGateway(DriveGateway):
    def __init__(self):
        self._files = {}
        self._ids = itertools.count(1)

    @staticmethod
    def _public(record: dict) -> dict:
        return {
            "id": record["id"],
            "name": record["name"],
            "mime_type": record["mime_type"],
            "size": record["size"],
            "modified_at": record["modified_at"],
        }

    def list_files(
        self, folder_id=None, page_token=None, page_size=DriveGateway.DEFAULT_PAGE_SIZE
    ):
        items = [self._public(f) for f in self._files.values() if f["folder_id"] == folder_id]
        start = int(page_token) if page_token else 0
        page = items[start : start + page_size]
        next_token = str(start + page_size) if start + page_size < len(items) else None
        return page, next_token

    def get_metadata(self, file_id):
        record = self._files.get(file_id)
        if record is None:
            raise DriveNotFound(f"File {file_id!r} not found.")
        return self._public(record)

    def download(self, file_id):
        record = self._files.get(file_id)
        if record is None:
            raise DriveNotFound(f"File {file_id!r} not found.")
        content = record["content"]

        def _chunks():
            for offset in range(0, len(content), _CHUNK):
                yield content[offset : offset + _CHUNK]
            if not content:
                yield b""

        return _chunks()

    def upload(self, name, stream, mime_type, folder_id=None):
        content = stream.read()
        file_id = f"fake-{next(self._ids)}"
        record = {
            "id": file_id,
            "name": name,
            "mime_type": mime_type,
            "size": len(content),
            "modified_at": None,
            "folder_id": folder_id,
            "content": content,
        }
        self._files[file_id] = record
        return self._public(record)


_default_instance = None


_DEMO_FILES = (
    ("Manual de marca.pdf", b"%PDF-1.4 demo content " * 40, "application/pdf"),
    ("Presupuesto 2026.csv", b"rubro,importe\ndemo,123\n" * 30, "text/csv"),
    ("notas-reunion.txt", b"Notas de la reunion de demo.\n" * 10, "text/plain"),
    ("logo.png", b"\x89PNG\r\n\x1a\n-demo-" * 30, "image/png"),
)


def _seed_demo_files(gateway):
    import io

    for name, content, mime_type in _DEMO_FILES:
        gateway.upload(name, io.BytesIO(content), mime_type)


def default_fake_gateway() -> FakeDriveGateway:
    global _default_instance
    if _default_instance is None:
        from django.conf import settings

        _default_instance = FakeDriveGateway()
        if getattr(settings, "DRIVE_FAKE_SEED_FILES", False):
            _seed_demo_files(_default_instance)
    return _default_instance


def reset_default_fake_gateway():
    global _default_instance
    _default_instance = None
