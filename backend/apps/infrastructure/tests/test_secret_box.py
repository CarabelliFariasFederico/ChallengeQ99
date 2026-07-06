import pytest
from cryptography.fernet import Fernet

from apps.domain.models import DriveCredential
from apps.infrastructure.crypto.secret_box import (
    CryptoConfigError,
    DecryptionError,
    SecretBox,
    generate_key,
)

KEY_V1 = Fernet.generate_key().decode()
KEY_V2 = Fernet.generate_key().decode()


class TestRoundTrip:
    def test_round_trip_str(self):
        box = SecretBox({1: KEY_V1})
        assert box.decrypt(box.encrypt("my-refresh-token")) == b"my-refresh-token"

    def test_round_trip_bytes(self):
        box = SecretBox({1: KEY_V1})
        assert box.decrypt(box.encrypt(b"\x00\x01binary")) == b"\x00\x01binary"

    def test_ciphertext_does_not_contain_plaintext(self):
        box = SecretBox({1: KEY_V1})
        secret = "super-secret-refresh-token-12345"
        ciphertext = box.encrypt(secret)
        assert secret.encode() not in ciphertext

    def test_generate_key_produces_a_working_key(self):
        box = SecretBox({1: generate_key()})
        assert box.decrypt(box.encrypt("x")) == b"x"


class TestKeyRotation:
    def test_old_records_decrypt_after_adding_v2(self):
        old_box = SecretBox({1: KEY_V1})
        old_ciphertext = old_box.encrypt("legacy-secret")

        rotated_box = SecretBox({1: KEY_V1, 2: KEY_V2})
        assert rotated_box.current_version == 2

        assert rotated_box.decrypt(old_ciphertext, key_version=1) == b"legacy-secret"

        assert rotated_box.decrypt(old_ciphertext) == b"legacy-secret"

        assert rotated_box.decrypt(rotated_box.encrypt("new"), key_version=2) == b"new"

    def test_decrypt_with_wrong_version_is_a_loud_error(self):
        ciphertext = SecretBox({1: KEY_V1}).encrypt("s")
        box = SecretBox({1: KEY_V1, 2: KEY_V2})
        with pytest.raises(DecryptionError):
            box.decrypt(ciphertext, key_version=2)

    def test_decrypt_with_unknown_version_is_a_loud_error(self):
        box = SecretBox({1: KEY_V1})
        with pytest.raises(DecryptionError):
            box.decrypt(box.encrypt("s"), key_version=9)

    def test_foreign_ciphertext_matches_no_key(self):
        foreign = SecretBox({1: Fernet.generate_key()}).encrypt("s")
        with pytest.raises(DecryptionError):
            SecretBox({1: KEY_V1}).decrypt(foreign)


class TestConfiguration:
    def test_missing_key_fails_with_actionable_message(self, settings):
        settings.FERNET_KEY = ""
        settings.FERNET_KEYS = ""
        with pytest.raises(CryptoConfigError) as excinfo:
            SecretBox.from_settings()
        assert "generate_fernet_key" in str(excinfo.value)

    def test_invalid_key_fails_loudly(self):
        with pytest.raises(CryptoConfigError):
            SecretBox({1: "definitely-not-a-fernet-key"})

    def test_no_keys_at_all_fails_loudly(self):
        with pytest.raises(CryptoConfigError):
            SecretBox({})

    def test_from_settings_single_key_is_version_1(self, settings):
        settings.FERNET_KEY = KEY_V1
        settings.FERNET_KEYS = ""
        assert SecretBox.from_settings().current_version == 1

    def test_from_settings_versioned_map_wins(self, settings):
        settings.FERNET_KEY = ""
        settings.FERNET_KEYS = f"1:{KEY_V1},2:{KEY_V2}"
        assert SecretBox.from_settings().current_version == 2

    def test_from_settings_malformed_map_fails_loudly(self, settings):
        settings.FERNET_KEYS = "not-a-versioned-pair"
        with pytest.raises(CryptoConfigError):
            SecretBox.from_settings()


@pytest.mark.django_db
class TestDriveCredentialSecretIntegration:
    @pytest.fixture(autouse=True)
    def _crypto(self, settings):
        settings.FERNET_KEY = ""
        settings.FERNET_KEYS = f"1:{KEY_V1}"

    def _credential(self):
        return DriveCredential.objects.create(
            account_label="Marketing Drive",
            auth_method=DriveCredential.AuthMethod.OAUTH,
        )

    def test_set_and_get_secret_round_trip(self):
        credential = self._credential()
        credential.set_secret("refresh-token-abc")
        credential.save()
        credential.refresh_from_db()
        assert credential.get_secret() == b"refresh-token-abc"

    def test_persisted_ciphertext_never_contains_plaintext(self):
        credential = self._credential()
        credential.set_secret("PLAINTEXT-SENTINEL")
        credential.save()
        stored = bytes(
            DriveCredential.objects.values_list("secret_ciphertext", flat=True).get(
                pk=credential.pk
            )
        )
        assert stored
        assert b"PLAINTEXT-SENTINEL" not in stored

    def test_set_secret_stamps_the_current_key_version(self, settings):
        settings.FERNET_KEYS = f"1:{KEY_V1},2:{KEY_V2}"
        credential = self._credential()
        credential.set_secret("s")
        assert credential.key_version == 2

    def test_get_secret_without_stored_secret_is_a_loud_error(self):
        credential = self._credential()
        with pytest.raises(DecryptionError):
            credential.get_secret()
