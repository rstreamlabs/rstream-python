# Security

Report security issues privately through the rstream project maintainers.

Do not include authentication tokens, webhook signing secrets, private keys, or
customer endpoint URLs in public issues.

The SDK avoids logging secrets and refuses ambiguous credential reuse when an
explicit engine override is configured.

