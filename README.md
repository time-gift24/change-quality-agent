# Change Quality Agent

Change Quality Agent provides the backend substrate for running SOP quality
checks and observing their progress.

## Capabilities

- Starts SOP quality runs from a mocked SOP source in v1.
- Persists run history and durable run events in Postgres.
- Exposes generic run observation so clients can inspect status without
  depending on SOP-specific fields.
- Streams persisted run events for replay and progress observation.
- Uses an in-process v1 runner while worker leases, checkpoint resume, and the
  real SOP client remain future integration points.
- Manages MCP server configuration and stdio runtime lifecycle behind the
  `X-MCP-Admin-Token` header. Set `mcp_admin_token`, allow commands with
  `mcp_allowed_stdio_commands`, pin launchable command/first-arg pairs with
  `mcp_allowed_stdio_specs` such as `uvx:mcp-server-filesystem`, and only set
  `mcp_runtime_single_instance=true` when the API is deployed as a single
  process owning MCP child processes.
