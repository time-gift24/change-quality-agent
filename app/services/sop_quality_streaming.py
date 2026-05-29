import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID


class SopQualityBroadcast:
    def __init__(self) -> None:
        self._subscribers: dict[UUID, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(
            set
        )

    @asynccontextmanager
    async def subscribe(
        self,
        check_id: UUID,
    ) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers[check_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[check_id].discard(queue)
            if not self._subscribers[check_id]:
                self._subscribers.pop(check_id, None)

    async def publish(self, check_id: UUID, message: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(check_id, ())):
            await queue.put(dict(message))
