from abc import ABC, abstractmethod
from wopr_audit.schema import AuditEvent


class BaseStorage(ABC):
    @abstractmethod
    async def init(self) -> None:
        """Initialize storage (create tables, etc.)."""
        ...

    @abstractmethod
    async def store(self, event: AuditEvent) -> None:
        """Store a single audit event."""
        ...

    @abstractmethod
    async def query(self, filters: dict | None = None, limit: int = 100, offset: int = 0) -> list[AuditEvent]:
        """Query stored events with optional filters."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close storage connections."""
        ...
