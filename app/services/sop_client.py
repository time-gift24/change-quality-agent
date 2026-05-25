from typing import Protocol

from app.schemas.sop import SopSnapshot


class SopNotFoundError(Exception):
    pass


class SopClientError(Exception):
    pass


class SopClient(Protocol):
    async def get_sop(self, sop_id: str, env_key: str) -> SopSnapshot:
        ...


class MockSopClient:
    def __init__(self, missing_sop_ids: set[str] | None = None) -> None:
        self._missing_sop_ids = missing_sop_ids or set()

    async def get_sop(self, sop_id: str, env_key: str) -> SopSnapshot:
        if sop_id in self._missing_sop_ids:
            raise SopNotFoundError(sop_id)
        return SopSnapshot(
            sop_id=sop_id,
            env_key=env_key,
            source_version="mock-v1",
            updated_at=None,
            payload={
                "id": sop_id,
                "title": f"Mock SOP {sop_id}",
                "env": env_key,
                "steps": [
                    {"id": "prepare", "title": "Prepare change"},
                    {"id": "review", "title": "Review change"},
                    {"id": "execute", "title": "Execute change"},
                ],
            },
        )
