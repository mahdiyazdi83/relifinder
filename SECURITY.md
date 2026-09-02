# Security Policy

## Supported version

ReliFinder is currently pre-1.0. Security fixes are applied to the latest code on the `main` branch.

## Reporting a vulnerability

Use GitHub's private **Report a vulnerability** form in the repository Security tab. Do not open a public issue for vulnerabilities involving credentials, SQL safety, path traversal, network exposure, or private database metadata.

Include only the minimum sanitized reproduction needed. Never send real Oracle passwords, wallet files, connection descriptors, schema names, reports, logs, sampled values, or customer data.

If private vulnerability reporting is unavailable, open a public issue requesting a private contact channel without including exploit details or sensitive information.

## Security boundary

ReliFinder is designed for local, read-only discovery. Reports and structural metadata can still reveal sensitive database topology. Users should run ReliFinder with a physically SELECT-only Oracle account, keep the GUI bound to loopback, and protect all generated output.