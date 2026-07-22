"""Shared primitives for the AI Software Company domain model."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Protocol
from uuid import uuid4


class DomainValidationError(ValueError):
    """Raised when a domain object or transition violates an invariant."""


class InvalidTransitionError(DomainValidationError):
    """Raised when a lifecycle transition is not permitted."""


class Clock(Protocol):
    """Source of timezone-aware UTC timestamps."""

    def now(self) -> datetime:
        """Return the current timezone-aware UTC timestamp."""


class UtcClock:
    """System clock using timezone-aware UTC."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class IdGenerator(Protocol):
    """Source of stable string identifiers."""

    def new_id(self, prefix: str) -> str:
        """Return a new stable ID with the requested prefix."""


class UuidIdGenerator:
    """UUID-based production ID generator."""

    def new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"


class SequenceIdGenerator:
    """Deterministic ID generator intended for tests."""

    def __init__(self, start: int = 1) -> None:
        self._next = start

    def new_id(self, prefix: str) -> str:
        value = f"{prefix}_{self._next:06d}"
        self._next += 1
        return value


def require_id(value: str, field: str = "id") -> str:
    """Validate a non-empty stable string identifier."""
    if not isinstance(value, str) or not value.strip():
        raise DomainValidationError(f"{field} must be a non-empty string")
    return value


def require_text(value: str, field: str) -> str:
    """Validate required text."""
    if not isinstance(value, str) or not value.strip():
        raise DomainValidationError(f"{field} must be non-empty")
    return value


def require_utc(value: datetime, field: str) -> datetime:
    """Validate that a timestamp is timezone-aware and normalized to UTC."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DomainValidationError(f"{field} must be timezone-aware")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise DomainValidationError(f"{field} must use UTC")
    return value


def require_enum(value: Any, enum_type: type[Enum], field: str) -> Enum:
    """Validate runtime enum membership instead of relying only on type hints."""
    if not isinstance(value, enum_type):
        raise DomainValidationError(f"{field} must be a {enum_type.__name__}")
    return value


def utc_from_iso(value: str) -> datetime:
    """Parse and validate an ISO-8601 UTC timestamp."""
    return require_utc(datetime.fromisoformat(value), "timestamp")


def json_value(value: Any) -> Any:
    """Recursively convert dataclasses, enums and timestamps to JSON values."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        require_utc(value, "timestamp")
        return value.isoformat()
    if is_dataclass(value):
        return {key: json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise DomainValidationError(f"value is not JSON-compatible: {type(value).__name__}")


def enum_parser(enum_type: type[Enum]) -> Callable[[str], Enum]:
    """Return a parser useful to explicit deserializers."""
    return enum_type
