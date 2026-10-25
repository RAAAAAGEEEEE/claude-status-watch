# Architecture

Single file, [claude_status_watch.py](../claude_status_watch.py), standard library only. Configuration: [CONFIGURATION](CONFIGURATION.md).

```
status.claude.com/api/v2/summary.json
        |  fetch_json
        v
 analyse_incident  -> models, components, "all models" flag
        |
        v   compare with state_file (previous run)
   events: new / update / resolved / component
        |  passes_filters -> format_message -> notify -> channels
        v
 state_file (atomic write)         status_file (atomic write) <- guard reads it
```

- **Source**: the Atlassian Statuspage `summary.json` lists components and unresolved incidents with their updates. For a resolved incident the script also fetches `/api/v2/incidents/<id>.json` to get the final update and duration; if that fails the end message is still sent.
- **Model detection**: whole words from `models` searched in the incident title; if none, in the updates. Phrases from `all_models_phrases`, or an unnamed incident of sufficient impact on `all_models_components`, mark "all models".
- **State**: per incident a signature (status, impact, models). A change of signature is an update. The state is only advanced after a successful delivery, so a missed message is retried.
- **Locking**: `fcntl` lock on `<state_file>.lock` so overlapping runs skip (not available on Windows).
- **Guard**: reads only the status file; it never touches the network.

Tests: `tests/test_claude_status_watch.py` runs the real script against a local HTTP server standing in for Telegram, ntfy, Discord and Slack.
