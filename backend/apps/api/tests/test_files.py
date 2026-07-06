import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.domain.models import AuditLog
from apps.infrastructure.drive.fake import default_fake_gateway

pytestmark = pytest.mark.django_db


def seed_file(name="doc.txt", content=b"hello world", mime="text/plain"):
    return default_fake_gateway().upload(name, io.BytesIO(content), mime)


def multipart_file(name="up.txt", content=b"uploaded-bytes", mime="text/plain"):
    return SimpleUploadedFile(name, content, content_type=mime)


class TestDeniedByDefault:
    def test_member_without_grants_is_403_everywhere(self, api_client, member, active_credential):
        seeded = seed_file()
        api_client.force_authenticate(member)
        responses = [
            api_client.get("/api/files"),
            api_client.get(f"/api/files/{seeded['id']}/content"),
            api_client.post("/api/files", {"file": multipart_file()}, format="multipart"),
        ]
        assert [r.status_code for r in responses] == [403, 403, 403]
        assert AuditLog.objects.filter(action=AuditLog.Action.ACCESS_DENIED).count() == 3

    def test_admin_role_grants_nothing_on_the_data_plane(
        self, api_client, admin_user, active_credential
    ):
        api_client.force_authenticate(admin_user)
        assert api_client.get("/api/files").status_code == 403

    def test_unauthenticated_is_401(self, api_client, active_credential):
        assert api_client.get("/api/files").status_code == 401


class TestViewer:
    def test_can_list_but_not_download_nor_upload(
        self, api_client, member, active_credential, grant
    ):
        grant(member, active_credential, view=True)
        seeded = seed_file(name="visible.txt")
        api_client.force_authenticate(member)

        listing = api_client.get("/api/files")
        assert listing.status_code == 200
        assert [i["name"] for i in listing.data["items"]] == ["visible.txt"]
        assert listing.data["next_page_token"] is None

        assert api_client.get(f"/api/files/{seeded['id']}/content").status_code == 403
        upload = api_client.post("/api/files", {"file": multipart_file()}, format="multipart")
        assert upload.status_code == 403

    def test_cursor_pagination(self, api_client, member, active_credential, grant):
        grant(member, active_credential, view=True)
        for i in range(3):
            seed_file(name=f"f{i}.txt")
        api_client.force_authenticate(member)

        page1 = api_client.get("/api/files", {"page_size": 2})
        assert len(page1.data["items"]) == 2
        token = page1.data["next_page_token"]
        assert token is not None

        page2 = api_client.get("/api/files", {"page_size": 2, "page_token": token})
        assert len(page2.data["items"]) == 1
        assert page2.data["next_page_token"] is None


class TestProvidersCase:
    def test_upload_yes_download_no(self, api_client, member, active_credential, grant):
        grant(member, active_credential, upload=True)
        api_client.force_authenticate(member)

        upload = api_client.post(
            "/api/files",
            {"file": multipart_file(name="factura.pdf", mime="application/pdf")},
            format="multipart",
        )
        assert upload.status_code == 201
        file_id = upload.data["id"]

        assert default_fake_gateway().get_metadata(file_id)["name"] == "factura.pdf"

        log = AuditLog.objects.get(action=AuditLog.Action.FILE_UPLOAD)
        assert log.actor == member and log.target_id == file_id

        assert api_client.get(f"/api/files/{file_id}/content").status_code == 403


class TestDownload:
    def test_streams_bytes_and_audits(self, api_client, member, active_credential, grant):
        grant(member, active_credential, download=True)
        content = b"x" * 200_000
        seeded = seed_file(name="big.bin", content=content, mime="application/octet-stream")
        api_client.force_authenticate(member)

        response = api_client.get(f"/api/files/{seeded['id']}/content")
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == content
        assert 'filename="big.bin"' in response["Content-Disposition"]
        assert response["Content-Length"] == str(len(content))

        log = AuditLog.objects.get(action=AuditLog.Action.FILE_DOWNLOAD)
        assert log.actor == member and log.target_id == seeded["id"]
        assert log.metadata["name"] == "big.bin"

    def test_non_latin1_filename_downloads_without_500(
        self, api_client, member, active_credential, grant
    ):
        grant(member, active_credential, download=True)
        seeded = seed_file(name="informe—2026 🚀.pdf", content=b"pdf", mime="application/pdf")
        api_client.force_authenticate(member)
        response = api_client.get(f"/api/files/{seeded['id']}/content")
        assert response.status_code == 200

        assert "filename*=utf-8''" in response["Content-Disposition"].lower()

    def test_unknown_file_is_typed_404(self, api_client, member, active_credential, grant):
        grant(member, active_credential, download=True)
        api_client.force_authenticate(member)
        response = api_client.get("/api/files/nonexistent/content")
        assert response.status_code == 404
        assert response.data["code"] == "drive_file_not_found"


class TestUploadLimits:
    def test_oversized_upload_is_rejected(
        self, api_client, member, active_credential, grant, settings
    ):
        settings.DRIVE_UPLOAD_MAX_BYTES = 5
        grant(member, active_credential, upload=True)
        api_client.force_authenticate(member)
        response = api_client.post(
            "/api/files", {"file": multipart_file(content=b"0123456789")}, format="multipart"
        )
        assert response.status_code == 400

    def test_disallowed_mime_type_is_rejected(
        self, api_client, member, active_credential, grant, settings
    ):
        settings.DRIVE_UPLOAD_ALLOWED_MIME_TYPES = ["application/pdf"]
        grant(member, active_credential, upload=True)
        api_client.force_authenticate(member)
        response = api_client.post(
            "/api/files", {"file": multipart_file(mime="text/plain")}, format="multipart"
        )
        assert response.status_code == 400


class TestNoActiveCredential:
    def test_files_answers_409_not_500(self, api_client, member):
        api_client.force_authenticate(member)
        response = api_client.get("/api/files")
        assert response.status_code == 409
        assert response.data["code"] == "no_active_credential"

        assert not AuditLog.objects.filter(action=AuditLog.Action.ACCESS_DENIED).exists()
