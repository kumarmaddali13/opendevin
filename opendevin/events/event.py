import datetime
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from opendevin.events.serialization.event import EventSource


@dataclass
class Event:
    @property
    def message(self) -> str:
        if hasattr(self, '_message'):
            return self._message  # type: ignore [attr-defined]
        return ''

    @property
    def id(self) -> int:
        if hasattr(self, '_id'):
            return self._id  # type: ignore [attr-defined]
        return -1

    @property
    def timestamp(self) -> Optional[datetime.datetime]:
        if hasattr(self, '_timestamp'):
            return self._timestamp  # type: ignore [attr-defined]
        return None

    @property
    def source(self) -> Optional['EventSource']:
        if hasattr(self, '_source'):
            return self._source  # type: ignore [attr-defined]
        return None

    @property
    def cause(self) -> Optional[int]:
        if hasattr(self, '_cause'):
            return self._cause  # type: ignore [attr-defined]
        return None

    @staticmethod
    @contextmanager
    def ignore_command_id():
        try:
            Event._ignore_command_id_active = True  # type: ignore [attr-defined]
            yield
        finally:
            Event._ignore_command_id_active = False  # type: ignore [attr-defined]

    @staticmethod
    def is_ignoring_command_id():
        return (
            Event._ignore_command_id_active
            if hasattr(Event, '_ignore_command_id_active')
            else False
        )
