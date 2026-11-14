from pathlib import Path
import vsc


def generate(lang, out_dir: Path):
    server_dir = out_dir / "server"
    server_dir.mkdir(parents=True, exist_ok=True)

    vsc_pkg_parent = str(Path(vsc.__file__).resolve().parent.parent)
    root_path = Path(lang.root_file).resolve()
    root_dir = str(root_path.parent)
    root_module = root_path.stem

    server_py = f"""import importlib
import os
import sys

# 1. Prevent rebuilds & protect LSP stdio pipe
os.environ["VSC_RUNTIME"] = "1"
_RPC_OUT = sys.stdout.buffer
sys.stdout = sys.stderr

# 2. Expose library + user's root file dynamically
sys.path.insert(0, {vsc_pkg_parent!r})
sys.path.insert(0, {root_dir!r})

import vsc
from vsc.runtime import serve

importlib.import_module({root_module!r})
serve(vsc.lang, _RPC_OUT)
"""
    (server_dir / "server.py").write_text(server_py, encoding="utf-8")