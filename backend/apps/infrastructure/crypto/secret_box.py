from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class CryptoConfigError(Exception):
    pass


class DecryptionError(Exception):
    pass


def generate_key() -> str:
    return Fernet.generate_key().decode()


class SecretBox:
    def __init__(self, keys: dict):
        if not keys:
            raise CryptoConfigError("SecretBox needs at least one Fernet key.")
        self._fernets = {}
        for version, key in keys.items():
            try:
                version = int(version)
            except (TypeError, ValueError) as exc:
                raise CryptoConfigError(
                    f"Fernet key version {version!r} is not an integer."
                ) from exc
            try:
                self._fernets[version] = Fernet(key)
            except (TypeError, ValueError) as exc:
                raise CryptoConfigError(
                    f"Fernet key v{version} is invalid ({exc}). Generate a valid one "
                    f"with `python manage.py generate_fernet_key`."
                ) from exc
        self._current_version = max(self._fernets)

    @classmethod
    def from_settings(cls) -> "SecretBox":
        keys_map = (getattr(settings, "FERNET_KEYS", "") or "").strip()
        single = (getattr(settings, "FERNET_KEY", "") or "").strip()
        if keys_map:
            keys = {}
            for pair in keys_map.split(","):
                pair = pair.strip()
                if not pair:
                    continue
                version, sep, key = pair.partition(":")
                if not sep or not key.strip() or not version.strip().isdigit():
                    raise CryptoConfigError(
                        f"FERNET_KEYS entry {pair!r} must look like '<version>:<key>'."
                    )
                keys[int(version)] = key.strip()
            return cls(keys)
        if single:
            return cls({1: single})
        raise CryptoConfigError(
            "No Fernet key configured. Generate one with "
            "`python manage.py generate_fernet_key` and set FERNET_KEY "
            "(or a versioned FERNET_KEYS map) in your .env."
        )

    @property
    def current_version(self) -> int:
        return self._current_version

    def encrypt(self, plaintext) -> bytes:
        if isinstance(plaintext, str):
            plaintext = plaintext.encode()
        return self._fernets[self._current_version].encrypt(plaintext)

    def decrypt(self, ciphertext, key_version: int | None = None) -> bytes:
        ciphertext = bytes(ciphertext)
        if key_version is not None:
            fernet = self._fernets.get(key_version)
            if fernet is None:
                raise DecryptionError(f"No Fernet key registered for version {key_version}.")
            try:
                return fernet.decrypt(ciphertext)
            except InvalidToken as exc:
                raise DecryptionError(
                    f"Ciphertext does not verify against key v{key_version}."
                ) from exc
        for version in sorted(self._fernets, reverse=True):
            try:
                return self._fernets[version].decrypt(ciphertext)
            except InvalidToken:
                continue
        raise DecryptionError("Ciphertext does not match any configured Fernet key.")
