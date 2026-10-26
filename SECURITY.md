# Security Policy

## Reporting a vulnerability

Please report vulnerabilities **privately** using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
(the repository's *Security* tab → *Report a vulnerability*). Do not open a public issue for security problems.

Include a description, reproduction steps and the affected version. You can expect an acknowledgement within a
reasonable time; fixes are released as soon as practical.

## Handling of private data

Never attach real chat exports, phone numbers or names to issues, pull requests or reports. Use synthetic text.

## Scope

See [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) for scope, mitigations and known residual risks. In particular, the
local API has no authentication and must only be bound to `127.0.0.1`.

## Supported versions

Only the latest release on the default branch receives security fixes.
