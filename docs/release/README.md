# docs/release

Release-facing documentation for GalNX.

| File | Purpose |
| --- | --- |
| `0.1.0-preview.md` | Release notes for the current preview: scope, verified artifacts, requirements, known limitations, release-gate results. |
| `expert-review-0.1.0.md` | External review plan that drove the 0.1.0 convergence (audit baseline, P0/P1/P2 task list, release checklist), kept with its §11 execution-status and deviations record after completion. |
| `tasks/` | Implementation reports produced while converging on 0.1.0 (`TASK-*.md`) while closing the post-review fix round (`FIX-01.md` … `FIX-06.md`; FIX-03 and FIX-05 share one report), and the third-round cleanup (`CLEAN-01-04.md`). Each report follows the fixed format: task id, source commit, files changed, observed problem, decision, behaviour before/after, tests, commands, deviations, limitations, rollback. |

## Versioning and release process

- The workbench version lives in `pyproject.toml` and is reported by
  `galnx --version`; tags are annotated `v<version>` on the private
  development repository.
- The public mirror `GalNX-public` receives one snapshot commit per release
  event (milestone, hardware acceptance, or plan revision), never the private
  history. Each snapshot commit message records the private source commit.
- Release notes are written before the snapshot is published, then the snapshot
  numbers (`PUBLIC_RELEASE.md`) are appended so that a reader can reproduce
  what was actually published.
- A release is only published when the release gate in
  `0.1.0-preview.md` §8 passes on the maintainer's Windows host; CI covers the
  portable subset (`.github/workflows/ci.yml`).

## Changelog

See [`CHANGELOG.md`](../../CHANGELOG.md) at the repository root.
