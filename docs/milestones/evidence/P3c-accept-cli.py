
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(r"E:\Othergames\Nintendo Switch\Workspace\GalNX")
env = dict(os.environ)
gitdir = r"D:\Scoop\apps\git\current\bin"
parts = env.get("PATH", "").split(os.pathsep)
env["PATH"] = os.pathsep.join([gitdir] + [p for p in parts if p and p.lower() != gitdir.lower()])
env["PYTHONPATH"] = str(ROOT / "src")
args = [sys.executable, "-m", "galnx", "engines", "prepare",
        "--descriptor", "examples/engines/kirikiroid2-nx.yaml",
        "--dest", r"E:\galnx-build\pilot-01\k2nx-src",
        "--check-only", "--json"]
cp = subprocess.run(args, cwd=str(ROOT), env=env, capture_output=True, text=True)
Path(r"E:\galnx-build\p3c\acceptance-cli-check-only.json").write_text(cp.stdout, encoding="utf-8")
Path(r"E:\galnx-build\p3c\acceptance-cli-check-only.log").write_text(cp.stderr, encoding="utf-8")
print("RC", cp.returncode)
print("STDOUT", cp.stdout[:4000])
print("STDERR", cp.stderr[:4000])
