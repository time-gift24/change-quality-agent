from uuid import uuid4

import pytest

from app.services.sop_quality_streaming import SopQualityBroadcast


@pytest.mark.asyncio
async def test_broadcast_delivers_message_to_all_subscribers() -> None:
    check_id = uuid4()
    broadcast = SopQualityBroadcast()

    async with broadcast.subscribe(check_id) as first:
        async with broadcast.subscribe(check_id) as second:
            await broadcast.publish(
                check_id,
                {"type": "live", "node": "review_sop", "message": "Checking."},
            )

            assert await first.get() == {
                "type": "live",
                "node": "review_sop",
                "message": "Checking.",
            }
            assert await second.get() == {
                "type": "live",
                "node": "review_sop",
                "message": "Checking.",
            }
