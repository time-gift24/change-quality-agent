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
