from apps.application import audit
from apps.domain.models import AuditLog
from apps.infrastructure.drive.factory import DriveClientFactory


def list_files(folder_id, page_token, page_size):
    gateway = DriveClientFactory.build()
    return gateway.list_files(folder_id=folder_id, page_token=page_token, page_size=page_size)


def upload_file(request, upload, mime_type, folder_id):
    gateway = DriveClientFactory.build()
    metadata = gateway.upload(
        name=upload.name,
        stream=upload,
        mime_type=mime_type,
        folder_id=folder_id,
    )
    audit.record(
        request,
        AuditLog.Action.FILE_UPLOAD,
        target_type="drive_file",
        target_id=metadata["id"],
        metadata={"name": metadata["name"], "size": metadata["size"], "mime_type": mime_type},
    )
    return metadata


def open_download(request, file_id):
    gateway = DriveClientFactory.build()
    metadata = gateway.get_metadata(file_id)
    stream = gateway.download(file_id)
    audit.record(
        request,
        AuditLog.Action.FILE_DOWNLOAD,
        target_type="drive_file",
        target_id=file_id,
        metadata={"name": metadata["name"], "size": metadata["size"]},
    )
    return metadata, stream
