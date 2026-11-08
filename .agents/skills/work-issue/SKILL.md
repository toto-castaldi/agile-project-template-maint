---
name: work-issue
description: Implement one GitHub issue of agile-project-template in ../agile-project-template - read the issue, change the template keeping it project-agnostic and initializable, verify the template invariants and commit on main with Fixes #N. Use when the user asks to work on, fix or implement a template issue.
---

# Work on a template issue

Rules: `AGENTS.md` of this workspace, §2–§5. The user's arguments give the issue number; if missing, run `gh issue list` in the template directory and ask which one.

Work in `../agile-project-template` (`T` below).

## 1. Checks

1. `T` is on `main`, up to date (`git -C T switch main && git -C T pull --ff-only`) and the working tree is clean. If not, stop and report without discarding anything.
2. `gh issue view N --comments` (inside `T`): the issue is open. Summarize it to the user.
3. If the issue is ambiguous, too large for one change or conflicts with the invariants (`AGENTS.md` §3), stop and propose a clarification or a split into several issues (`gh issue create` only with the user's agreement).

## 2. Plan

State briefly:

- which template files change;
- whether the change affects existing projects (`docs/PROCESS.md` or `.agents/skills/`) and the expected semver level (major / minor / patch, `AGENTS.md` §4);
- for a major change, the migration an existing project needs.

For a large or risky change ask whether to work in a branch `issue/N-short-name` with a pull request instead of directly on `main`.

## 3. Implement

1. Edit the template files. Do **not** change `Process version` (only `release-template` does) and do not record anything in the template's `backlog/` or `CHANGELOG.md`.
2. Keep placeholders, the "Template not initialized" notice, `TEC-001` and the seed of `backlog/` intact unless the issue is about them.
3. If a skill was added, removed or renamed, update the skill tables in `docs/PROCESS.md` (§10, subsection "Skills") and `README.md`.

## 4. Verify

Walk through every invariant in `AGENTS.md` §3 and give evidence, for example:

```bash
cd ../agile-project-template
grep -rn "§[0-9]" .agents/skills AGENTS.md backlog README.md   # references vs. headings of docs/PROCESS.md
grep -n "^## \|^### " docs/PROCESS.md
ls .agents/skills && readlink .claude/skills
head -5 .agents/skills/*/SKILL.md
git diff --stat
```

Mentally dry-run `kickoff` against the changed files: everything it reads or replaces still exists. Report any invariant that fails and fix it before committing.

## 5. Commit

```bash
git -C ../agile-project-template add -A
git -C ../agile-project-template commit
```

Message: `type(scope): description (#N)` in English, body explaining the change, footer `Fixes #N`. For a breaking change use `type(scope)!:` and add a `BREAKING CHANGE: <migration for existing projects>` footer.

Do **not** push. Report: summary, files changed, invariant checks, expected semver level, commit hash, and that the user can ask to push (the issue closes on push) or to run `release-template`.
