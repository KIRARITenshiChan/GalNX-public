# GalNX quickstart

The smallest example that runs the complete manifest -> build -> artifact ->
cache loop with **Python only**. It is not a game template: it packs two text
assets into a deterministic `out/demo.pak` so you can watch GalNX execute a
declared build command, verify the artifact and reuse the cached result.

## Run it

From the repository root (the preflight check resolves `game.source_dir`
against the current directory):

```bash
python -m pip install -e .
PYTHONPATH=src python -m galnx build run --manifest examples/quickstart/manifest.yaml --yes
```

The first run executes the packer:

```
build: 1 executed, 0 not configured, 0 cache hit(s)
  [OK] examples/quickstart/manifest.yaml  adapter=krkrsdl2  ...  build=executed
```

Run the same command again and nothing is executed:

```
cache: 1 hit(s), 0 miss(es); built 0
build: 0 executed, 0 not configured, 1 cache hit(s)
```

Edit `content/demo.txt` and run it once more: the cache misses, the packer
runs again and `out/demo.pak` changes.

## Files

| Path | Purpose |
| --- | --- |
| `manifest.yaml` | Declares the build contract (`build.commands`, `build.artifact`, `build.inputs`). |
| `tools/pack_demo.py` | Deterministic packer (standard library only); writes `out/demo.pak`. |
| `content/` | Two tiny text assets; the only build inputs. |
| `out/demo.pak` | Generated artifact (untracked); delete it to force a rebuild. |

## What this demonstrates

- `build.commands` is real configuration: the CLI runs it and records logs
  under `.galnx/logs/`.
- `build.artifact` is verified after the command; a missing artifact fails the
  build.
- `build.inputs` feeds the content-addressed cache; without it GalNX refuses
  to cache (the key could not describe the inputs).
- `engine.adapter` is carried for schema/registry compatibility. No engine
  toolchain is invoked here, so the example works on any machine with Python.

Generated paths (`out/`, `.galnx/`) are ignored by git; remove them to start
from a clean state.
