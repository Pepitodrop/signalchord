# Rails control plane

This boundary owns users, organizations, workspaces, RBAC, API tokens, source policies, watchlists, investigations, policies, review queues, billing, usage, notifications, feature flags and audit metadata.

The repository currently includes the domain/outbox contract and boot files; generate the full Rails 8 application in Stage 2 and retain these invariants:

- PostgreSQL is transactional source of truth.
- Graph facts are never mirrored into relational tables.
- Domain events are inserted into `outbox_events` in the same database transaction.
- Sidekiq is limited to control-plane jobs; Kafka owns streaming workflows.
- Every query and mutation is tenant scoped and authorized.
