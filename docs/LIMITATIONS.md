# Limitations

- **The status page is the provider's declaration.** It can lag behind a real outage, and a problem that is never posted is invisible. It does not replace your own error handling.
- **Model detection is text matching.** An incident that says "elevated errors" without naming a model is treated as affecting all models only if it is `major` or worse on `Claude API` or `Claude Code` (configurable). Wording changes can fool it. The guard errs toward pausing. Negations ("Sonnet is unaffected") are not understood: a title or update that contains a phrase from `all_models_phrases` counts as all models.
- A component added to an incident after it was first reported does not produce an update message.
- **Polling, not push.** With a 5-minute schedule an incident can be reported up to 5 minutes late.
- **No automatic fallback** to another model: the guard only says pause or go.
- **Scheduled maintenance** entries of the status page are ignored.
- **Windows and macOS are untested** by the author: the Task Scheduler script and the desktop notifications for these systems were written from the documentation, not run. Windows has no run lock either.
- **Status page format**: relies on the Atlassian Statuspage JSON API (`/api/v2/summary.json`). If the provider changes its status system, the script needs an update.
- **Messages** exist in English and French only.
- A resolved incident is detected when it leaves the unresolved list; if the script was not running at that moment the end message still comes at the next run, with an approximate duration.
