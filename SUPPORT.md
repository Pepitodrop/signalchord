# Community support

SignalChord is a personal open-source project maintained on a best-effort basis. There is no paid support plan, uptime guarantee or guaranteed response time.

## Where to ask for help

- Use GitHub Discussions when enabled for setup questions, architecture discussion and general ideas.
- Use a GitHub issue for reproducible bugs or focused feature requests.
- Use the security process in `SECURITY.md` for vulnerabilities. Do not disclose security issues publicly.

Before opening an issue, search existing issues and include:

- SignalChord version or commit SHA;
- operating system, CPU architecture, Docker and Kubernetes versions;
- deployment method and relevant non-secret configuration;
- exact reproduction steps;
- expected and observed behavior;
- sanitized logs and health-check output.

## Supported scope

Before `v1.0.0`, only the latest `main` branch is actively maintained. After `v1.0.0`, the current stable release and the latest `main` branch are the intended support targets.

The supported self-hosting target is a single-owner Linux server running Docker Engine and a lightweight Kubernetes distribution such as k3s. Other platforms are welcome when contributors can reproduce and maintain them.

## Out of scope

The project does not provide contractual support, managed hosting, custom source licences, legal advice, paid-provider setup, data recovery guarantees or security certification. Community contributions for additional deployment targets remain welcome.
