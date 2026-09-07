# Security policy

## Reporting

Do not open a public issue containing an unpatched vulnerability, secret, private diff or customer data. Contact the repository owner privately and include affected commit, reproduction, impact and a minimal proposed mitigation. No response-time SLA is currently promised.

## Deployment baseline

- Enable `DIFFPRISM_AUTH_REQUIRED` before exposing any non-health endpoint.
- Generate a random auth secret and use a strong bootstrap password.
- Grant GitHub tokens only the repository and Contents/Pull requests permissions required by the enabled feature.
- Verify webhook HMAC signatures and keep webhook and session secrets separate.
- Terminate TLS at a trusted reverse proxy and expose only required paths.
- Treat PR content, model output and Review Pack files as untrusted.
- Scope model credentials and repair commands to an isolated worker account/container.
- Keep PostgreSQL, Redis and OpenTelemetry endpoints on private networks with authentication.
- Review diagnostic exports before sharing; they can contain diff and model context.

## Known boundaries

DiffPrism validates tool schemas and repository paths, but it is not a security sandbox for arbitrary repositories, Skill content or operator-configured shell test commands. LLM evidence is not proof by itself. The Evidence Examiner reduces unsupported findings but does not eliminate false positives or false negatives. Automatic fixes use a new branch and verification gate; operators must still review them before merge.

The bundled benchmark is synthetic and is not a security certification.
