"""Tests of the import-md migration of the template's backlog CLI."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[2] / "agile-project-template" / ".agents" / "tools" / "backlog.py"

SOURCE = """# Product Backlog — `demo`

## Management

- Process: `docs/PROCESS.md`.

## Version v0.1.0

**State:** Closed (2026-01-10)

**Goal:** Prima versione

### EPIC-001 — Fondamenta

**Scope:** base del progetto

#### TEC-001 — Kickoff

- **Epic:** EPIC-001 — Fondamenta
- **Type:** Task · **Priority:** P0 · **Status:** Done
- **Branch:** `task/TEC-001-kickoff`
- **Dependencies:** none
- **Design references:** PROCESS §3, AGENTS
- **Acceptance criteria:**
  - Primo criterio
    che continua
  - Secondo criterio
- **Outcome:** Consegnato e verificato, 2026-01-09

## Version v0.2.0

**State:** Open

**Goal:** Seconda versione

### EPIC-001 — Fondamenta

**Scope:** base del progetto

#### BUG-002 — Errore

- **Epic:** EPIC-001 — Fondamenta
- **Module:** MOD-001 — Nome
- **Type:** Bug · **Priority:** P1 · **Status:** Blocked
- **Branch:** `fix/BUG-002-errore`
- **Dependencies:** TEC-001
- **Requirements:** REQ-X-001
- **Found in:** v0.1.0
- **Steps to reproduce:**
  1. Apri
  2. Clicca
- **Expected:** Funziona
- **Actual:** Non funziona
- **Acceptance criteria:**
  - Test di regressione
- **Blocked by:** Attesa fornitore

## Dependencies and suggested order

1. TEC-001.

## Unassigned backlog

Ideas not assigned to any version. They need requirements before they can be designed.

- US-009 — Idea con ID
- Idea senza ID
"""
STATUS = "# Project status\n\n## Notes\n\n- Nota importante\n\n## Blocked\n\nNone.\n"


class ImportMd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "REQUIREMENTS.md").write_text("REQ-X-001\n", encoding="utf-8")
        (self.root / "docs" / "TECHNICAL-DESIGN.md").write_text("MOD-001\n", encoding="utf-8")
        (self.root / "STATUS.md").write_text(STATUS, encoding="utf-8")
        self.source(SOURCE)

    def run_tool(self, *args):
        return subprocess.run(
            [sys.executable, "-I", str(TOOL), "--root", str(self.root), *args],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )

    def source(self, text):
        (self.root / "BACKLOG.md").write_text(text, encoding="utf-8")

    def replaced(self, old, new):
        self.assertIn(old, SOURCE)
        self.source(SOURCE.replace(old, new))

    def record(self, kind, name):
        return json.loads((self.root / "backlog" / kind / f"{name}.json").read_text(encoding="utf-8"))

    def assert_refused(self, expected, *args):
        result = self.run_tool("import-md", *args)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(expected, result.stdout + result.stderr)
        self.assertFalse((self.root / "backlog").exists())
        self.assertNotIn("Traceback", result.stderr)

    def test_full_import(self):
        result = self.run_tool("import-md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        tec = self.record("items", "TEC-001")
        self.assertEqual((tec["status"], tec["closed_at"]), ("Done", "2026-01-09"))
        self.assertEqual(tec["branch"], "task/TEC-001-kickoff")
        self.assertEqual(tec["acceptance_criteria"], ["Primo criterio che continua", "Secondo criterio"])
        self.assertEqual(tec["design_references"], ["PROCESS §3", "AGENTS"])
        bug = self.record("items", "BUG-002")
        self.assertEqual(bug["module"], "MOD-001")
        self.assertEqual(bug["steps_to_reproduce"], "1. Apri\n2. Clicca")
        self.assertEqual(bug["blocked_by"], "Attesa fornitore")
        version = self.record("versions", "v0.1.0")
        self.assertEqual((version["state"], version["closed_at"]), ("Closed", "2026-01-10"))
        self.assertEqual(self.record("epics", "EPIC-001")["scope"], "base del progetto")
        self.assertIn("- Nota importante", (self.root / "backlog" / "NOTES.md").read_text(encoding="utf-8"))
        self.assertIn("- Idea senza ID", (self.root / "backlog" / "IDEAS.md").read_text(encoding="utf-8"))
        self.assertIn("ignored section: Dependencies", result.stdout)
        self.assertEqual(self.run_tool("check").returncode, 0)

    def test_id_in_an_idea_is_not_reused(self):
        self.assertEqual(self.run_tool("import-md").returncode, 0)
        result = self.run_tool(
            "add", "--type", "US", "--title", "T", "--version", "v0.2.0", "--epic", "EPIC-001",
            "--priority", "P1", "--criterion", "C", "--requirements", "REQ-X-001",
        )
        self.assertEqual(result.stdout.strip(), "US-010", result.stderr)

    def test_dry_run_writes_nothing(self):
        result = self.run_tool("import-md", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("nothing was written", result.stdout)
        self.assertFalse((self.root / "backlog").exists())

    def test_refuses_non_empty_store(self):
        self.assertEqual(self.run_tool("import-md").returncode, 0)
        result = self.run_tool("import-md")
        self.assertEqual(result.returncode, 1)
        self.assertIn("empty store", result.stderr)

    def test_unknown_field_refused_with_location(self):
        self.replaced("- **Expected:** Funziona", "- **Colore:** Rosso\n- **Expected:** Funziona")
        self.assert_refused("BACKLOG.md:")

    def test_unknown_section_refused(self):
        self.replaced("## Unassigned backlog", "## Roadmap\n\ntesto\n\n## Unassigned backlog")
        self.assert_refused("unknown section")

    def test_stray_text_refused(self):
        self.replaced("**Goal:** Seconda versione", "**Goal:** Seconda versione\n\nTesto libero")
        self.assert_refused("unrecognized line")

    def test_done_without_date_refused(self):
        self.replaced("Consegnato e verificato, 2026-01-09", "Consegnato")
        self.assert_refused("has no date")

    def test_unknown_status_refused(self):
        self.replaced("**Status:** Blocked", "**Status:** Quasi")
        self.assert_refused("unknown status")

    def test_invalid_reference_refused(self):
        self.replaced("**Requirements:** REQ-X-001", "**Requirements:** REQ-X-999")
        self.assert_refused("not in docs/REQUIREMENTS.md")

    def test_skip_option_lists_what_is_left_out(self):
        self.replaced("- **Expected:** Funziona", "- **Colore:** Rosso\n- **Expected:** Funziona")
        result = self.run_tool("import-md", "--skip-unrecognized")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("skipped:", result.stdout)

    def test_skip_option_does_not_bypass_validation(self):
        self.replaced("**Requirements:** REQ-X-001", "**Requirements:** REQ-X-999")
        self.assert_refused("not in docs/REQUIREMENTS.md", "--skip-unrecognized")

    def test_status_with_a_note_in_parentheses_is_accepted(self):
        self.replaced("**Status:** Done", "**Status:** Done (see Outcome)")
        result = self.run_tool("import-md", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("state counts differ", result.stdout)

    def test_missing_source_refused(self):
        (self.root / "BACKLOG.md").unlink()
        self.assert_refused("not found")


if __name__ == "__main__":
    unittest.main()
