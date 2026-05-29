import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class SessionBroadcast:
    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue[dict[str, object]]]] = defaultdict(set)

    @asynccontextmanager
    async def subscribe(
        self, session_id: int
    ) -> AsyncIterator[asyncio.Queue[dict[str, object]]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        self._subscribers[session_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[session_id].discard(queue)
            if not self._subscribers[session_id]:
                self._subscribers.pop(session_id, None)

    async def publish(self, session_id: int, message: dict[str, object]) -> None:
        for queue in list(self._subscribers.get(session_id, ())):
            await queue.put(dict(message))
