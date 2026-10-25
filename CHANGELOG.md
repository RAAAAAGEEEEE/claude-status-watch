# Changelog

## 1.0.0 (2026-10-25)

First release.

- `check`: reads the Claude status page summary, notifies on new incident, incident update, resolution and standalone component status change; no duplicates (state kept between runs); a message that could not be delivered is retried on the next run.
- Channels: Telegram, ntfy, Discord webhook, Slack webhook, e-mail (SMTP), desktop notification, custom command.
- Filters by component and by model; English and French messages.
- Optional status file listing the affected models and since when, and `guard` subcommand (exit code 75 = pause) for job launchers.
- Examples: cron, systemd timer, Windows Task Scheduler, guard for a shell launcher.
- Claude Code skill `claude-status-watch` that sets everything up.
