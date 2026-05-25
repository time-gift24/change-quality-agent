from app.models.runs import Run, RunEvent


def test_run_model_table_name() -> None:
    assert Run.__tablename__ == "runs"


def test_run_event_model_table_name() -> None:
    assert RunEvent.__tablename__ == "run_events"
