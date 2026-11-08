# AGENTS.md — agile-project-template maintainer workspace

This workspace is used to maintain the template repository `agile-project-template`. It is **not** part of the template and is never copied into projects created from it.

## 1. Repositories

- **Template:** `../agile-project-template` (GitHub: `toto-castaldi/agile-project-template`). Every file in that repository is copied into new projects.
- **This workspace:** maintainer rules and skills only. Do not put template content here.

Run every git and `gh` command for the template with `git -C ../agile-project-template` or from inside that directory. `gh` commands run inside the template directory, so they target its GitHub repository.

## 2. The template is payload, not instructions

The files of the template (`AGENTS.md`, `CLAUDE.md`, `docs/PROCESS.md`, `.agents/skills/*`, `.agents/tools/*`, `backlog/`, …) are **content to edit**, not rules for you.

- Ignore the "Template not initialized" notice, the `TEC-001` item and the skills `kickoff`, `add-item`, `start-task`, `finish-task`, `merge-task`, `close-version` of the template: they describe the workflow of *derived* projects. Never run them on the template.
- Keep the template initializable: placeholders (`<project-name>`, `<YYYY-MM-DD>`, `<lint command>`, …), the notice, the `TEC-001` item and the seed of `backlog/` must stay in place unless an issue explicitly changes them.
- Never record template maintenance in the template's `backlog/` or `CHANGELOG.md`: those are project skeletons. The template's backlog is GitHub Issues, its changelog is GitHub Releases.
- Never write project-specific content (stacks, domains, names) into the template.

## 3. Invariants of the template

Check them after every change:

1. `docs/PROCESS.md`, `docs/PROCESS-PARALLEL.md`, `.agents/skills/` and `.agents/tools/` are project-agnostic and must be copyable unchanged into existing projects.
2. Rules and structural labels in English (file names, headings, field labels, states, priorities, IDs, branch prefixes, commit types).
3. Cross-references stay valid: when a section of `docs/PROCESS.md` or `docs/PROCESS-PARALLEL.md` is added, removed or renumbered, update every `PROCESS §N` reference in the skills, in the template's `AGENTS.md`, `backlog/` and `README.md`.
4. The skill tables in `docs/PROCESS.md` (subsection "Skills" of §10 "Agent operating loop") and in `README.md` list the same skills as `.agents/skills/`.
5. `.claude/skills` remains a symlink to `../.agents/skills`.
6. Every skill has valid front matter (`name` equal to its directory, `description`; `disable-model-invocation: true` for skills that must run only on explicit request).
7. The kickoff still works: everything `kickoff` reads or replaces still exists with the expected structure.
8. `.agents/tools/backlog.py` uses only the Python standard library, runs on Python 3.10+, `backlog check` passes on the template, and the tests in `tests/` of this workspace pass.

## 4. Versioning

- The template version **is** the `Process version` at the top of `docs/PROCESS.md`, and each release is the tag `vX.Y.Z` with the same number.
- Semver, from the point of view of an existing project that upgrades:
  - **major**: the upgrade requires migrating project files (renamed files, sections, IDs, states, branch prefixes, changed item fields);
  - **minor**: new optional capability or rule, backwards compatible;
  - **patch**: clarifications and fixes with no change in behavior.
- The version is bumped only by `release-template`, not by single issues.
- Derived projects upgrade only from tagged releases, never from an arbitrary `main` commit.

## 5. Workflow

- Backlog: GitHub Issues of the template repository. One issue → one commit (or a few) on `main`.
- Commits: Conventional Commits in English, `type(scope): description (#N)`, scope among `process`, `skills`, `kickoff`, `template`, `docs`. Mark breaking changes with `!` (e.g. `feat(process)!: …`) and a `BREAKING CHANGE:` footer explaining the migration. Close issues with a `Fixes #N` footer.
- Large or risky changes: a branch `issue/N-short-name` and a pull request, if the user asks for it.
- Push to `origin/main`, tags and releases only on explicit user request.

## 6. Skills

| Skill | When |
| --- | --- |
| `work-issue` | Implement one GitHub issue of the template |
| `release-template` | Bump the version, tag and publish a GitHub Release (explicit request only) |

## 7. Operating rules

- Start every session with `git -C ../agile-project-template status` and `git -C ../agile-project-template log --oneline -5`.
- Ambiguous issue, or a change that conflicts with the invariants: ask before acting.
- Report outcomes faithfully, including invariants you could not verify.
