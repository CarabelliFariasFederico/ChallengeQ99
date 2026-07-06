from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import BinaryIO


class DriveError(Exception):
    pass


class DriveAuthError(DriveError):
    pass


class DriveNotFound(DriveError):
    pass


class DriveGateway(ABC):
    DEFAULT_PAGE_SIZE = 50

    @abstractmethod
    def list_files(
        self,
        folder_id: str | None = None,
        page_token: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[dict], str | None]:
        pass

    @abstractmethod
    def get_metadata(self, file_id: str) -> dict:
        pass

    @abstractmethod
    def download(self, file_id: str) -> Iterator[bytes]:
        pass

    @abstractmethod
    def upload(
        self,
        name: str,
        stream: BinaryIO,
        mime_type: str,
        folder_id: str | None = None,
    ) -> dict:
        pass
