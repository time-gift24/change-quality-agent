import pytest

from app.services.sop_client import MockSopClient, SopNotFoundError


@pytest.mark.asyncio
async def test_mock_sop_client_returns_snapshot() -> None:
    client = MockSopClient()

    snapshot = await client.get_sop("release-checklist", "dev")

    assert snapshot.sop_id == "release-checklist"
    assert snapshot.env_key == "dev"
    assert snapshot.payload["title"] == "Mock SOP release-checklist"


@pytest.mark.asyncio
async def test_mock_sop_client_can_simulate_not_found() -> None:
    client = MockSopClient(missing_sop_ids={"missing"})

    with pytest.raises(SopNotFoundError):
        await client.get_sop("missing", "dev")
