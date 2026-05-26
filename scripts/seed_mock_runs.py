"""Seed mock SOP runs + events into Postgres for end-to-end frontend testing."""

import asyncio
import random
from datetime import datetime
from uuid import UUID

from app.core.database import async_session
from app.repositories.runs import RunRepository
from app.schemas.runs import RunStatus

ENV_KEY = "dev"


def _generate_sop_id() -> str:
    date_part = datetime.now().strftime("%Y%m%d")
    suffix = f"{random.randint(0, 999999):06d}"
    return f"SOP{date_part}{suffix}"


ENV_SNAPSHOT = {"key": ENV_KEY, "name_en": "Development", "name_zh": "开发"}


def _sop_snapshot(sop_id: str, title: str) -> dict:
    return {
        "sop_id": sop_id,
        "env_key": ENV_KEY,
        "source_version": "mock-1",
        "updated_at": "2026-05-26T00:00:00Z",
        "payload": {"title": title},
    }


async def _seed_terminal_run(repo: RunRepository) -> UUID:
    sop_id = _generate_sop_id()
    run = await repo.create_sop_run(
        sop_id=sop_id,
        env_key=ENV_KEY,
        env_snapshot=ENV_SNAPSHOT,
        sop_snapshot=_sop_snapshot(sop_id, "Release checklist"),
        active_conflict_key=f"seed-terminal:{sop_id}:{ENV_KEY}",
    )
    run_id = run.id
    thread_id = run.thread_id

    await repo.mark_running(run_id)

    async def emit(event_type: str, node: str | None, payload: dict) -> None:
        await repo.append_event(
            run_id,
            event_type=event_type,
            thread_id=thread_id,
            payload=payload,
            node=node,
        )

    await emit("custom", "start", {"message": "Started mock SOP quality graph."})

    await emit("tasks", "load_sop", {"status": "started"})
    for chunk in ("Loading ", "release ", "checklist..."):
        await emit("messages", "load_sop", {"delta": chunk})
    await emit("tasks", "load_sop", {"status": "completed"})
    await emit(
        "updates",
        "load_sop",
        {"value": {"steps_loaded": 3}, "status": "ok"},
    )

    await emit("tasks", "check_steps", {"status": "started"})
    for chunk in ("Validating ", "step 1... ", "step 2... ", "step 3... done."):
        await emit("messages", "check_steps", {"delta": chunk})
    await emit("tasks", "check_steps", {"status": "completed"})
    await emit("updates", "check_steps", {"value": {"checks_passed": 3}})

    await emit("tasks", "summarize_result", {"status": "started"})
    for chunk in ("All ", "checks ", "passed. ", "Release ", "is ready."):
        await emit("messages", "summarize_result", {"delta": chunk})
    await emit("tasks", "summarize_result", {"status": "completed"})
    await emit(
        "updates",
        "summarize_result",
        {"value": {"summary": "Release ready", "risk": "low"}},
    )

    await emit("done", None, {"status": "done", "result_status": "mock_success"})

    await repo.mark_terminal(
        run_id,
        RunStatus.success,
        result_status="mock_success",
        raw_graph_output={"status": "ok"},
    )
    return run_id


async def _seed_failed_run(repo: RunRepository) -> UUID:
    sop_id = _generate_sop_id()
    run = await repo.create_sop_run(
        sop_id=sop_id,
        env_key=ENV_KEY,
        env_snapshot=ENV_SNAPSHOT,
        sop_snapshot=_sop_snapshot(sop_id, "Release checklist"),
        active_conflict_key=f"seed-error:{sop_id}:{ENV_KEY}",
    )
    run_id = run.id
    thread_id = run.thread_id

    await repo.mark_running(run_id)

    async def emit(event_type: str, node: str | None, payload: dict) -> None:
        await repo.append_event(
            run_id,
            event_type=event_type,
            thread_id=thread_id,
            payload=payload,
            node=node,
        )

    await emit("tasks", "load_sop", {"status": "started"})
    await emit("messages", "load_sop", {"delta": "Loading SOP from upstream..."})
    await emit(
        "tasks",
        "load_sop",
        {"status": "failed", "error": "SOP upstream returned 502."},
    )
    await emit(
        "error",
        "load_sop",
        {"error": "SOP upstream returned 502.", "type": "SopClientError"},
    )

    await repo.mark_terminal(
        run_id,
        RunStatus.error,
        result_status="error",
        error={"type": "SopClientError", "message": "SOP upstream returned 502."},
    )
    return run_id


async def _seed_markdown_table_run(repo: RunRepository) -> UUID:
    sop_id = _generate_sop_id()
    run = await repo.create_sop_run(
        sop_id=sop_id,
        env_key=ENV_KEY,
        env_snapshot=ENV_SNAPSHOT,
        sop_snapshot=_sop_snapshot(sop_id, "Database Migration Audit"),
        active_conflict_key=f"seed-markdown:{sop_id}:{ENV_KEY}",
    )
    run_id = run.id
    thread_id = run.thread_id

    await repo.mark_running(run_id)

    async def emit(event_type: str, node: str | None, payload: dict) -> None:
        await repo.append_event(
            run_id,
            event_type=event_type,
            thread_id=thread_id,
            payload=payload,
            node=node,
        )

    await emit("tasks", "analyze_schema", {"status": "started"})
    await emit("messages", "analyze_schema", {"delta": "Analyzing database schema..."})
    await emit("messages", "analyze_schema", {"delta": "\n\n**检测到的迁移风险:**\n\n"})
    await emit("messages", "analyze_schema", {"delta": "| 表名 | 列名 | 类型 | 建议 | 风险等级 |\n"})
    await emit("messages", "analyze_schema", {"delta": "|------|------|------|------|----------|\n"})
    await emit("messages", "analyze_schema", {"delta": "| orders | amount | integer | 改为 numeric | 🔴 High |\n"})
    await emit("messages", "analyze_schema", {"delta": "| users | email | varchar(255) | 加唯一索引 | 🟡 Medium |\n"})
    await emit("messages", "analyze_schema", {"delta": "| products | price | money | 改为 numeric | 🟢 Low |\n"})
    await emit("tasks", "analyze_schema", {"status": "completed"})
    await emit("updates", "analyze_schema", {"value": {"tables_checked": 3}})

    await emit("tasks", "check_locks", {"status": "started"})
    await emit("messages", "check_locks", {"delta": "Checking for long-running transactions..."})
    await emit("messages", "check_locks", {"delta": "\n\n**活跃事务:**\n\n- No long-running transactions detected.\n- All locks are row-level locks.\n\n"})
    await emit("tasks", "check_locks", {"status": "completed"})
    await emit("updates", "check_locks", {"value": {"locks_checked": 12}})

    await emit("tasks", "generate_report", {"status": "started"})
    await emit("messages", "generate_report", {"delta": "\n\n```sql\n-- 建议执行的 SQL:\n"})
    await emit("messages", "generate_report", {"delta": "CREATE UNIQUE INDEX idx_users_email ON users(email);\n"})
    await emit("messages", "generate_report", {"delta": "ALTER TABLE orders ALTER COLUMN amount TYPE numeric;\n```\n"})
    await emit("tasks", "generate_report", {"status": "completed"})
    await emit("updates", "generate_report", {"value": {"report_generated": True}})

    await emit("done", None, {"status": "done", "result_status": "complete"})
    await repo.mark_terminal(run_id, RunStatus.success, result_status="complete")
    return run_id


async def _seed_reasoning_run(repo: RunRepository) -> UUID:
    sop_id = _generate_sop_id()
    run = await repo.create_sop_run(
        sop_id=sop_id,
        env_key=ENV_KEY,
        env_snapshot=ENV_SNAPSHOT,
        sop_snapshot=_sop_snapshot(sop_id, "API v2 Design Review"),
        active_conflict_key=f"seed-reasoning:{sop_id}:{ENV_KEY}",
    )
    run_id = run.id
    thread_id = run.thread_id

    await repo.mark_running(run_id)

    async def emit(event_type: str, node: str | None, payload: dict) -> None:
        await repo.append_event(
            run_id,
            event_type=event_type,
            thread_id=thread_id,
            payload=payload,
            node=node,
        )

    await emit("tasks", "reasoning", {"status": "started"})
    await emit("messages", "reasoning", {"delta": "让我仔细分析一下这个 API 设计..."})
    await emit("messages", "reasoning", {"delta": "\n\n**思考过程:**\n\n"})
    await emit("messages", "reasoning", {"delta": "1. 首先看接口的幂等性设计：POST 接口缺少 Idempotency-Key\n"})
    await emit("messages", "reasoning", {"delta": "2. 然后是分页参数：offset/limit 模式没有最大限制\n"})
    await emit("messages", "reasoning", {"delta": "3. 错误码设计：4xx 和 5xx 没有细分\n"})
    await emit("messages", "reasoning", {"delta": "4. 速率限制：没有 RateLimit 响应头\n\n"})
    await emit("messages", "reasoning", {"delta": "**综合评估:** 整体设计符合 REST 规范，但在生产级可靠性方面有改进空间。\n"})
    await emit("tasks", "reasoning", {"status": "completed"})
    await emit("updates", "reasoning", {"value": {"points_analyzed": 4}})

    await emit("tasks", "tool_call_demo", {"status": "started"})
    await emit("messages", "tool_call_demo", {"delta": "**调用工具验证:**\n\n"})
    await emit("messages", "tool_call_demo", {"delta": "```json\n{\n  \"tool\": \"openapi_linter\",\n  \"input\": {\n    \"path\": \"/api/v2/spec/openapi.json\",\n    \"rules\": [\"security\", \"idempotency\", \"rate-limit\"]\n  }\n}\n```\n"})
    await emit("messages", "tool_call_demo", {"delta": "\n**工具返回:**\n\n"})
    await emit("messages", "tool_call_demo", {"delta": "- ✅ 安全检查通过\n"})
    await emit("messages", "tool_call_demo", {"delta": "- ⚠️ 幂等性需要补充文档\n"})
    await emit("messages", "tool_call_demo", {"delta": "- ⚠️ 速率限制配置缺失\n"})
    await emit("tasks", "tool_call_demo", {"status": "completed"})
    await emit("updates", "tool_call_demo", {"value": {"tool_called": "openapi_linter"}})

    await emit("done", None, {"status": "done", "result_status": "reviewed"})
    await repo.mark_terminal(run_id, RunStatus.success, result_status="reviewed")
    return run_id


async def main() -> None:
    async with async_session() as session:
        repo = RunRepository(session)
        terminal_run_id = await _seed_terminal_run(repo)
        failed_run_id = await _seed_failed_run(repo)
        markdown_run_id = await _seed_markdown_table_run(repo)
        reasoning_run_id = await _seed_reasoning_run(repo)
        await repo.commit()

    print(f"Seeded terminal run:  {terminal_run_id}")
    print(f"Seeded failed run:    {failed_run_id}")
    print(f"Seeded markdown run:  {markdown_run_id}")
    print(f"Seeded reasoning run: {reasoning_run_id}")


if __name__ == "__main__":
    asyncio.run(main())
