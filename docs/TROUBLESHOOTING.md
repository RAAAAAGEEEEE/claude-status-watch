# Troubleshooting

See [CONFIGURATION](CONFIGURATION.md) and [USAGE](USAGE.md).

| Symptom | Cause and fix |
| --- | --- |
| `notify-test` prints `channel telegram: HTTP error 401` or `404` | Wrong token. Recreate it with BotFather. The log never shows the token |
| `channel telegram: HTTP error 400` | Wrong chat id, or the bot never received a message from you; send it one |
| `failed (ValueError)` | A secret is missing: check the variable name and the `env_file` path |
| No message during a known incident | Run `check --dry-run`; check `notify_on` and `filters`; check cron actually runs (`cron.log`) |
| `fetch failed (...)` in the log | The status page or your network is unreachable. The state is kept, the next run retries |
| Same message again and again | The channel fails for some deliveries only; the state advances only when one channel succeeds |
| `guard` always says `go` | The status file is missing or older than `--max-age` (prints `status unknown or stale`); check that `status_file` is set and `check` runs |
| `guard` pauses forever | An incident is open on the status page, or the status file is older than `--max-age` with `--fail-closed`; compare with the status page and check `checked_at` in the status file |
| `another run is in progress, skipping` | Normal if two runs overlap |
| ntfy title shows `?` | Non-ASCII characters in the title are replaced (HTTP header limit); the body is intact |

To reset everything: delete `state_file` (you will be re-notified of open incidents).
