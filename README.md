# claude-status-watch

Get a message when [status.claude.com](https://status.claude.com) reports an incident, and optionally pause your own scheduled Claude jobs while the model they use is affected.

**Status: stable 1.0.0**, used in production by its author on Linux. The Windows and macOS parts are untested (see [docs/LIMITATIONS.md](docs/LIMITATIONS.md)).

## Problem and audience

If you run Claude Code or the Claude API from scripts, cron jobs or overnight queues, an outage makes those jobs fail silently or burn quota on retries. This tool is for developers and solo operators who want to be told, on the channel they already use, and who want their job launcher to wait.

## What it does

- Polls the public status page every few minutes (no Claude token, no account, standard-library Python only).
- Sends one message per new incident, per status change and per resolution (no duplicates), with the components, the models named (Opus, Sonnet, Haiku, Fable), and a link.
- Channels: Telegram, ntfy, Discord, Slack, e-mail (SMTP), desktop notification, or any command.
- Filters by component and by model.
- Optional status file plus a `guard` command so a job launcher pauses while its model is affected (exit code 75).

Example message (from the simulated incident in [examples/simulated_incident.json](examples/simulated_incident.json)):

```
New incident: Elevated errors on Claude Sonnet
Impact: major
Status: investigating
Components: Claude API (api.anthropic.com)
Models: Sonnet
Details: We are investigating elevated errors on Claude Sonnet.
https://status.claude.com/incidents/sim0000example
```

## Prerequisites

Python 3.9 or later and git. Nothing else to install.

## Quickstart

```bash
git clone https://github.com/RAAAAAGEEEEE/claude-status-watch.git ~/claude-status-watch
mkdir -p ~/.claude-status-watch
cp ~/claude-status-watch/examples/config.example.json ~/.claude-status-watch/config.json
# edit the config (see docs/CONFIGURATION.md for the other channels) and put the secrets in ~/.claude-status-watch/secrets.env
cp ~/claude-status-watch/.env.example ~/.claude-status-watch/secrets.env && chmod 600 ~/.claude-status-watch/secrets.env
python3 ~/claude-status-watch/claude_status_watch.py notify-test    # sends a test message
python3 ~/claude-status-watch/claude_status_watch.py check --dry-run --summary-file ~/claude-status-watch/examples/simulated_incident.json
```

The last command prints what an incident message looks like, sends nothing and writes no state. Then schedule `check` every 5 minutes: [cron, systemd timer or Windows](docs/INSTALLATION.md).

With Claude Code you can instead install the skill and ask "set up claude-status-watch": see [docs/INSTALLATION.md](docs/INSTALLATION.md#claude-code-skill).

## Pausing your own jobs

Set `"status_file"` in the config, then in your launcher:

```bash
python3 ~/claude-status-watch/claude_status_watch.py guard --status-file ~/.claude-status-watch/status.json --model claude-sonnet-5-5 || exit 75
```

A launcher that must pause only on code 75 (and ignore guard errors) tests `[ $? -eq 75 ]`. A complete wrapper is in [examples/guard-launcher.sh](examples/guard-launcher.sh). Details: [docs/USAGE.md](docs/USAGE.md).

## Architecture in short

One Python file with three commands (`check`, `guard`, `notify-test`). `check` fetches `summary.json`, compares it with the state kept from the previous run, notifies on differences, and writes the optional status file. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Configuration

One JSON file (`~/.claude-status-watch/config.json`, or `--config`, or the `CSW_CONFIG` variable). Secrets are read from environment variables or an env file, never stored in the config. All keys: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Security and privacy

The script only makes outbound requests: to the status page and to the channels you configure. Nothing about you or your machine is sent to the status page beyond a `User-Agent`. See [docs/PRIVACY_AND_SECURITY.md](docs/PRIVACY_AND_SECURITY.md).

## Limits

The status page is the provider's own declaration: an incident can start before it is posted, and a problem that never gets posted is invisible here. Model detection reads incident titles and updates as text. Full list: [docs/LIMITATIONS.md](docs/LIMITATIONS.md). Problems: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Roadmap (non-binding)

Possible later: more languages for messages, a per-channel filter, a Windows-tested installer.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security reports: [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE). Independent project, not affiliated with Anthropic: [docs/LEGAL_AND_ATTRIBUTION.md](docs/LEGAL_AND_ATTRIBUTION.md).

Documentation: [Installation](docs/INSTALLATION.md) · [Usage](docs/USAGE.md) · [Configuration](docs/CONFIGURATION.md) · [Architecture](docs/ARCHITECTURE.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Limitations](docs/LIMITATIONS.md) · [Privacy and security](docs/PRIVACY_AND_SECURITY.md) · [Changelog](CHANGELOG.md)
