# Security Policy

Shinobi is proprietary software. We take the security of the app and our users'
data seriously.

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Instead, report them
privately to the maintainer and allow reasonable time for a fix before any public
disclosure.

Include, where possible:
- A description of the issue and its impact
- Steps to reproduce
- Affected endpoint, file, or component

## Scope

Areas of particular interest:
- Authentication and session handling (`auth/`)
- OAuth token storage (`auth/db.py`)
- File upload and media processing (`/upload`, `/url`, `pipeline/`)
- Any endpoint that reads or writes user data

## Handling of secrets

- Never commit `.env`, `users.db`, `tokens.db`, or API keys.
- User uploads and generated media (`uploads/`, `output/`, `static/brand/`,
  `static/avatars/`) are gitignored and must never be committed.
