# Security

## Secrets

- Groww API keys, TOTP secrets and access tokens go only in `.env`, which is
  git-ignored. Never commit it, paste it into chats or issues, or share
  screenshots of it.
- A TOTP secret is as powerful as your password for API trading. If it leaks,
  revoke the key on Groww's Trading APIs page immediately and create a new one.
- On a shared or cloud machine: `chmod 600 .env` and keep the repo folder in
  your own user account.
- Before pushing: `git status` should never show `.env`, `config.toml` or `state/`.

## Reporting

Found a vulnerability or a bug that could place unintended orders? Don't open
a public issue. Contact Rohit Ghosh privately via GitHub
(@rohit1682) and describe the problem and how to reproduce it.
