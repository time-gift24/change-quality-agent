from app.schemas.sop import SopSnapshot


def test_sop_snapshot_accepts_raw_payload() -> None:
    snapshot = SopSnapshot(
        sop_id="release-checklist",
        env_key="dev",
        source_version="v1",
        updated_at=None,
        payload={"steps": ["review", "deploy"]},
    )

    assert snapshot.payload["steps"] == ["review", "deploy"]
