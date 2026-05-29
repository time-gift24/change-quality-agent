from pathlib import Path

from scripts.check_any_usage import AnyAllowance, find_disallowed_any


def test_find_disallowed_any_reports_unlisted_files(tmp_path: Path) -> None:
    source = tmp_path / "app" / "models.py"
    source.parent.mkdir()
    source.write_text("from typing import Any\n\nvalue: Any\n")

    findings = find_disallowed_any(tmp_path, [source], allowed_counts={})

    assert len(findings) == 1
    assert findings[0].path == Path("app/models.py")
    assert findings[0].count == 2
    assert findings[0].allowed == 0


def test_find_disallowed_any_reports_allowance_overages(tmp_path: Path) -> None:
    source = tmp_path / "app" / "core" / "agent_runtime.py"
    source.parent.mkdir(parents=True)
    source.write_text("from typing import Any\n\nfirst: Any\nsecond: Any\n")

    findings = find_disallowed_any(
        tmp_path,
        [source],
        allowed_counts={
            Path("app/core/agent_runtime.py"): AnyAllowance(
                count=2,
                reason="dynamic agent runtime boundary",
            )
        },
    )

    assert len(findings) == 1
    assert findings[0].path == Path("app/core/agent_runtime.py")
    assert findings[0].count == 3
    assert findings[0].allowed == 2
