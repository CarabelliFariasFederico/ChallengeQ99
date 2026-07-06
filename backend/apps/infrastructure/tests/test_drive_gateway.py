import io

import pytest

from apps.infrastructure.drive.fake import FakeDriveGateway
from apps.infrastructure.drive.gateway import DriveNotFound


@pytest.fixture
def gateway():
    return FakeDriveGateway()


def upload(
    gateway, name="report.pdf", content=b"pdf-bytes", folder_id=None, mime_type="application/pdf"
):
    return gateway.upload(name, io.BytesIO(content), mime_type, folder_id=folder_id)


class TestUploadListDownload:
    def test_upload_then_list_shows_the_file(self, gateway):
        meta = upload(gateway, name="a.txt", content=b"hello", mime_type="text/plain")
        items, next_token = gateway.list_files()
        assert next_token is None
        assert [i["id"] for i in items] == [meta["id"]]
        assert items[0]["name"] == "a.txt"
        assert items[0]["mime_type"] == "text/plain"
        assert items[0]["size"] == 5

    def test_download_returns_the_uploaded_bytes(self, gateway):
        content = b"x" * 200_000
        meta = upload(gateway, content=content)
        assert b"".join(gateway.download(meta["id"])) == content

    def test_download_streams_in_chunks(self, gateway):
        meta = upload(gateway, content=b"y" * 200_000)
        chunks = list(gateway.download(meta["id"]))
        assert len(chunks) > 1

    def test_get_metadata_matches_upload(self, gateway):
        meta = upload(gateway, name="b.bin", content=b"1234")
        fetched = gateway.get_metadata(meta["id"])
        assert fetched == meta

    def test_folder_scoping(self, gateway):
        in_root = upload(gateway, name="root.txt")
        in_folder = upload(gateway, name="nested.txt", folder_id="folder-1")
        root_items, _ = gateway.list_files()
        folder_items, _ = gateway.list_files(folder_id="folder-1")
        assert [i["id"] for i in root_items] == [in_root["id"]]
        assert [i["id"] for i in folder_items] == [in_folder["id"]]

    def test_pagination(self, gateway):
        ids = [upload(gateway, name=f"f{i}.txt")["id"] for i in range(3)]
        page1, token = gateway.list_files(page_size=2)
        assert [i["id"] for i in page1] == ids[:2]
        assert token is not None
        page2, token2 = gateway.list_files(page_token=token, page_size=2)
        assert [i["id"] for i in page2] == ids[2:]
        assert token2 is None


class TestTypedErrors:
    def test_get_metadata_unknown_id_raises_drive_not_found(self, gateway):
        with pytest.raises(DriveNotFound):
            gateway.get_metadata("nope")

    def test_download_unknown_id_raises_drive_not_found(self, gateway):
        with pytest.raises(DriveNotFound):
            gateway.download("nope")
