# Security Rules

These rules are mandatory for every AI assistant and every coding session in this repository.

1. Never commit, stage, or push `.env`, `.env.*`, passwords, API keys, access tokens, session cookies, private keys, or account credentials.
2. Never print or paste secrets into chat replies, logs, diffs, screenshots, commit messages, pull requests, or generated files.
3. Treat personal account details and private contact information as sensitive by default. Do not expose them on the public website or in public repository history.
4. If a secret is found, stop and protect it first:
   - remove it from tracking
   - redact it from outputs
   - warn that the secret must be rotated
   - avoid any commit or push until the exposure risk is addressed
5. `.env.example` may contain placeholder variable names only. It must never contain real values.
6. Before any commit or push, run the repository's secret checks and make sure sensitive files are not tracked.

If there is any doubt, protect privacy first and do not push.
