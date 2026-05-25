---
name: project-structure
description: Use when adding, moving, or reviewing code in this FastAPI + LangGraph agent project, especially API routes, schemas, config, security, dependencies, graph state, graph assembly, nodes, routers, prompts, tools, tests, environment files, or Docker/deployment files.
---

# Project Structure

## Core Rule

Keep the web API layer and the LangGraph agent layer separate. Before creating or editing files, place each change in the directory below. If a requested change does not fit, stop and explain the closest compliant location instead of inventing a new top-level layout.

## Required Layout

```text
app/
  __init__.py
  main.py
  api/
    __init__.py
    deps.py
    v1/
      __init__.py
      agent.py
      auth.py
  core/
    __init__.py
    config.py
    security.py
  schemas/
    __init__.py
    agent.py

agent/
  __init__.py
  state.py
  graph.py
  nodes/
    __init__.py
    llm_node.py
    tool_node.py
  edges/
    __init__.py
    routers.py
  prompts/
    __init__.py
    system_prompts.py
  tools/
    __init__.py
    web_search.py
    db_query.py

tests/
  __init__.py
  test_api.py
  test_agent.py

.env.example
.gitignore
README.md
pyproject.toml
Dockerfile
```

## Placement Rules

| Change type | Location |
| --- | --- |
| FastAPI app creation, lifespan, middleware, router registration | `app/main.py` |
| HTTP endpoints for agent invocation, streaming, auth, or versioned API | `app/api/v1/` |
| FastAPI dependencies such as database clients, Redis clients, request-scoped services | `app/api/deps.py` |
| Environment and application settings | `app/core/config.py` |
| Auth, password hashing, token, encryption, and security helpers | `app/core/security.py` |
| Request and response models for HTTP APIs | `app/schemas/` |
| LangGraph state structure | `agent/state.py` |
| LangGraph graph assembly and `compile()` | `agent/graph.py` |
| Graph node implementations | `agent/nodes/` |
| Conditional routing and edge decisions | `agent/edges/routers.py` |
| Prompt templates and system prompts | `agent/prompts/` |
| Tools callable by the agent | `agent/tools/` |
| API behavior tests | `tests/test_api.py` |
| Agent graph/state/node tests | `tests/test_agent.py` |

## Boundaries

- Do not put LangGraph business logic inside FastAPI route files. Routes should validate input, call the graph/service, and shape HTTP responses.
- Do not put HTTP request or response schemas inside `agent/`. Agent code should be reusable without FastAPI.
- Do not put config reads throughout the codebase. Centralize them in `app/core/config.py`.
- Do not commit `.env`. Commit `.env.example` for documented variables.
- Do not use mixed-case Python module names. Use `tool_node.py`, not `Tool_node.py`.
- Do not turn root `main.py` into the application. The FastAPI entrypoint belongs in `app/main.py`.

## Adding New Code

1. Identify whether the change is web/API behavior, agent/domain behavior, shared configuration, or tests.
2. Use the required layout and placement table before creating any file.
3. Pair this skill with the FastAPI skill when touching FastAPI or Pydantic code.
4. Add or update tests in `tests/` for any new behavior.
5. If the current repository has legacy files outside this layout, prefer migrating toward this structure in the same change when it is low risk; otherwise leave a clear note.
