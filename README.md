# Change Quality Agent

## 本地 Skill 准备

本仓库不再提交 `.agents/` 目录中的 skill 实现；该目录只作为本地 agent/Codex 环境配置使用。

开始开发或运行 agent 前，请先在本机增加项目需要的 skills，再进行代码改动。当前项目至少需要关注：

- `using-git-worktrees`
- `fastapi`
- `project-structure`

如果参与前端相关工作，请按任务需要补充 React/Vercel/Web UI 相关 skills。缺失的 skill 请从团队共享来源或个人 skill 库安装到本地环境，避免把 `.agents/` 或 `skills-lock.json` 提交到仓库。
