---
name: claude-status-watch
version: 1.0.0
description: Sets up and operates claude-status-watch, which notifies the user (Telegram, ntfy, Discord, Slack, e-mail, desktop or custom command) when status.claude.com reports an incident, and can pause scheduled Claude jobs while their model is affected. Use for "notify me when Claude is down", "set up the Claude status watcher", "pause my jobs during a Claude outage", "is Claude having an incident".
---

# claude-status-watch

Version 1.0.0. Script: `claude_status_watch.py` from the repository https://github.com/RAAAAAGEEEEE/claude-status-watch (default location `~/claude-status-watch`). Documentation: `docs/` of the repository.

## Scope

In scope: install and configure the watcher, test a channel, schedule it (cron, systemd timer, Windows Task Scheduler), set filters, wire the guard into a job launcher, explain an incident message, answer "is Claude down now".
Out of scope: fixing the user's failing jobs, switching models automatically, monitoring other services, calling any Claude API.

## When to trigger

The user asks to be warned about Claude outages or incidents, to set up or change the watcher, to pause or guard scheduled jobs during outages, or asks whether Claude currently has an incident.

## Inputs and outputs

Inputs: chosen channel(s) and their credentials (given by the user, never invented), language, optional component and model filters, optional status file path, scheduler type. Outputs: `~/.claude-status-watch/config.json`, a secrets env file (mode 600), a working schedule, a test message received by the user, and a short report.

## Modes, in this order

1. **Check what exists.** `ls ~/claude-status-watch ~/.claude-status-watch`. If the repository is missing: `git clone https://github.com/RAAAAAGEEEEE/claude-status-watch.git ~/claude-status-watch`. Python 3.9+ needed.
2. **Ask** which channel(s), language (`en` or `fr`), whether to filter by component or model, whether job launchers must pause (then set `status_file`). Offer ntfy (a long random topic name, no account) as the zero-account option. Ask for credentials as an API key or token the user pastes; never print them back.
3. **Write the config** from `examples/config.example.json`, secrets in `~/.claude-status-watch/secrets.env` (`chmod 600`). Back up an existing config with an ISO timestamp suffix first.
4. **Test**: `python3 ~/claude-status-watch/claude_status_watch.py notify-test`, then `check --dry-run --summary-file ~/claude-status-watch/examples/simulated_incident.json`. Ask the user to confirm the message arrived.
5. **Schedule** `check` every 5 minutes with the matching example from `examples/` (read `docs/INSTALLATION.md`). Confirm with `crontab -l` or `systemctl --user list-timers`.
6. **Pause option**: show the `guard` line from `docs/USAGE.md` or `examples/guard-launcher.sh` and add it to the user's launcher only if asked.

## Fallbacks and errors

- Channel error `HTTP error 401/404/400`: wrong or missing token or chat id; re-ask, do not echo secrets.
- Status page unreachable: the script keeps its state and retries at the next run; nothing to fix.
- No scheduler available (for example Windows without PowerShell rights): give the manual command and say so.
- Windows and macOS paths are untested upstream: say so when the user is on those systems.
- Never modify the user's launcher or crontab without saying exactly what will change.

## Evidence levels

Report each step as VERIFIED (command run, output seen), or NOT VERIFIED (not run, say why). A delivered test message is only VERIFIED when the user confirms it.

## Usage

Once installed, the user asks in plain language (examples below); the modes above run in order. Day to day, `python3 ~/claude-status-watch/claude_status_watch.py check --dry-run` shows what would be sent and `guard` answers go or pause.

## Example invocations

- "Notify me on ntfy when Claude has an incident."
- "Set up claude-status-watch with Discord, French messages, only Claude Code."
- "Pause my nightly Sonnet job when Sonnet is affected."

## Example report

```
Channel: ntfy topic (stored in secrets.env)    VERIFIED test message confirmed by user
Schedule: systemd user timer every 5 min       VERIFIED list-timers shows next run
Pause: status file ~/.claude-status-watch/status.json, guard added to launcher   VERIFIED guard prints "go"
```

## Install

Personal: `cp -r ~/claude-status-watch/skill/claude-status-watch ~/.claude/skills/`. Per project: copy to `<project>/.claude/skills/`.

## Security and privacy

Only the public status page and the user's chosen channels are contacted. Secrets stay in the env file, are never printed, and are not committed. See `docs/PRIVACY_AND_SECURITY.md`.

## Versioning, references

Follows the repository version (see `CHANGELOG.md`). Independent project, not affiliated with Anthropic (`docs/LEGAL_AND_ATTRIBUTION.md`).
