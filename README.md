# agile-project-template-maint

Maintainer workspace for [`agile-project-template`](https://github.com/toto-castaldi/agile-project-template).

It holds the rules and skills a coding agent (pi, Claude Code) uses to evolve the template **without** the maintenance work leaking into the template itself. Every file of the template is copied into new projects, so the template's backlog lives in GitHub Issues and its changelog in GitHub Releases.

## Setup

Clone both repositories side by side:

```text
scm-projects/
├── agile-project-template/
└── agile-project-template-maint/   ← start the agent here
```

## Usage

```bash
cd agile-project-template-maint
claude        # or pi
```

| Skill | When |
| --- | --- |
| `work-issue <N>` | Implement GitHub issue N of the template and commit on its `main` (no push) |
| `release-template` | Bump `Process version`, tag `vX.Y.Z`, push and publish a GitHub Release (explicit request only) |

Rules: [`AGENTS.md`](AGENTS.md).
