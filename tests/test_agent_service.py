import pytest

from app.schemas.agents import AgentCreate, AgentDraftConfig, AgentDraftUpdate


def service_type():
    try:
        from app.services.agents import AgentService
    except ModuleNotFoundError as exc:
        pytest.fail(f"Agent service module is missing: {exc}")
    return AgentService


def draft_config() -> AgentDraftConfig:
    return AgentDraftConfig(
        system_prompt="You are careful.",
        model="openai:gpt-5-mini",
        model_config={"temperature": 0},
        tool_allowlist=["search_sop"],
        mcp_server_ids=["change-docs"],
    )


class FakeRepository:
    def __init__(self) -> None:
        self.created_kwargs: dict[str, object] | None = None
        self.updated_key: str | None = None
        self.updated_kwargs: dict[str, object] | None = None
        self.published_key: str | None = None
        self.deleted_key: str | None = None
        self.created_agent = object()
        self.updated_agent = object()
        self.published_version = object()
        self.deleted_agent = object()

    async def create_agent(self, **kwargs):
        self.created_kwargs = kwargs
        return self.created_agent

    async def update_draft(self, key: str, **kwargs):
        self.updated_key = key
        self.updated_kwargs = kwargs
        return self.updated_agent

    async def publish_agent(self, key: str):
        self.published_key = key
        return self.published_version

    async def soft_delete(self, key: str):
        self.deleted_key = key
        return self.deleted_agent


@pytest.mark.asyncio
async def test_create_agent_delegates_request_fields_and_commits() -> None:
    AgentService = service_type()
    repository = FakeRepository()
    commit_count = 0

    def commit() -> None:
        nonlocal commit_count
        commit_count += 1

    service = AgentService(repository=repository, commit=commit)
    request = AgentCreate(
        key="release-reviewer",
        display_name="Release Reviewer",
        description="Checks release quality",
        draft=draft_config(),
    )

    result = await service.create_agent(request)

    assert result is repository.created_agent
    assert repository.created_kwargs == {
        "key": "release-reviewer",
        "display_name": "Release Reviewer",
        "description": "Checks release quality",
        "draft": request.draft,
    }
    assert commit_count == 1


@pytest.mark.asyncio
async def test_update_draft_omits_unset_description_from_repository_call() -> None:
    AgentService = service_type()
    repository = FakeRepository()
    service = AgentService(repository=repository)

    result = await service.update_draft(
        "release-reviewer",
        AgentDraftUpdate(display_name="Renamed Reviewer"),
    )

    assert result is repository.updated_agent
    assert repository.updated_key == "release-reviewer"
    assert repository.updated_kwargs == {"display_name": "Renamed Reviewer"}


@pytest.mark.asyncio
async def test_update_draft_passes_explicit_null_description_to_repository() -> None:
    AgentService = service_type()
    repository = FakeRepository()
    service = AgentService(repository=repository)

    await service.update_draft(
        "release-reviewer",
        AgentDraftUpdate(description=None),
    )

    assert repository.updated_kwargs == {"description": None}


@pytest.mark.asyncio
async def test_update_draft_awaits_async_commit() -> None:
    AgentService = service_type()
    repository = FakeRepository()
    commit_steps: list[str] = []

    async def commit() -> None:
        commit_steps.append("committed")

    service = AgentService(repository=repository, commit=commit)

    await service.update_draft(
        "release-reviewer",
        AgentDraftUpdate(enabled=False),
    )

    assert repository.updated_kwargs == {"enabled": False}
    assert commit_steps == ["committed"]


@pytest.mark.asyncio
async def test_publish_agent_delegates_and_commits() -> None:
    AgentService = service_type()
    repository = FakeRepository()
    commit_count = 0

    def commit() -> None:
        nonlocal commit_count
        commit_count += 1

    service = AgentService(repository=repository, commit=commit)

    result = await service.publish_agent("release-reviewer")

    assert result is repository.published_version
    assert repository.published_key == "release-reviewer"
    assert commit_count == 1


@pytest.mark.asyncio
async def test_delete_agent_delegates_and_commits() -> None:
    AgentService = service_type()
    repository = FakeRepository()
    commit_count = 0

    def commit() -> None:
        nonlocal commit_count
        commit_count += 1

    service = AgentService(repository=repository, commit=commit)

    result = await service.delete_agent("release-reviewer")

    assert result is repository.deleted_agent
    assert repository.deleted_key == "release-reviewer"
    assert commit_count == 1
