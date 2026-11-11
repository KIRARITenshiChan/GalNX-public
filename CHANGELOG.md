# Changelog

All notable changes to GalNX are documented here. The project follows
[Semantic Versioning](https://semver.org/); the current line is a preview
series, so the minor number moves with the workbench contract rather than with
the game support matrix. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [0.1.0-preview] - 2026-11-11

First public preview of the workbench that ports PC visual novels to Nintendo
Switch by orchestrating existing engines instead of writing new ones.

### Added

- **CLI** `galnx` with eight command families: `doctor`, `preflight`,
  `input`, `package`, `engines`, `payload`, `batch`, `build`
  (`src/galnx/cli.py`).
- **Game manifest** (`schemas/game-manifest.schema.json`) as the single source
  of execution configuration, plus the documented trust boundary: the manifest
  declares commands, so it is executable configuration
  (`docs/MANIFEST.md`).
- **Build contract** (`src/galnx/build/config.py`, `executor.py`):
  `build.commands` and `build.artifact` must be declared together; a manifest
  without commands is `not_configured` instead of a silent success; build
  plans are printed before execution with sensitive environment names masked;
  `build run --dry-run` never spawns a process and `--yes` is required for
  non-interactive execution; exit code 3 means "nothing to execute".
- **Engine adapter registry** with a capability model
  (`src/galnx/engines/`, `docs/engines/`): capabilities are split into
  `graphics` / `movie` / `audio` / `input` / `save` / `touch`, each
  carrying an evidence level (`not_verified` … `game_verified`), and every
  descriptor also carries a top-level verification block. Built-in adapters:
  `krkrsdl2`, `onscripter-nx`, `brewser`; data-driven descriptors ship for
  `rfvp` and `kirikiroid2-nx` (`examples/engines/`).
- **Game-level verification matrix** (`docs/engines/verification-matrix.md`)
  separating engine readiness from per-game / per-build acceptance evidence.
- **Packaging**: `galnx package nsp plan|build|verify`, TitleID rules
  (base aligned to `0x2000`, update `+0x800`, DLC `+0x1000`, reserved
  system ranges), a NACP/metadata builder, and a contract checker
  (`src/galnx/package/`).
- **Payload planning** (`galnx payload plan|materialize`) for self-contained
  romfs trees, plus a keymap contract preserving byte-identical configuration.
- **Batch runner and report schema v2** (`src/galnx/batch/`,
  `schemas/batch-report.schema.json`) reporting `executed` vs
  `not_configured` builds separately from project health.
- **Build cache schema v2** (`src/galnx/build/cache.py`): deterministic
  tree-digest of declared `build.inputs`, toolchain fingerprint over
  devkitA64/GCC, CMake, Ninja, Rust, Cargo.lock and optional FFmpeg/SDL2
  components, and a blocking-versus-degraded distinction: a missing required
  input disables caching, an unknown optional toolchain version still produces
  a deterministic key but adds a `cache.degraded` warning.
- **Public release pipeline** (`scripts/public_release_sanitize.py`,
  `scripts/public_release_publish.py`, `docs/environment/public-release.md`):
  fail-closed sanitizer that drops third-party game art and captured game data,
  blocks high-risk extensions, magic-byte mismatch, credential material and
  personal absolute paths, rewrites markdown references, emits
  `PUBLIC_RELEASE.md`, and can publish the sanitized tree as an independent
  snapshot commit.
- **SBOM and license inventory** (`docs/third_party/inventory.yaml`,
  `scripts/check_license_inventory.py`, `THIRD_PARTY_NOTICES.md`) with
  per-binary link mode, patch provenance, obligations and evidence, plus a
  `runtime-linked` / `runtime-bundled` / `build-only` / `development-only`
  classification.
- **Reusable templates** (`examples/templates/minimal-manifest.yaml`,
  `external-engine-descriptor.yaml`, `input-profile.yaml`) and a test that
  keeps them free of personal absolute paths.
- **CI workflow** (`.github/workflows/ci.yml`) running the test suite, CLI
  smoke commands, the build-plan contract, the SBOM check and the public-tree
  sanitizer on every push and pull request.
- **Device acceptance index** (`docs/pilot/0.1.0-device-acceptance.md`)
  recording which pilot build was verified on hardware, by whom and when.

### Changed

- `pyproject.toml` description now describes the workbench instead of a
  "framework skeleton".
- README rewritten as a project home page: quick start from templates, trust
  boundary, environment variables, document map, release status.
- Engine descriptors no longer pretend every adapter is ready:
  `krkrsdl2`, `onscripter-nx` and `brewser` are marked `research`
  (emulator-level evidence) while `rfvp` and `kirikiroid2-nx` are `ready`
  with hardware acceptance.
- `galnx engines info` prints per-capability verification levels.
- Framework plan bumped to v1.44 (snapshot `docs/PLAN_DRAFT_v1.44.md`).

### Fixed

- Cache entries are no longer written when a required `build.inputs` path is
  missing or unreadable; previously the run silently produced an unstable key.
- Batch reports distinguish "nothing was built because nothing is configured"
  from "the build failed"; the CLI returns 3 instead of 0 in that case.

### Verified

Hardware acceptance (Nintendo Switch, Atmosphère, installed over MTP/DBI) for
four self-contained Chinese-language NSPs, all unsigned homebrew builds:

| Pilot | Game | Version | NSP size | sha256 |
| --- | --- | --- | --- | --- |
| Pilot-01 | 晴霁之后定是菜花盛开的好天气 (Kirikiroid2-NX A10) | 1.0.9 | — | `0efc23f6…` |
| Pilot-02 | 五彩斑斓的世界 HD Re:GENERATION (rfvp) | 1.2.5-test | 10,087,541,464 B | `f6860842…` |
| Pilot-03 | 樱花、萌放。-as the Night's, Reincarnation- (rfvp) | 1.3.3-test | 8,116,841,176 B | `965ee356…` |
| Pilot-04 | 映入红瞳的世界 HD (rfvp) | 1.4.1-test | 6,738,209,496 B | `db31a312…` |

- 737 automated tests + 63 subtests pass on Windows (Python 3.12).
- `galnx package nsp verify` passes for the pilot NSPs (13 checks, 0 fail;
  the only warning is the expected "unsigned homebrew" NCA signature).
- The public mirror contains no game screenshots, covers or captured game data.

### Fixed (post-review FIX round)

- **Non-interactive builds are fail-closed** (`src/galnx/cli.py`): `build run`
  and `batch build` refuse to execute `build.commands` when stdin is not a TTY
  and `--yes` is absent (exit code 2, fixed stderr message, no artifact);
  `_confirm_execution()` treats `EOFError` as a decline so Windows `NUL` no
  longer produces a traceback. Interactive sessions still ask `[y/N]`.
- **Runnable build example** (`examples/quickstart/`): a self-contained
  manifest, deterministic Python packer (`tools/pack_demo.py`, `GALNXPK1`),
  content files and README prove the manifest→plan→execute→cache→artifact
  loop from a clean tree without devkitPro; CI gained a
  `Minimal build example (quickstart)` step.
- **Empty `build.inputs` disables caching** (`src/galnx/build/cache.py`):
  a project that declares `build.commands` without `build.inputs` now gets a
  blocking `build.inputs is not declared: cache disabled for this project`
  reason and neither reads nor writes the cache; the cache payload reports
  `inputs_declared`.
- **Verification levels follow evidence**: Pilot-04 (AKASEKA HD) is reported
  as `device_verified` instead of `game_verified` at the game level because
  the full story / save-load / soak sign-off is missing; the rfvp descriptor,
  verification matrix, engine docs and device-acceptance index were aligned.

### Security

- `prod.keys` / `title.keys` never enter the repository, logs or CI; the NSP
  helpers take an explicit `--keyset` path that stays outside the tree.
- The rfvp runtime statically links an FFmpeg build configured with
  `--enable-gpl` (required for the NVDEC hardware decoders), so a distributed
  NSP is GPL-2.0-or-later as a whole; the workbench code itself stays MIT and
  no NSP binaries are published.
- The public sanitizer fails closed on credential-like strings, private keys,
  personal absolute paths and unknown binaries.

### Known limitations

- Windows is the only supported build host in 0.1.x; cross-platform CI is a
  follow-up.
- `krkrsdl2`, `onscripter-nx` and `brewser` remain emulator-level
  (`research`); no hardware acceptance exists for them.
- Commercial `.xp3` / `.hcb` / game data are never shipped; pilots are
  reproducible from the user's own legally obtained copy.
- Firmware and Atmosphère versions are not recorded in the repository yet.

## [0.1.0-dev] - 2026-10-29 → 2026-11-10

Pre-preview development recorded in `docs/builds/001–052` and
`docs/milestones/M1–M6`: devkitPro toolchain audit, minimum NRO build, KiriKiri
SDL2 bring-up, controller input layer, self-contained NSP packaging, second
engine (Brewser / ONScripter), rfvp Rust backend on the Switch with NVDEC video
decode, save/load hardening, async decode and resource caching, NV12 zero-copy
movie upload, and the first sanitized public snapshot.
