"""Tests for claude_status_watch (standard library only). Run: python3 -m unittest discover -s tests -v"""
import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import claude_status_watch as csw  # noqa: E402

SECRET = "SECRET-TOKEN-123"


def read_text(path):
    with open(path) as f:
        return f.read()


def read(path):
    return json.loads(read_text(path))


def summary(incidents=(), components=None):
    return {
        "page": {"url": "https://status.example.test"},
        "status": {"indicator": "major" if incidents else "none"},
        "components": components or [
            {"name": "claude.ai", "status": "operational"},
            {"name": "Claude API (api.anthropic.com)", "status": "operational"},
            {"name": "Claude Code", "status": "operational"},
        ],
        "incidents": list(incidents),
    }


def incident(iid="i1", name="Elevated errors on Claude Sonnet", status="investigating", impact="major",
             comps=("Claude API (api.anthropic.com)",), body="We are investigating."):
    return {"id": iid, "name": name, "status": status, "impact": impact,
            "started_at": "2026-01-01T10:00:00.000Z",
            "components": [{"name": c} for c in comps],
            "incident_updates": [{"id": "u", "status": status, "body": body, "affected_components": None}]}


class Sink(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        Sink.received.append((self.path, dict(self.headers), self.rfile.read(n).decode()))
        self.send_response(Sink.status_code)
        self.end_headers()

    def log_message(self, *a):
        pass


Sink.status_code = 200


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.state = os.path.join(self.dir, "state.json")
        self.status = os.path.join(self.dir, "status.json")
        self.summary = os.path.join(self.dir, "summary.json")
        Sink.received = []
        Sink.status_code = 200
        self.server = HTTPServer(("127.0.0.1", 0), Sink)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def config(self, **over):
        cfg = {"state_file": self.state, "status_file": self.status, "channels": [
            {"type": "telegram", "token": SECRET, "chat": "42", "api_base": self.base}]}
        cfg.update(over)
        path = os.path.join(self.dir, "config.json")
        with open(path, "w") as f:
            json.dump(cfg, f)
        return path

    def run_check(self, data, cfg_path):
        with open(self.summary, "w") as f:
            json.dump(data, f)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = csw.main(["check", "--config", cfg_path, "--summary-file", self.summary])
        return code, out.getvalue()


class TestCheck(Base):
    def test_new_update_resolved_no_duplicates(self):
        cfg = self.config()
        self.run_check(summary([incident()]), cfg)
        self.assertEqual(len(Sink.received), 1)
        self.assertIn(f"/bot{SECRET}/sendMessage", Sink.received[0][0])
        text = json.loads(Sink.received[0][2])["text"]
        self.assertIn("Sonnet", text)
        self.assertIn("https://status.example.test/incidents/i1", text)
        self.run_check(summary([incident()]), cfg)  # same state: no duplicate
        self.assertEqual(len(Sink.received), 1)
        self.run_check(summary([incident(status="monitoring")]), cfg)
        self.assertEqual(len(Sink.received), 2)
        self.assertIn("Incident update", json.loads(Sink.received[1][2])["text"])
        self.run_check(summary([]), cfg)
        self.assertEqual(len(Sink.received), 3)
        self.assertIn("Incident resolved", json.loads(Sink.received[2][2])["text"])
        self.run_check(summary([]), cfg)
        self.assertEqual(len(Sink.received), 3)

    def test_secret_never_logged(self):
        Sink.status_code = 500
        code, out = self.run_check(summary([incident()]), self.config())
        self.assertNotIn(SECRET, out)
        self.assertIn("HTTP error 500", out)

    def test_failed_delivery_is_retried(self):
        cfg = self.config()
        Sink.status_code = 500
        self.run_check(summary([incident()]), cfg)
        Sink.status_code = 200
        Sink.received = []
        self.run_check(summary([incident()]), cfg)
        self.assertEqual(len(Sink.received), 1)

    def test_status_file_models_and_since(self):
        self.run_check(summary([incident()]), self.config())
        st = read(self.status)
        self.assertEqual(list(st["models_affected"]), ["sonnet"])
        self.assertEqual(st["models_affected"]["sonnet"]["since"], "2026-01-01T10:00:00.000Z")
        self.assertFalse(st["ok"])
        self.assertFalse(st["all_models_affected"])

    def test_unnamed_major_on_api_affects_all_models(self):
        inc = incident(name="Elevated errors", body="We are investigating.")
        self.run_check(summary([inc]), self.config())
        st = read(self.status)
        self.assertTrue(st["all_models_affected"])

    def test_unnamed_minor_does_not_affect_all(self):
        inc = incident(name="Slow dashboard", impact="minor", comps=("claude.ai",))
        self.run_check(summary([inc]), self.config())
        self.assertFalse(read(self.status)["all_models_affected"])

    def test_other_models_phrase(self):
        inc = incident(name="Errors on Claude Fable", body="Errors on all Claude models.", impact="minor")
        self.run_check(summary([inc]), self.config())
        self.assertTrue(read(self.status)["all_models_affected"])

    def test_component_filter(self):
        cfg = self.config(filters={"components": ["Claude Code"]})
        self.run_check(summary([incident()]), cfg)
        self.assertEqual(Sink.received, [])
        self.run_check(summary([incident(iid="i2", comps=("Claude Code",))]), cfg)
        self.assertEqual(len(Sink.received), 1)

    def test_model_filter(self):
        cfg = self.config(filters={"models": ["opus"]})
        self.run_check(summary([incident()]), cfg)  # Sonnet only
        self.assertEqual(Sink.received, [])
        self.run_check(summary([incident(iid="i3", name="Errors on Claude Opus")]), cfg)
        self.assertEqual(len(Sink.received), 1)

    def test_uncovered_component_change(self):
        comps = [{"name": "claude.ai", "status": "degraded_performance"}]
        cfg = self.config()
        self.run_check(summary([], comps), cfg)
        self.assertEqual(len(Sink.received), 1)
        self.run_check(summary([], comps), cfg)
        self.assertEqual(len(Sink.received), 1)
        self.run_check(summary([], [{"name": "claude.ai", "status": "operational"}]), cfg)
        self.assertEqual(len(Sink.received), 2)
        self.assertIn("back to normal", json.loads(Sink.received[1][2])["text"])

    def test_french(self):
        self.run_check(summary([incident()]), self.config(language="fr", message_prefix="[TEST] "))
        text = json.loads(Sink.received[0][2])["text"]
        self.assertTrue(text.startswith("[TEST] Nouvel incident"))

    def test_fetch_failure_keeps_state(self):
        cfg = self.config()
        self.run_check(summary([incident()]), cfg)
        before = read_text(self.state)
        code = csw.main(["check", "--config", cfg, "--summary-file", os.path.join(self.dir, "missing.json")])
        self.assertEqual(code, 1)
        self.assertEqual(read_text(self.state), before)

    def test_dry_run_writes_nothing(self):
        cfg = self.config()
        with open(self.summary, "w") as f:
            json.dump(summary([incident()]), f)
        with contextlib.redirect_stdout(io.StringIO()):
            csw.main(["check", "--dry-run", "--config", cfg, "--summary-file", self.summary])
        self.assertFalse(os.path.exists(self.state))
        self.assertEqual(Sink.received, [])


class TestReview(Base):
    def test_component_covered_by_incident_no_false_back_to_normal(self):
        cfg = self.config()
        deg = [{"name": "claude.ai", "status": "degraded_performance"}]
        self.run_check(summary([], deg), cfg)
        self.run_check(summary([incident(comps=("claude.ai",))], deg), cfg)
        texts = [json.loads(r[2])["text"] for r in Sink.received]
        self.assertFalse(any("back to normal" in t for t in texts))

    def test_malformed_summary_keeps_state(self):
        cfg = self.config()
        self.run_check(summary([incident()]), cfg)
        before = read_text(self.state)
        code, _ = self.run_check({"page": {}}, cfg)
        self.assertEqual(code, 1)
        self.assertEqual(read_text(self.state), before)
        self.assertEqual(len(Sink.received), 1)

    def test_negated_other_models_is_not_all(self):
        inc = incident(name="Errors on Claude Opus", impact="minor", body="Sonnet and other Claude models are fine.")
        self.run_check(summary([inc]), self.config())
        self.assertFalse(read(self.status)["all_models_affected"])

    def test_bad_smtp_security_rejected(self):
        with self.assertRaises(ValueError):
            csw.send_email({"security": "tls", "host": "x", "from": "a", "to": "b"}, "t", "b")

    def test_component_filter_applies_to_component_messages(self):
        cfg = self.config(filters={"components": ["Claude Code"]})
        self.run_check(summary([], [{"name": "claude.ai", "status": "degraded_performance"}]), cfg)
        self.assertEqual(Sink.received, [])

    def test_postmortem_not_open(self):
        self.run_check(summary([incident(status="postmortem")]), self.config())
        self.assertEqual(Sink.received, [])

    def test_mixed_case_config(self):
        cfg = csw.load_config(self.config(models=["Opus", "Sonnet"]))
        self.assertEqual(cfg["models"], ["opus", "sonnet"])


class TestChannels(Base):
    def test_ntfy_discord_slack(self):
        chans = [
            {"type": "ntfy", "server": self.base, "topic": "mytopic"},
            {"type": "discord", "webhook": self.base + "/discord"},
            {"type": "slack", "webhook": self.base + "/slack"},
        ]
        self.run_check(summary([incident()]), self.config(channels=chans))
        paths = [r[0] for r in Sink.received]
        self.assertEqual(paths, ["/mytopic", "/discord", "/slack"])
        self.assertIn("content", json.loads(Sink.received[1][2]))
        self.assertIn("text", json.loads(Sink.received[2][2]))

    def test_command_channel_gets_env_and_stdin(self):
        out = os.path.join(self.dir, "out.txt")
        script = os.path.join(self.dir, "hook.py")
        with open(script, "w") as f:
            f.write("import os,sys\nopen(%r,'w').write(os.environ['CSW_EVENT']+'|'+sys.stdin.read())\n" % out)
        chans = [{"type": "command", "argv": [sys.executable, script]}]
        self.run_check(summary([incident()]), self.config(channels=chans))
        content = read_text(out)
        self.assertTrue(content.startswith("new|New incident: Elevated errors on Claude Sonnet"))

    def test_env_file_secret(self):
        envf = os.path.join(self.dir, "x.env")
        with open(envf, "w") as f:
            f.write(f"BOT_TOKEN='{SECRET}'\nexport CHAT=7\n")
        chans = [{"type": "telegram", "env_file": envf, "token_env": "BOT_TOKEN", "chat_env": "CHAT",
                  "api_base": self.base}]
        self.run_check(summary([incident()]), self.config(channels=chans))
        self.assertIn(f"/bot{SECRET}/", Sink.received[0][0])
        self.assertEqual(json.loads(Sink.received[0][2])["chat_id"], "7")

    def test_unknown_channel_type_fails_delivery(self):
        code, out = self.run_check(summary([incident()]), self.config(channels=[{"type": "pigeon"}]))
        self.assertIn("failed (ValueError)", out)
        self.assertEqual(read(self.state)["incidents"], {})

    def test_notify_test(self):
        cfg = self.config()
        self.assertEqual(csw.main(["notify-test", "--config", cfg]), 0)
        self.assertEqual(len(Sink.received), 1)


class TestGuard(Base):
    def guard(self, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = csw.main(["guard", "--status-file", self.status, *extra])
        return code, out.getvalue()

    def test_guard_by_model(self):
        self.run_check(summary([incident()]), self.config())
        self.assertEqual(self.guard("--model", "claude-sonnet-5-5")[0], 75)
        self.assertEqual(self.guard("--model", "sonnet")[0], 75)
        self.assertEqual(self.guard("--model", "claude-opus-5-5")[0], 0)
        self.assertEqual(self.guard()[0], 75)  # no model: any affected model pauses
        self.assertEqual(self.guard("--model", "mystery-model")[0], 75)

    def test_guard_all_models(self):
        self.run_check(summary([incident(name="Elevated errors")]), self.config())
        self.assertEqual(self.guard("--model", "opus")[0], 75)

    def test_guard_clear_after_resolution(self):
        cfg = self.config()
        self.run_check(summary([incident()]), cfg)
        self.run_check(summary([]), cfg)
        self.assertEqual(self.guard("--model", "sonnet"), (0, "go\n"))

    def test_guard_stale_and_missing(self):
        self.assertEqual(self.guard("--model", "sonnet")[0], 0)
        self.assertEqual(self.guard("--model", "sonnet", "--fail-closed")[0], 75)
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        with open(self.status, "w") as f:
            json.dump({"checked_at": old, "models_affected": {"sonnet": {"since": "x"}}}, f)
        self.assertEqual(self.guard("--model", "sonnet")[0], 0)
        self.assertEqual(self.guard("--model", "sonnet", "--max-age", "600")[0], 75)


if __name__ == "__main__":
    unittest.main()
