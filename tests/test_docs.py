"""Documentation checks: internal links resolve, examples parse, no em dash, no personal strings."""
import glob
import json
import os
import re
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
import claude_status_watch as csw  # noqa: E402

MD = [p for p in glob.glob(os.path.join(ROOT, "**", "*.md"), recursive=True)]
FORBIDDEN = ["motpop", "hermes", "vuntum", "siteservi", "/root/", "crosswire", "antoine"]


def text_files():
    for ext in ("md", "py", "json", "sh", "ps1", "service", "timer", "example"):
        yield from glob.glob(os.path.join(ROOT, "**", "*." + ext), recursive=True)
    yield os.path.join(ROOT, ".env.example")


class TestDocs(unittest.TestCase):
    def test_internal_links_resolve(self):
        for path in MD:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            for target in re.findall(r"\]\(([^)]+)\)", content):
                if target.startswith(("http", "mailto:", "#")):
                    continue
                file_part = target.split("#")[0]
                full = os.path.normpath(os.path.join(os.path.dirname(path), file_part))
                self.assertTrue(os.path.exists(full), f"{path}: broken link {target}")

    def test_example_config_loads(self):
        cfg = csw.load_config(os.path.join(ROOT, "examples", "config.example.json"))
        self.assertEqual(cfg["channels"][0]["type"], "telegram")

    def test_simulated_incident_is_valid_json(self):
        with open(os.path.join(ROOT, "examples", "simulated_incident.json")) as f:
            self.assertEqual(json.load(f)["incidents"][0]["id"], "sim0000example")

    def test_no_em_dash_no_personal_strings(self):
        for path in text_files():
            if path.endswith("test_docs.py"):
                continue
            with open(path, encoding="utf-8") as f:
                content = f.read()
            low = content.lower()
            self.assertNotIn("—", content, path)
            for word in FORBIDDEN:
                self.assertNotIn(word, low, f"{path}: {word}")


if __name__ == "__main__":
    unittest.main()
