# Contributing

Issues and pull requests are welcome.

- Python 3.9+, standard library only: please do not add dependencies.
- Run the tests before opening a pull request: `python3 -W error::ResourceWarning -m unittest discover -s tests -v`
- A behaviour change updates the relevant file in `docs/` and `CHANGELOG.md` in the same commit.
- A new notification channel needs: a `send_*` function, a branch in `notify()`, a test against the local HTTP sink in `tests/test_claude_status_watch.py`, and a section in [docs/CONFIGURATION.md](docs/CONFIGURATION.md).
- Never commit a real token, webhook URL, e-mail address or chat id. Use placeholders such as `YOUR_TOKEN`.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the script is organised.
