"""Tests of `backlog template-check`. Run with: python3 -m unittest discover -s tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[2] / "agile-project-template"
TOOL = TEMPLATE / ".agents" / "tools" / "backlog.py"
GIT_ENV = {
    **os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
}


class TemplateCheck(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "project"
        (self.root / "docs").mkdir(parents=True)
        self.template = Path(tmp.name) / "template"
        self.template.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("commit", "-q", "--allow-empty", "-m", "init")

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.template), *args], check=True, capture_output=True, env=GIT_ENV)

    def tag(self, *names):
        for name in names:
            self.git("tag", name)

    def process(self, version="4.1.0", template=None):
        lines = ["# Development Process", ""]
        if version:
            lines += [f"**Process version:** {version}", ""]
        if template is not False:
            lines += [f"**Template:** {template or self.template}", ""]
        (self.root / "docs" / "PROCESS.md").write_text("\n".join(lines + ["Text."]) + "\n", encoding="utf-8")

    def check(self, *args):
        result = subprocess.run(
            [sys.executable, "-I", str(TOOL), "--root", str(self.root), "template-check", *args],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def report(self):
        return json.loads(self.check("--format", "json"))

    def test_behind_reports_latest_release_and_level(self):
        self.process("4.1.0")
        self.tag("v3.0.0", "v4.1.0", "v4.10.0", "v4.2.1", "not-a-release", "v5.0.0-rc1")
        report = self.report()
        self.assertEqual(
            (report["state"], report["current"], report["latest"], report["level"]),
            ("behind", "4.1.0", "4.10.0", "minor"),
        )
        self.assertIn("4.10.0", report["message"])
        self.assertIn("this project uses 4.1.0", report["message"])

    def test_levels(self):
        self.process("4.1.0")
        self.tag("v4.1.3")
        self.assertEqual(self.report()["level"], "patch")
        self.tag("v5.0.0")
        report = self.report()
        self.assertEqual(report["level"], "major")
        self.assertIn("migration", report["message"])

    def test_current_and_ahead_are_up_to_date(self):
        self.tag("v4.1.0")
        for version in ("4.1.0", "4.2.0"):
            self.process(version)
            self.assertEqual(self.report()["state"], "current")
            self.assertEqual(self.check("--quiet"), "")
            self.assertEqual(self.check("--format", "claude-hook"), "")

    def test_claude_hook_output(self):
        self.process("4.1.0")
        self.tag("v4.2.0")
        output = json.loads(self.check("--format", "claude-hook"))
        self.assertEqual(list(output), ["systemMessage"])
        self.assertIn("4.2.0", output["systemMessage"])
        self.assertEqual(self.check("--quiet"), output["systemMessage"] + "\n")

    def test_github_template_links_its_releases(self):
        self.process("4.1.0")
        self.tag("v4.2.0")
        report = self.report()
        self.assertNotIn("/releases", report["message"])
        self.assertIn(str(self.template), report["message"])

    def test_unknown_is_silent_and_never_fails(self):
        self.tag("v9.0.0")
        cases = {
            "missing template line": dict(template=False),
            "missing version line": dict(version=None),
            "unreachable template": dict(template=str(self.template.parent / "nowhere")),
        }
        for name, kwargs in cases.items():
            with self.subTest(name):
                self.process(**kwargs)
                self.assertEqual(self.report()["state"], "unknown")
                self.assertEqual(self.check("--quiet"), "")
                self.assertEqual(self.check("--format", "claude-hook"), "")
                self.assertIn("cannot check", self.check())

    def test_no_release_tag(self):
        self.process("4.1.0")
        self.assertEqual(self.report()["state"], "unknown")

    def test_missing_process_file(self):
        self.assertEqual(self.report()["state"], "unknown")


class TemplateFiles(unittest.TestCase):
    def test_process_names_the_template(self):
        head = (TEMPLATE / "docs" / "PROCESS.md").read_text(encoding="utf-8").splitlines()[:8]
        self.assertIn("**Template:** https://github.com/toto-castaldi/agile-project-template", head)

    def test_claude_code_session_start_hook(self):
        settings = json.loads((TEMPLATE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        [entry] = settings["hooks"]["SessionStart"]
        self.assertEqual(entry["matcher"], "startup")
        [hook] = entry["hooks"]
        self.assertIn(".agents/tools/backlog.py\" template-check --format claude-hook", hook["command"])

    def test_pi_extension_runs_the_cli(self):
        source = (TEMPLATE / ".pi" / "extensions" / "template-check" / "index.ts").read_text(encoding="utf-8")
        self.assertIn('"template-check", "--format", "json"', source)
        self.assertIn('event.reason !== "startup"', source)


if __name__ == "__main__":
    unittest.main()
