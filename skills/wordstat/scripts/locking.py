"""OS-managed single-writer ownership for one local store."""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO


class StoreBusyError(RuntimeError):
    """Another process already owns this store."""


class StoreLock:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / ".owner.lock"
        self._handle: BinaryIO = self.path.open("a+b")
        try:
            self._handle.seek(0, os.SEEK_END)
            if self._handle.tell() == 0:
                self._handle.seek(0)
                self._handle.write(b"0")
                self._handle.flush()
                os.fsync(self._handle.fileno())
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt

                try:
                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as error:
                    raise StoreBusyError(f"store is already owned: {directory}") from error
            else:
                import fcntl

                try:
                    fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as error:
                    raise StoreBusyError(f"store is already owned: {directory}") from error
        except BaseException:
            self._handle.close()
            raise

    def close(self) -> None:
        if self._handle.closed:
            return
        self._handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
