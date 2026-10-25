# Usage

Settings are in [CONFIGURATION](CONFIGURATION.md); installation in [INSTALLATION](INSTALLATION.md).

## Commands

```bash
python3 claude_status_watch.py check [--config FILE] [--dry-run] [--summary-file FILE]
python3 claude_status_watch.py notify-test [--config FILE] [--dry-run]
python3 claude_status_watch.py guard --status-file FILE [--model MODEL] [--max-age MINUTES] [--fail-closed]
```

`check` is the default command when none is given. Exit codes: `check` 0 = ok, 1 = status page unreachable (state unchanged), 2 = configuration error. `guard` 0 = go, 75 = pause, 2 = error (bad arguments or configuration). A launcher that must only pause on 75 tests `[ $? -eq 75 ]`.

`guard` does not read `CSW_CONFIG`; pass `--config` if you changed the model list.

## What triggers a message

| Event | When |
| --- | --- |
| New incident | An unresolved incident appears that was not known |
| Incident update | Its status, impact or detected models changed (for example investigating to monitoring) |
| Incident resolved | A known incident is no longer unresolved; the message carries the final update and the duration |
| Component status change | A component is not operational and no open incident lists it, or it returned to normal |

Remove an event from `notify_on` to silence it. A failed delivery is retried at the next run; the state is only advanced when at least one channel succeeded.

## Filters

`"filters": {"components": ["Claude Code"], "models": ["opus"]}`. Both must match. A component filter matches by substring. A model filter lets through incidents that name that model, incidents that concern all models, and incidents that name no model (they cannot be excluded). The status file used by `guard` is never filtered.

## Pausing job launchers

1. Set `"status_file"` in the config. `check` rewrites it at every successful run.
2. In the launcher call `guard`. With `--model claude-sonnet-5-5` (or just `sonnet`), it exits 75 if that family is affected or if an incident concerns all models. Without `--model`, any affected model pauses. A model id it does not recognise behaves like no model.
3. If the file is missing or older than `--max-age` minutes (default 30), the status is unknown and `guard` lets the job go, unless `--fail-closed`.

Example of a wrapper: [examples/guard-launcher.sh](../examples/guard-launcher.sh). Output of `guard` during an incident:

```
pause: sonnet since 2026-01-01T10:00:00.000Z
```

Status file shape:

```json
{"schema": 1, "checked_at": "2026-10-25T02:04:22+00:00", "ok": false, "indicator": "major",
 "all_models_affected": false, "all_models_since": null,
 "models_affected": {"sonnet": {"since": "2026-01-01T10:00:00.000Z", "incidents": ["sim0000example"]}},
 "incidents": []}
```

(`incidents` holds one object per open incident with id, title, status, impact, components, models, url.)

## Trying it without a real incident

```bash
python3 claude_status_watch.py check --dry-run --summary-file examples/simulated_incident.json
```

`--dry-run` sends nothing and writes no state or status file (it may create the state directory and a lock file). Use a separate `state_file` in a scratch config if you want to run it for real against your channels; set `"message_prefix": "[TEST] "`.
