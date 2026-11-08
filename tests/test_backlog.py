"""Tests of the template's backlog CLI. Run with: python3 -m unittest discover -s tests"""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[2] / "agile-project-template" / ".agents" / "tools" / "backlog.py"
TODAY = datetime.date.today().isoformat()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ok("version", "add", "v0.1.0", "--goal", "Primo obiettivo")
        self.ok("epic", "add", "--title", "Base", "--scope", "Fondamenta")

    def run_tool(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, "-I", str(TOOL), "--root", str(self.root), *args],
            capture_output=True, text=True, encoding="utf-8", cwd=cwd,
        )

    def ok(self, *args):
        result = self.run_tool(*args)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result.stdout

    def refused(self, *args):
        result = self.run_tool(*args)
        self.assertEqual(result.returncode, 1, result.stdout)
        return result.stderr + result.stdout

    def add(self, *extra, kind="TEC"):
        return self.ok(
            "add", "--type", kind, "--title", "Titolo", "--version", "v0.1.0", "--epic", "EPIC-001",
            "--priority", "P1", "--criterion", "Criterio", *extra,
        ).strip()

    def item(self, item_id):
        return json.loads((self.root / "backlog" / "items" / f"{item_id}.json").read_text(encoding="utf-8"))

    def start(self, item_id, *extra):
        return self.ok("start", item_id, "--branch", f"task/{item_id}-slug", *extra)


class Records(Base):
    def test_ids_are_sequential_per_type(self):
        self.assertEqual(self.add(), "TEC-001")
        self.assertEqual(self.add(), "TEC-002")

    def test_canonical_file_format(self):
        self.add("--description", "Perché no")
        text = (self.root / "backlog" / "items" / "TEC-001.json").read_text(encoding="utf-8")
        self.assertTrue(text.endswith("}\n"))
        self.assertIn("Perché", text)
        self.assertLess(text.index('"id"'), text.index('"title"'))
        self.assertNotIn("outcome", text)

    def test_user_story_needs_requirement(self):
        self.assertIn("requirement", self.refused(
            "add", "--type", "US", "--title", "T", "--version", "v0.1.0", "--epic", "EPIC-001",
            "--priority", "P1", "--criterion", "C",
        ))
        self.assertFalse((self.root / "backlog" / "items" / "US-001.json").exists())

    def test_bug_needs_its_fields(self):
        self.assertIn("found_in", self.refused(
            "add", "--type", "BUG", "--title", "T", "--version", "v0.1.0", "--epic", "EPIC-001",
            "--priority", "P1", "--criterion", "C", "--requirements", "REQ-A-001",
        ))

    def test_unknown_references_are_refused(self):
        self.assertIn("unknown version", self.refused(
            "add", "--type", "TEC", "--title", "T", "--version", "v9.9.9", "--epic", "EPIC-001",
            "--priority", "P1", "--criterion", "C",
        ))
        self.assertIn("unknown dependency", self.refused(
            "add", "--type", "TEC", "--title", "T", "--version", "v0.1.0", "--epic", "EPIC-001",
            "--priority", "P1", "--criterion", "C", "--dependencies", "TEC-099",
        ))

    def test_requirement_must_exist_in_requirements_doc(self):
        (self.root / "docs").mkdir()
        (self.root / "docs" / "REQUIREMENTS.md").write_text("REQ-AUTH-001\n", encoding="utf-8")
        self.add("--requirements", "REQ-AUTH-001", kind="US")
        self.assertIn("not in docs/REQUIREMENTS.md", self.refused(
            "edit", "US-001", "--requirements", "REQ-AUTH-002",
        ))

    def test_edit_replaces_and_clears(self):
        self.add("--description", "D")
        self.ok("edit", "TEC-001", "--description", "", "--title", "Nuovo", "--criterion", "A", "--criterion", "B")
        item = self.item("TEC-001")
        self.assertNotIn("description", item)
        self.assertEqual(item["title"], "Nuovo")
        self.assertEqual(item["acceptance_criteria"], ["A", "B"])

    def test_edit_refuses_cycle(self):
        self.add()
        self.add("--dependencies", "TEC-001")
        self.assertIn("cycle", self.refused("edit", "TEC-001", "--dependencies", "TEC-002"))


class Transitions(Base):
    def test_full_cycle(self):
        self.add()
        self.start("TEC-001")
        self.assertEqual(self.item("TEC-001")["status"], "In Progress")
        self.ok("block", "TEC-001", "--reason", "Attesa")
        self.assertEqual(self.item("TEC-001")["blocked_by"], "Attesa")
        self.ok("resume", "TEC-001")
        self.assertNotIn("blocked_by", self.item("TEC-001"))
        self.ok("done", "TEC-001", "--outcome", "Fatto")
        item = self.item("TEC-001")
        self.assertEqual((item["status"], item["closed_at"]), ("Done", TODAY))
        self.ok("reopen", "TEC-001")
        item = self.item("TEC-001")
        self.assertEqual(item["status"], "In Progress")
        self.assertNotIn("closed_at", item)

    def test_branch_must_match_item(self):
        self.add()
        self.assertIn("invalid branch", self.refused("start", "TEC-001", "--branch", "main"))
        self.assertIn("invalid branch", self.refused("start", "TEC-001", "--branch", "us/TEC-001-x"))
        self.assertEqual(self.item("TEC-001")["status"], "Todo")

    def test_start_uses_current_branch(self):
        self.add()
        subprocess.run(["git", "init", "-q", "-b", "task/TEC-001-kick", str(self.root)], check=True)
        self.ok("start", "TEC-001")
        self.assertEqual(self.item("TEC-001")["branch"], "task/TEC-001-kick")

    def test_dependencies_block_start_unless_overridden(self):
        self.add()
        self.add("--dependencies", "TEC-001")
        self.assertIn("TEC-001", self.refused("start", "TEC-002", "--branch", "task/TEC-002-x"))
        self.start("TEC-002", "--override-dependencies", "Richiesto")
        self.assertEqual(self.item("TEC-002")["dependency_override"], "Richiesto")

    def test_invalid_transitions(self):
        self.add()
        self.refused("done", "TEC-001", "--outcome", "X")
        self.refused("resume", "TEC-001")
        self.refused("reopen", "TEC-001")

    def test_drop_keeps_file_and_id_is_not_reused(self):
        self.add()
        self.ok("drop", "TEC-001", "--reason", "Non serve")
        self.assertEqual(self.item("TEC-001")["status"], "Dropped")
        self.assertEqual(self.add(), "TEC-002")

    def test_drop_refused_while_needed(self):
        self.add()
        self.add("--dependencies", "TEC-001")
        self.assertIn("TEC-002", self.refused("drop", "TEC-001", "--reason", "X"))


class Versions(Base):
    def test_second_open_version_refused_but_patch_allowed(self):
        self.assertIn("more than one open", self.refused("version", "add", "v0.2.0", "--goal", "G"))
        self.ok("version", "add", "v0.1.1", "--goal", "Patch")

    def test_planned_version_lifecycle(self):
        self.ok("version", "add", "v0.2.0", "--goal", "Futura", "--planned")
        self.ok("add", "--type", "TEC", "--title", "T", "--version", "v0.2.0", "--epic", "EPIC-001",
                "--priority", "P1", "--criterion", "C")
        self.assertEqual(json.loads(self.ok("ready", "--json"))["total"], 0)
        self.assertIn("more than one open", self.refused("version", "open", "v0.2.0"))
        self.refused("close-version", "v0.2.0")

    def test_opening_planned_version_after_close(self):
        self.ok("version", "add", "v0.2.0", "--goal", "Futura", "--planned")
        self.ok("close-version", "v0.1.0")
        self.ok("version", "open", "v0.2.0")
        self.assertIn("v0.2.0:", self.ok("status"))

    def test_close_requires_finished_items(self):
        self.add()
        self.assertIn("TEC-001", self.refused("close-version", "v0.1.0"))
        self.start("TEC-001")
        self.ok("done", "TEC-001", "--outcome", "Fatto")
        self.ok("close-version", "v0.1.0")
        version = json.loads((self.root / "backlog" / "versions" / "v0.1.0.json").read_text())
        self.assertEqual((version["state"], version["closed_at"]), ("Closed", TODAY))

    def test_scope_change_is_dated_and_appended(self):
        self.ok("version", "edit", "v0.1.0", "--scope-change", "Aggiunto TEC-001")
        self.ok("version", "edit", "v0.1.0", "--scope-change", "Aggiunto TEC-002")
        version = json.loads((self.root / "backlog" / "versions" / "v0.1.0.json").read_text(encoding="utf-8"))
        self.assertEqual(version["scope_changes"], [f"{TODAY}: Aggiunto TEC-001", f"{TODAY}: Aggiunto TEC-002"])
        self.assertEqual(version["goal"], "Primo obiettivo")
        self.assertIn(f"{TODAY}: Aggiunto TEC-001", self.ok("export"))

    def test_add_needs_version_or_unassigned(self):
        args = ("add", "--type", "US", "--title", "T", "--epic", "EPIC-001", "--priority", "P2", "--criterion", "C")
        self.assertIn("exactly one", self.refused(*args))
        self.assertIn("exactly one", self.refused(*args, "--version", "v0.1.0", "--unassigned", "--requirements", "REQ-A-001"))
        self.assertEqual(self.ok(*args, "--unassigned").strip(), "US-001")
        self.assertIn("no version", self.refused("start", "US-001", "--branch", "us/US-001-x"))
        self.ok("edit", "US-001", "--version", "v0.1.0", "--requirements", "REQ-A-001")
        self.ok("start", "US-001", "--branch", "us/US-001-x")

    def test_remarks_replace_on_edit_and_show(self):
        self.add("--remark", "Prima")
        self.ok("edit", "TEC-001", "--remark", "Seconda")
        self.assertEqual(self.item("TEC-001")["remarks"], ["Seconda"])
        self.assertIn("Seconda", self.ok("show", "TEC-001"))

    def test_no_new_work_in_closed_version(self):
        self.ok("close-version", "v0.1.0")
        self.assertIn("closed version", self.refused(
            "add", "--type", "TEC", "--title", "T", "--version", "v0.1.0", "--epic", "EPIC-001",
            "--priority", "P1", "--criterion", "C",
        ))


class Check(Base):
    def write_raw(self, item_id, data):
        path = self.root / "backlog" / "items" / f"{item_id}.json"
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_clean_store(self):
        self.add()
        self.assertIn("check OK", self.ok("check"))

    def test_hand_edit_detected(self):
        self.add()
        self.write_raw("TEC-001", self.item("TEC-001"))
        self.assertIn("canonical", self.refused("check"))

    def test_done_without_outcome_detected(self):
        self.add()
        data = {**self.item("TEC-001"), "status": "Done"}
        self.write_raw("TEC-001", data)
        self.assertIn("Done without outcome", self.refused("check"))

    def test_cycle_detected(self):
        self.add()
        self.add("--dependencies", "TEC-001")
        self.write_raw("TEC-001", {**self.item("TEC-001"), "dependencies": ["TEC-002"]})
        self.assertIn("cycle", self.refused("check"))

    def test_unknown_field_and_bad_json_reported_without_crash(self):
        self.add()
        self.add()
        self.write_raw("TEC-001", {**self.item("TEC-001"), "colour": "red"})
        (self.root / "backlog" / "items" / "TEC-002.json").write_text("{", encoding="utf-8")
        output = self.refused("check")
        self.assertIn("unknown field", output)
        self.assertIn("cannot read", output)
        self.assertNotIn("Traceback", output)

    def test_wrong_types_reported_without_crash(self):
        self.add()
        self.write_raw("TEC-001", {**self.item("TEC-001"), "dependencies": "TEC-002", "title": 7})
        output = self.refused("check")
        self.assertIn("must be", output)
        self.assertNotIn("Traceback", output)

    def test_reading_commands_refuse_a_broken_store(self):
        (self.root / "backlog" / "items").mkdir(parents=True)
        (self.root / "backlog" / "items" / "TEC-001.json").write_text("{", encoding="utf-8")
        self.assertIn("cannot be read", self.refused("status"))

    def test_empty_store_is_valid(self):
        self.root = Path(self.tmp.name) / "empty"
        self.root.mkdir()
        self.assertIn("check OK", self.ok("check"))
        self.assertIn("none", self.ok("status"))


class Reading(Base):
    def populate(self, count):
        for number in range(count):
            self.add()
        for number in range(1, count // 2 + 1):
            item_id = f"TEC-{number:03d}"
            self.start(item_id)
            self.ok("done", item_id, "--outcome", "Fatto")

    def test_status_counts(self):
        self.populate(4)
        output = self.ok("status")
        self.assertIn("v0.1.0: 2/4 done (50%)", output)
        self.assertIn("Todo 2", output)
        data = json.loads(self.ok("status", "--json"))
        self.assertEqual(data["versions"][0]["counts"]["Done"], 2)

    def test_dropped_not_in_progress_total(self):
        self.add()
        self.add()
        self.ok("drop", "TEC-001", "--reason", "No")
        self.assertIn("0/1 done", self.ok("status"))

    def test_status_size_does_not_grow(self):
        self.populate(24)
        small = self.ok("status").splitlines()
        for _ in range(16):
            self.add()
        self.assertEqual(len(self.ok("status").splitlines()), len(small))

    def test_status_bounds_notes_and_long_titles(self):
        for number in range(8):
            self.ok("notes", "--add", f"Nota {number}")
        self.ok("add", "--type", "TEC", "--title", "x" * 500, "--version", "v0.1.0", "--epic", "EPIC-001",
                "--priority", "P0", "--criterion", "C")
        output = self.ok("status")
        self.assertIn("… 3 more", output)
        self.assertIn("see the notes command", output)
        self.assertLess(max(map(len, output.splitlines())), 160)

    def test_done_hidden_from_list_unless_requested(self):
        self.populate(2)
        self.assertNotIn("TEC-001", self.ok("list"))
        self.assertIn("TEC-001", self.ok("list", "--status", "Done"))
        self.assertIn("TEC-001", self.ok("list", "--include-closed"))

    def test_list_default_limit(self):
        for _ in range(32):
            self.add()
        self.assertIn("showing 30 of 32", self.ok("list"))
        self.assertEqual(json.loads(self.ok("list", "--json", "--limit", "0"))["total"], 32)

    def test_ready_needs_done_dependencies_and_orders_by_priority(self):
        self.add()
        self.add("--dependencies", "TEC-001")
        self.ok("add", "--type", "TEC", "--title", "Alta", "--version", "v0.1.0", "--epic", "EPIC-001",
                "--priority", "P0", "--criterion", "C")
        ids = [i["id"] for i in json.loads(self.ok("ready", "--json"))["items"]]
        self.assertEqual(ids, ["TEC-003", "TEC-001"])

    def test_show_and_export(self):
        self.add("--description", "Descrizione")
        self.assertIn("Descrizione", self.ok("show", "TEC-001"))
        self.assertEqual(json.loads(self.ok("show", "TEC-001", "--json"))["id"], "TEC-001")
        self.ok("ideas", "--add", "Idea")
        output = self.ok("export")
        self.assertIn("#### TEC-001 — Titolo", output)
        self.assertIn("- Idea", output)
        self.refused("show", "TEC-099")

    def test_list_files(self):
        self.ok("notes", "--add", "Una")
        self.ok("notes", "--add", "Due")
        self.ok("notes", "--remove", "1")
        self.assertEqual(json.loads(self.ok("notes", "--json")), ["Due"])
        self.refused("notes", "--remove", "5")

    def test_tool_writes_nothing_outside_the_store(self):
        self.add()
        self.assertEqual({p.name for p in self.root.iterdir()}, {"backlog"})
        leftovers = [p for p in (self.root / "backlog").rglob(".*") if p.is_file()]
        self.assertEqual(leftovers, [])


class Branches(Base):
    def git(self, *args, cwd):
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=env)

    def test_status_overlays_remote_item_branch(self):
        self.add()
        remote = Path(self.tmp.name) / "remote.git"
        self.git("init", "-q", "--bare", "-b", "main", str(remote), cwd=self.tmp.name)
        clone = Path(self.tmp.name) / "clone"
        self.git("clone", "-q", str(remote), str(clone), cwd=self.tmp.name)
        self.git("switch", "-q", "-c", "main", cwd=clone)
        self.root, original = clone, self.root
        (clone / "backlog").mkdir()
        for part in ("items", "epics", "versions"):
            subprocess.run(["cp", "-r", str(original / "backlog" / part), str(clone / "backlog")], check=True)
        self.git("add", ".", cwd=clone)
        self.git("commit", "-qm", "seed", cwd=clone)
        self.git("push", "-q", "origin", "main", cwd=clone)
        self.git("switch", "-q", "-c", "task/TEC-001-slug", cwd=clone)
        self.ok("start", "TEC-001")
        self.git("commit", "-qam", "start", cwd=clone)
        self.git("push", "-q", "origin", "task/TEC-001-slug", cwd=clone)
        self.git("switch", "-q", "main", cwd=clone)

        self.assertIn("In progress (0)", self.ok("status"))
        self.assertIn("task/TEC-001-slug", self.ok("status", "--branches"))
        self.assertEqual(self.item("TEC-001")["status"], "Todo")

        self.git("merge", "-q", "--no-ff", "-m", "merge", "task/TEC-001-slug", cwd=clone)
        self.git("push", "-q", "origin", "main", cwd=clone)
        self.git("switch", "-q", "--detach", "HEAD~1", cwd=clone)
        self.assertIn("In progress (0)", self.ok("status", "--branches"))

    def test_failed_fetch_is_only_a_warning(self):
        result = self.run_tool("status", "--branches")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("warning", result.stderr)


if __name__ == "__main__":
    unittest.main()
