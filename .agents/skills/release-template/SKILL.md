---
name: release-template
description: Release a new version of agile-project-template - collect changes since the last tag, choose the semver bump, update Process version in docs/PROCESS.md, commit, create the annotated vX.Y.Z tag, push and publish a GitHub Release with upgrade notes for existing projects. Run only on explicit user request.
disable-model-invocation: true
---

# Release the template

Rules: `AGENTS.md` of this workspace, §4–§5. Run only because the user explicitly asked. The user's arguments may force a version or a bump level.

Work in `../agile-project-template` (`T` below).

## 1. Checks

1. `T` is on `main`, up to date and the working tree is clean.
2. Find the last release: `git -C T describe --tags --abbrev=0`. If there is no tag yet, the first release uses the current `Process version` unchanged; the range is the whole history.
3. List the changes: `git -C T log --oneline <last-tag>..HEAD` and the issues closed since then (`gh issue list --state closed --search "closed:>=<date of last tag>"`). If there are no changes, stop.
4. Re-run the invariant checks of `AGENTS.md` §3 on the current `main`. Stop if any fails.

## 2. Version

1. Compute the bump from the commits (`AGENTS.md` §4): any `!` / `BREAKING CHANGE` → major; any `feat` → minor; otherwise patch.
2. Propose `vX.Y.Z` to the user with the reasoning and wait for confirmation.
3. Update `**Process version:** X.Y.Z` in `docs/PROCESS.md` (skip if it already matches on the first release).
4. Commit: `chore(release): vX.Y.Z`.

## 3. Tag and publish

```bash
cd ../agile-project-template
git tag -a vX.Y.Z -m "agile-project-template vX.Y.Z"
git push origin main
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file <notes file>
```

Write the notes file in your scratch directory, in English:

```markdown
## Changes
- <one line per change, with (#N)>

## Upgrade existing projects
- Files to copy unchanged: `docs/PROCESS.md`, `.agents/skills/<…>`
- Migration steps: <for major changes, from the BREAKING CHANGE footers; otherwise "none">
- Do it in a `task/` item of the project and check `Process version` = X.Y.Z afterwards.
```

Report: version, tag, release URL, closed issues, and the upgrade notes.
