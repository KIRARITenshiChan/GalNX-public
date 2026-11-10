# GalNX public release tree

This directory is a sanitized snapshot, not the full repository.

- Source commit: 7306669
- Generated (UTC): 2026-11-10T12:13:58Z
- Kept tracked files: 967
- Excluded game-art files: 351
- Markdown references rewritten: 0 in 0 files

## Why some files are missing

GalNX keeps Citron/hardware screenshots, per-title covers and icons as
development evidence. They show commercial game art whose copyright belongs
to the respective publishers, so they are excluded from the public tree:

- docs/assets/: 4 files
- docs/milestones/: 342 files
- examples/pilot: 5 files

The full list is in PUBLIC_RELEASE_ART_EXCLUSIONS.txt. Those files remain in the private repository and can
be restored only with the copyright holders permission.

Markdown references that pointed at excluded art were rewritten during export
(images replaced by a placeholder, plain links reduced to their label), so the
public docs do not link to files that are not part of this tree.

## Licensing

- Project code and docs: MIT, see LICENSE.
- Engine patches: follow their upstream licenses, see THIRD_PARTY_NOTICES.md
  and docs/builds/patches/LICENSE.md.
- No game data, prod.keys, title.keys or Nintendo certificates are included.

## Publishing

Push this tree as a fresh repository or an orphan branch (see
docs/environment/public-release.md): the private history still contains the
excluded images, so pushing the original history would republish them.
