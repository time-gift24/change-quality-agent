# 项目法则（严格遵守）

- 禁止在 main 分支路径中有任何代码操作
- 改动不分大小，均需新建 git worktree

## 谨记技能！！！
- using-git-worktrees

## 本地 Skill 准备（必须）

- 本仓库不再提交 `.agents/` 中的 skill 内容，`.agents/` 仅用于本地 agent/Codex 环境。
- 开始开发前，先在本机增加项目需要的 skills；至少确认 `using-git-worktrees`、`fastapi`、`project-structure` 可用。
- 前端相关任务按需增加 React/Vercel/Web UI 相关 skills。
- 不要提交 `.agents/` 或 `skills-lock.json`。

# 项目结构

| 目录 | 说明 |
|------|------|
| `backend/` | Python 后端（FastAPI） |
| `frontend/` | React 前端 |
| `api/` | API 契约文档（OpenAPI/AsyncAPI spec、接口约定） |

**重要**: `api/` 为共享文档目录，backend 和 frontend 均应遵守其中定义的接口契约。

# 开发指南

## 设计与检视原则(非常重要)
- YAGNI（You Ain't Gonna Need It，你不会需要它）
- KISS (Keep It Simple and Stupid，尽可能保持简单)
- DRY (Don't Repeat Yourself，禁止重复你自身)

# 后端开发指南

- 遵守 python 的[规则](./rules/python)
- 每个文件行数不得超过 1000 行
