# Product Operations Readiness

SignalChord is not production-ready for customer launch until the release checklist is complete. This document records repository-side controls for issue #32 and the external evidence that still must be attached before the issue can close.

## Repository-Side Controls

- Invitation onboarding: tenant owners and admins can create and revoke invitations. Accepted invitations create or attach a user, create an enabled tenant membership, audit the acceptance, and return a scoped session token without exposing token digests.
- Session management: authenticated users can list their own active tenant sessions and revoke the current or selected session. Membership suspension revokes that tenant member's active API tokens.
- RBAC administration: tenant owners and admins can list and update memberships. The API prevents removal or demotion of the last enabled owner.
- Account suspension: disabled memberships cannot log in or continue using existing user-scoped tokens. Global disabled users remain blocked.
- Usage and billing guardrails: tenant-local usage limits cover sources, watchlists and notification endpoints. Non-writable billing states block write paths without affecting other tenants.
- Support intake: tenant-scoped support tickets record category, severity, status, contact email and audit events. Only tenant owners and admins can update ticket status.
- Notification failure handling: provider invalid-token failures disable only the affected tenant endpoint; transient failures remain recorded on the delivery for retry and investigation.
- Export and deletion: authenticated governance request APIs for tenant export, tenant deletion and source takedown remain the repository-side evidence for customer export/deletion workflows.

Machine-readable evidence is in `product/readiness-checklist.json` and is validated by `scripts/validate_product_readiness.py`.

## External Blockers

The following launch requirements cannot be completed truthfully from repository code alone:

- Production email delivery: verified domains/senders, bounce and complaint handling, recovery email templates, provider outage tests and delivery logs.
- MFA decision and provider: product/security decision, enrollment and recovery flows, provider configuration and customer-facing instructions.
- Mobile signing and push credentials: store signing assets, push credentials and real device validation for invalid-token and provider outage behavior.
- Billing provider integration: contracted provider, payment-state webhooks, metering reconciliation and approved cost-control behavior.
- Terms, privacy and acceptable use: approved customer-facing legal materials, source responsibility terms, support scope and security contact process.
- Representative customer acceptance: staging journey from invitation/signup through source/watchlist setup, article-to-alert delivery, administration, export, suspension and deletion.

Issue #32 should remain open until these artifacts exist for the exact release candidate.
