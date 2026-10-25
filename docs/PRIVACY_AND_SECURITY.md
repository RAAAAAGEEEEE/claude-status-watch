# Privacy and security

See also [SECURITY.md](../SECURITY.md) and [CONFIGURATION](CONFIGURATION.md).

## What leaves your machine

- To `status.claude.com`: an HTTPS GET with the `User-Agent` `claude-status-watch/<version>`. Nothing else.
- To each channel you configure: the message (incident title, components, models, public update text, link). The destination sees your token or webhook, as with any such integration.
- Nothing else. No telemetry, no analytics, no call to any Claude API, no account.

## Secrets

- Read from environment variables or an env file, referenced by name in the config. Keep the env file `chmod 600` and out of git (`.gitignore` excludes `.env` and `config.json`).
- Never written to the logs: on a delivery error only the channel type and the HTTP status code or the exception class are logged, never the URL (a Telegram URL contains the token).
- The state and status files contain only public incident information.

## Hardening notes

- The `command` channel runs the program you name with no shell.
- Choose a long random ntfy topic: the name is the only protection of a public ntfy.sh topic.
- The status file is world-readable (0644) on purpose, so other users' launchers can read it; it holds no secret.
