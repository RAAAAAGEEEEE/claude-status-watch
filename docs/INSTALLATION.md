# Installation

Requires Python 3.9+ and git. See also [USAGE](USAGE.md) and [CONFIGURATION](CONFIGURATION.md).

## 1. Get the code and a config

```bash
git clone https://github.com/RAAAAAGEEEEE/claude-status-watch.git ~/claude-status-watch
mkdir -p ~/.claude-status-watch
cp ~/claude-status-watch/examples/config.example.json ~/.claude-status-watch/config.json
cp ~/claude-status-watch/.env.example ~/.claude-status-watch/secrets.env
chmod 600 ~/.claude-status-watch/secrets.env
```

Edit both files: keep the channels you use, fill their secrets. Then check it works:

```bash
python3 ~/claude-status-watch/claude_status_watch.py notify-test
```

## 2. Schedule `check` every 5 minutes

### Linux or macOS: cron

```bash
crontab -e
```

and add the line from [examples/cron.example](../examples/cron.example).

### Linux: systemd user timer

```bash
mkdir -p ~/.config/systemd/user
cp ~/claude-status-watch/examples/claude-status-watch.service ~/claude-status-watch/examples/claude-status-watch.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now claude-status-watch.timer
systemctl --user list-timers claude-status-watch.timer
```

The unit files assume the clone is in `~/claude-status-watch`.

### Windows: Task Scheduler

Run [examples/windows-task.ps1](../examples/windows-task.ps1) in PowerShell. This script was not run on Windows by the author ([LIMITATIONS](LIMITATIONS.md)).

## Claude Code skill

```bash
mkdir -p ~/.claude/skills
cp -r ~/claude-status-watch/skill/claude-status-watch ~/.claude/skills/
```

Per project instead of personal: copy it to `<project>/.claude/skills/` instead. Then ask Claude Code: "set up claude-status-watch". The skill asks which channel you want, writes the config, runs the test message and installs the schedule.

## Update and uninstall

Update: `git -C ~/claude-status-watch pull`. Uninstall: remove the cron line or timer, then `rm -rf ~/claude-status-watch ~/.claude-status-watch`.
