# Security policy

This is an experimental local pilot, not a hardened multi-tenant service.
Bind to loopback. Do not expose the API publicly without authentication,
authorization, rate limiting, request-size limits, TLS, and database isolation.

Never commit credentials, API keys, paid datasets, restricted research, personal
financial information, or private user data. Use environment variables. `.env`
is ignored; `.env.example` contains no credentials. Logs must not include API keys
or authenticated request URLs.

Only redistribute data with explicit permission. Source licensing must be tracked
separately from the software license. Synthetic fixtures are safe demonstrations,
not substitutes for licensed live datasets.

Report vulnerabilities using GitHub's private vulnerability reporting feature
if enabled, or contact maintainers privately through GitHub. Do not post exploit
details or secrets in public issues. If a secret is exposed, revoke it immediately;
deleting a file does not remove it from Git history.

No production support or response-time guarantee is offered during the pilot.
