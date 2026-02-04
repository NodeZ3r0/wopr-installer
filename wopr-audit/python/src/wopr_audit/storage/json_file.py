import json
from pathlib import Path
from wopr_audit.schema import AuditEvent
from wopr_audit.storage.base import BaseStorage


class JSONFileStorage(BaseStorage):
    """Append-only JSON Lines file storage. Minimal deps, works everywhere."""

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)

    async def init(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    async def store(self, event: AuditEvent) -> None:
        line = event.model_dump_json() + "\n"
        with open(self.file_path, "a") as f:
            f.write(line)

    async def query(self, filters: dict | None = None, limit: int = 100, offset: int = 0) -> list[AuditEvent]:
        if not self.file_path.exists():
            return []
        results = []
        with open(self.file_path, "r") as f:
            lines = f.readlines()
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            event = AuditEvent.model_validate_json(line)
            if filters:
                skip = False
                for k, v in filters.items():
                    if getattr(event, k, None) != v:
                        skip = True
                        break
                if skip:
                    continue
            if offset > 0:
                offset -= 1
                continue
            results.append(event)
            if len(results) >= limit:
                break
        return results

    async def close(self) -> None:
        pass
