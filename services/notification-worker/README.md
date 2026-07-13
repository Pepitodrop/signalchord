# notification-worker

Consumes `notification.requested.v1`, claims tenant-authorized encrypted device endpoints through the Rails control plane and delivers minimized Expo push payloads. A per-event/per-endpoint delivery ledger prevents ordinary replay duplicates; failed sends remain retryable and auditable.
