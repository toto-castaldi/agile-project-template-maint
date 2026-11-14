"""Tests of the requirement and design files: check, docs and migrate-docs."""
import collections
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[2] / "agile-project-template"
TOOL = TEMPLATE / ".agents" / "tools" / "backlog.py"

REQUIREMENTS = """# Requirements — demo

**Target version:** v0.2.0

**State:** baseline

Intro che cita `docs/TECHNICAL-DESIGN.md`.

## 1. Goal

Obiettivo.

## 3. Glossary

- **Lezione:** incontro.

## 4. Scope

### In scope for v0.2.0

- Presenze (REQ-STUDIO-001).

## 5. Functional requirements

| Area | Meaning |
| ---- | ------- |
| STUDIO | Studio |

### Presenze

#### REQ-STUDIO-001 — Registrazione delle presenze

Il sistema deve registrare le presenze.

##### Dettaglio

- Anche "tutti tranne".

#### REQ-STUDIO-002 — Consultazione

Il sistema deve mostrare le presenze.

```text
## not a heading
# comment


kept
```

## 6. Non-functional requirements

#### REQ-NFR-001 — Gate

Gate riproducibile.

## 7. Release acceptance — v0.2.0

- Scenario completo.

## 8. Withdrawn requirements

#### REQ-NFR-002 — Vecchio

**Withdrawn (2026-01-01):** non serve più.
"""

DESIGN = """# Technical design — demo

**Target version:** v0.2.0

## 1. Initial architectural decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Dati | PostgreSQL | Relazionale |

## 3. Modules

**MOD-001 — Agente:** tutto.

## 4. Data model

### Lezioni

Tabella delle lezioni.

## 8. Test strategy

Test in memoria.

## 9. Gestione dei log

Log senza segreti.

## 10. Open decisions

- Cron — TEC-002
"""


class DocsBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ok("version", "add", "v0.2.0", "--goal", "Obiettivo")
        self.ok("epic", "add", "--title", "Base", "--scope", "Fondamenta")

    def run_tool(self, *args):
        return subprocess.run(
            [sys.executable, "-I", str(TOOL), "--root", str(self.root), *args],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )

    def ok(self, *args):
        result = self.run_tool(*args)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result.stdout

    def refused(self, *args):
        result = self.run_tool(*args)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result.stdout + result.stderr

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def requirement(self, requirement_id, state="Active", title="Titolo"):
        self.write(f"docs/requirements/{requirement_id}.md", f"# {requirement_id} — {title}\n\n**State:** {state}\n\nTesto.\n")

    def add(self, *extra, kind="TEC"):
        return self.ok(
            "add", "--type", kind, "--title", "Titolo", "--version", "v0.2.0", "--epic", "EPIC-001",
            "--priority", "P1", "--criterion", "Criterio", *extra,
        ).strip()

    def item(self, item_id):
        return json.loads((self.root / "backlog" / "items" / f"{item_id}.json").read_text(encoding="utf-8"))


class Check(DocsBase):
    def test_template_seed_passes(self):
        result = subprocess.run([sys.executable, "-I", str(TOOL), "check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_design_reference_must_resolve(self):
        self.write("docs/design/README.md", "# Design\n")
        self.write("docs/design/data-model.md", "# Data model\n")
        self.add("--design-references", "design/data-model,design/README,PROCESS §5,ADR-001")
        message = self.refused("edit", "TEC-001", "--design-references", "design/missing")
        self.assertIn("docs/design/missing.md does not exist", message)
        self.assertIn("does not exist", self.refused("edit", "TEC-001", "--design-references", "design/_TEMPLATE"))

    def test_requirements_reference_resolves_to_requirement_files(self):
        self.write("docs/requirements/glossary.md", "# Glossary\n")
        self.add("--design-references", "requirements/glossary")
        self.assertIn("does not exist", self.refused("add", "--type", "TEC", "--title", "T", "--version", "v0.2.0",
                                                     "--epic", "EPIC-001", "--priority", "P1", "--criterion", "C",
                                                     "--design-references", "requirements/acceptance"))

    def test_withdrawn_requirement_only_for_closed_items(self):
        self.requirement("REQ-A-001", state="Withdrawn")
        self.assertIn("REQ-A-001 is Withdrawn", self.refused(
            "add", "--type", "US", "--title", "T", "--version", "v0.2.0", "--epic", "EPIC-001",
            "--priority", "P1", "--criterion", "C", "--requirements", "REQ-A-001",
        ))
        self.requirement("REQ-A-001")
        self.add("--requirements", "REQ-A-001", kind="US")
        self.ok("start", "US-001", "--branch", "us/US-001-slug")
        self.ok("done", "US-001", "--outcome", "Fatto")
        self.requirement("REQ-A-001", state="Withdrawn")
        self.ok("check")

    def test_malformed_files_are_reported(self):
        self.write("docs/requirements/REQ-a-1.md", "# x\n")
        self.write("docs/requirements/REQ-B-001.md", "# REQ-B-001 — Titolo\n\nnessuno stato\n")
        self.write("docs/requirements/REQ-B-002.md", "Titolo\n\n**State:** Forse\n")
        self.write("docs/design/Bad_Name.md", "# Bad\n")
        self.write("docs/design/no-title.md", "testo\n")
        output = self.refused("check")
        self.assertIn("REQ-a-1.md: requirement file name", output)
        self.assertIn("REQ-B-001.md: needs one line '**State:** Active'", output)
        self.assertIn("REQ-B-002.md: first line must be '# REQ-B-002 — <title>'", output)
        self.assertIn("REQ-B-002.md: needs one line", output)
        self.assertIn("Bad_Name.md: design topic file name", output)
        self.assertIn("no-title.md: first line must be '# <title>'", output)

    def test_module_is_read_from_modules_file(self):
        self.write("docs/design/modules.md", "# Modules\n\nMOD-001 — Agente\n")
        self.add("--module", "MOD-001")
        self.assertIn("not in docs/design/modules.md", self.refused("edit", "TEC-001", "--module", "MOD-002"))

    def test_docs_lists_requirements_and_topics(self):
        self.requirement("REQ-NFR-001", title="Gate")
        self.requirement("REQ-B-010", title="Dieci")
        self.requirement("REQ-B-002", title="Due", state="Withdrawn")
        self.write("docs/requirements/README.md", "# Requirements\n")
        self.write("docs/requirements/_TEMPLATE.md", "# REQ-`<AREA>`-NNN\n")
        self.write("docs/design/test-strategy.md", "# Test strategy\n")
        self.write("docs/design/README.md", "# Design\n")
        output = self.ok("docs")
        self.assertLess(output.index("REQ-B-002 — Due (Withdrawn)"), output.index("REQ-B-010 — Dieci"))
        self.assertLess(output.index("REQ-B-010"), output.index("REQ-NFR-001 — Gate"))
        self.assertIn("design/test-strategy — Test strategy", output)
        self.assertNotIn("README", output.split("Design")[1].replace("referenced", ""))
        data = json.loads(self.ok("docs", "--json"))
        self.assertEqual([r["id"] for r in data["requirements"]], ["REQ-B-002", "REQ-B-010", "REQ-NFR-001"])
        self.assertEqual(data["design"][0]["reference"], "design/test-strategy")


class Migration(DocsBase):
    def setUp(self):
        super().setUp()
        self.write("docs/REQUIREMENTS.md", REQUIREMENTS)
        self.write("docs/TECHNICAL-DESIGN.md", DESIGN)
        self.write("AGENTS.md", "Dettagli in `docs/TECHNICAL-DESIGN.md` §4.\n")
        self.add_legacy_item()

    def add_legacy_item(self):
        # An item written before the migration: legacy references are free text until then.
        self.ok(
            "add", "--type", "US", "--title", "Presenze", "--version", "v0.2.0", "--epic", "EPIC-001",
            "--priority", "P1", "--criterion", "Vedi `TECHNICAL-DESIGN` e TECHNICAL-DESIGN §12",
            "--requirements", "REQ-STUDIO-001,REQ-NFR-001", "--module", "MOD-001",
            "--design-references", "TECHNICAL-DESIGN §4,TECHNICAL-DESIGN §8.2,TECHNICAL-DESIGN §1,PROCESS §5",
            "--description", "Vedi docs/TECHNICAL-DESIGN.md §9 e REQUIREMENTS §7.",
        )

    def read(self, relative):
        return (self.root / relative).read_text(encoding="utf-8")

    def test_dry_run_writes_nothing(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        output = self.ok("migrate-docs", "--dry-run")
        self.assertIn("docs/requirements/REQ-STUDIO-001.md", output)
        self.assertIn("dry run: nothing was written", output)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_split_layout(self):
        output = self.ok("migrate-docs")
        self.assertFalse((self.root / "docs" / "REQUIREMENTS.md").exists())
        self.assertFalse((self.root / "docs" / "TECHNICAL-DESIGN.md").exists())
        names = {p.name for p in (self.root / "docs" / "requirements").iterdir()}
        self.assertEqual(names, {
            "README.md", "glossary.md", "acceptance.md", "REQ-STUDIO-001.md", "REQ-STUDIO-002.md",
            "REQ-NFR-001.md", "REQ-NFR-002.md",
        })
        self.assertEqual({p.name for p in (self.root / "docs" / "design").iterdir()}, {
            "README.md", "modules.md", "data-model.md", "test-strategy.md", "gestione-dei-log.md",
        })
        requirement = self.read("docs/requirements/REQ-STUDIO-001.md")
        self.assertTrue(requirement.startswith("# REQ-STUDIO-001 — Registrazione delle presenze\n\n**State:** Active\n"))
        self.assertIn("\n## Dettaglio\n", requirement)
        self.assertIn("```text\n## not a heading\n# comment\n\n\nkept\n```", self.read("docs/requirements/REQ-STUDIO-002.md"))
        self.assertIn("**State:** Withdrawn", self.read("docs/requirements/REQ-NFR-002.md"))
        self.assertTrue(self.read("docs/requirements/glossary.md").startswith("# Glossary\n"))
        self.assertTrue(self.read("docs/requirements/acceptance.md").startswith("# Release acceptance — v0.2.0\n"))
        readme = self.read("docs/requirements/README.md")
        self.assertIn("## Goal", readme)
        self.assertIn("### In scope for v0.2.0", readme)
        self.assertIn("| STUDIO | Studio |", readme)
        self.assertNotIn("### Presenze", readme)
        self.assertNotIn("Withdrawn requirements", readme)
        self.assertNotIn("Non-functional requirements", readme)
        design = self.read("docs/design/README.md")
        self.assertIn("## Initial architectural decisions", design)
        self.assertIn("## Open decisions", design)
        self.assertIn("\n## Lezioni\n", self.read("docs/design/data-model.md"))
        self.assertTrue(self.read("docs/design/gestione-dei-log.md").startswith("# Gestione dei log\n"))
        self.assertIn("update by hand: AGENTS.md:1:", output)
        self.assertIn("update by hand: docs/requirements/README.md", output)
        self.assertIn("check OK", output)

    def test_no_content_is_lost(self):
        def content(text):
            return [line for line in text.splitlines()
                    if line.strip() and not re.match(r"^#{1,6} ", line) and line.strip() != "None."]
        old = collections.Counter(content(REQUIREMENTS) + content(DESIGN))
        self.ok("migrate-docs")
        new = collections.Counter()
        for path in (self.root / "docs").rglob("*.md"):
            new.update(line for line in content(path.read_text(encoding="utf-8"))
                       if not re.fullmatch(r"\*\*State:\*\* (Active|Withdrawn)", line))
        self.assertEqual(old, new)

    def test_item_references_are_rewritten(self):
        output = self.ok("migrate-docs")
        item = self.item("US-001")
        self.assertEqual(item["design_references"], ["design/data-model", "design/test-strategy", "design/README", "PROCESS §5"])
        self.assertEqual(item["description"], "Vedi design/gestione-dei-log e requirements/acceptance.")
        self.assertEqual(item["acceptance_criteria"], ["Vedi `design/README` e TECHNICAL-DESIGN §12"])
        self.assertIn("unresolved reference left as it is: TECHNICAL-DESIGN §12", output)
        self.ok("check")
        self.assertIn("1 item(s) with rewritten references: US-001", output)

    def test_refused_when_already_migrated(self):
        self.write("docs/design/README.md", "# Design\n")
        self.assertIn("already contains files", self.refused("migrate-docs"))
        self.assertTrue((self.root / "docs" / "REQUIREMENTS.md").exists())

    def test_refused_when_an_item_loses_its_requirement(self):
        self.write("docs/REQUIREMENTS.md", REQUIREMENTS.replace("#### REQ-NFR-001 — Gate", "REQ-NFR-001 Gate"))
        output = self.refused("migrate-docs")
        self.assertIn("requirement REQ-NFR-001 is not in docs/requirements/", output)
        self.assertIn("nothing was written", output)
        self.assertFalse((self.root / "docs" / "requirements").exists())
        self.assertTrue((self.root / "docs" / "REQUIREMENTS.md").exists())

    def test_refused_on_duplicate_requirement(self):
        self.write("docs/REQUIREMENTS.md", REQUIREMENTS + "\n#### REQ-STUDIO-001 — Ancora\n\nDoppio.\n")
        self.assertIn("REQ-STUDIO-001 appears twice", self.refused("migrate-docs"))

    def test_refused_without_legacy_files(self):
        (self.root / "docs" / "REQUIREMENTS.md").unlink()
        (self.root / "docs" / "TECHNICAL-DESIGN.md").unlink()
        self.assertIn("nor docs/TECHNICAL-DESIGN.md found", self.refused("migrate-docs"))

    def test_template_seed_layout_matches_the_migration(self):
        """Migrating the 2.x template documents gives the topics shipped by the template."""
        legacy = subprocess.run(
            ["git", "-C", str(TEMPLATE), "show", "v2.3.0:docs/TECHNICAL-DESIGN.md"], capture_output=True, text=True,
        )
        if legacy.returncode != 0:
            self.skipTest("tag v2.3.0 not available")
        shutil.rmtree(self.root / "backlog")
        self.ok("version", "add", "v0.1.0", "--goal", "Obiettivo")
        (self.root / "docs" / "REQUIREMENTS.md").unlink()
        self.write("docs/TECHNICAL-DESIGN.md", legacy.stdout)
        self.ok("migrate-docs")
        migrated = {p.name for p in (self.root / "docs" / "design").iterdir()}
        shipped = {p.name for p in (TEMPLATE / "docs" / "design").iterdir() if not p.name.startswith("_")}
        self.assertEqual(migrated, shipped)


if __name__ == "__main__":
    unittest.main()
