# Configuration

JSON file read from `--config`, else the `CSW_CONFIG` environment variable, else `~/.claude-status-watch/config.json`. Keys starting with `_` are ignored (use them for comments). Placeholders for secrets: [.env.example](../.env.example). See also [USAGE](USAGE.md).

## Top-level keys

| Key | Default | Meaning |
| --- | --- | --- |
| `language` | `en` | Message language: `en` or `fr` |
| `source_url` | `https://status.claude.com/api/v2/summary.json` | Status API (Atlassian Statuspage format); a local path also works |
| `state_file` | `~/.claude-status-watch/state.json` | Memory between runs (no duplicates) |
| `status_file` | none | If set, written at each successful run for `guard` |
| `message_prefix` | empty | Text added before every title, for example `[TEST] ` |
| `models` | `opus, sonnet, haiku, fable` | Words searched in titles and updates to detect models |
| `filters.components` | empty | Substrings; empty = all components |
| `filters.models` | empty | Model words; empty = all models |
| `notify_on` | all four events | Subset of `new`, `update`, `resolved`, `component` |
| `all_models_components` | `Claude API`, `Claude Code` | An incident naming no model on one of these, at the impact below, counts as affecting all models |
| `all_models_min_impact` | `major` | `minor`, `major` or `critical` |
| `all_models_phrases` | `all models`, `every model`, ... | Phrases in the incident text meaning all models |
| `channels` | empty | List of channels; none = messages printed to stdout |

## Secrets

For each secret `x` of a channel, write either `"x_env": "VARIABLE_NAME"` (read from the process environment, then from the channel's `"env_file"`) or, discouraged, the literal `"x": "value"`. An env file has lines `NAME=value`, `#` comments allowed.

## Channels

Every channel has `"type"`. A failing channel does not stop the others.

| Type | Keys |
| --- | --- |
| `telegram` | `token_env`, `chat_env`, optional `thread_env` (topic id), `env_file`, `api_base` |
| `ntfy` | `topic`, optional `server` (default `https://ntfy.sh`), `token_env`, `priority` (1 to 5). Anyone who knows the topic name can read it: use a long random one |
| `discord` | `webhook_env` (or `webhook`) |
| `slack` | `webhook_env` (or `webhook`) |
| `email` | `host`, `port`, `security` (`starttls` default, `ssl`, `none`), `from`, `to` (string or list), `user_env`, `password_env` |
| `desktop` | none. Linux `notify-send`, macOS `osascript`, Windows PowerShell balloon |
| `command` | `argv` (list, or a string split like a shell). Receives `CSW_TITLE`, `CSW_BODY`, `CSW_EVENT`, `CSW_URL` in its environment and the message on stdin. No shell is used |

Examples:

```json
{"type": "ntfy", "topic": "YOUR-LONG-RANDOM-TOPIC"}
{"type": "discord", "webhook_env": "DISCORD_WEBHOOK_URL", "env_file": "~/.claude-status-watch/secrets.env"}
{"type": "email", "host": "smtp.example.com", "from": "alerts@example.com", "to": ["me@example.com"],
 "user_env": "SMTP_USER", "password_env": "SMTP_PASSWORD", "env_file": "~/.claude-status-watch/secrets.env"}
{"type": "command", "argv": ["/usr/local/bin/my-hook"]}
```

### Getting Telegram credentials

Create a bot with [@BotFather](https://t.me/BotFather) (it gives the token), send it a message, then read your chat id from `https://api.telegram.org/bot<TOKEN>/getUpdates` (replace `<TOKEN>`; do not share that URL).
