# Security policy

## Supported versions

SignalChord is currently an alpha project. Only the latest commit on the default branch receives security fixes.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities in a public issue. Use GitHub private vulnerability reporting from the repository **Security** tab when it is enabled, or email [ich@luisbenedikt.de](mailto:ich@luisbenedikt.de) with the subject `SignalChord security report`.

Include affected components, reproduction steps, impact and any proposed mitigation. Please allow a reasonable investigation window before public disclosure. Reports involving exposed credentials, tenant isolation, SSRF, source-policy bypass, injection, authentication, encryption or destructive data access are treated as high priority.

## Operational scope

Example credentials and open host ports in Docker Compose are for local development only. They are not a supported production configuration. Production operators must use external secret management, encrypted transport, least-privilege identities, network isolation, backups and an incident-response process.
