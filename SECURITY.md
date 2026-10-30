# Security policy

## Supported versions

Security fixes are made for the latest release on PyPI.

## Reporting a vulnerability

Please **do not open a public issue**. Report it privately via
[GitHub's private vulnerability reporting](https://github.com/kwpap/pywcif/security/advisories/new).
Include the affected version, a description, and steps to reproduce if possible.

You can expect a first reply within 7 days. Once a fix is released, the advisory is published
with credit to the reporter, unless you prefer to stay anonymous.

## Scope notes

- `fetch_wcif` sends OAuth tokens only over https (or to localhost) and never forwards them on
  redirects. A way around either is a vulnerability.
- Private WCIF documents contain personal data (emails, birthdates). pywcif never writes them
  anywhere you did not ask it to.
