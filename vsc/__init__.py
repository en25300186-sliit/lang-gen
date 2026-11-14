import inspect
import os
import sys
from pathlib import Path
from .core import Language, Syntax, AutoClose, Scope
from .generators import run_all

lang = Language()


def build(out_dir: str = "./dist", target: Language | None = None):
    if os.environ.get("VSC_RUNTIME") == "1":
        return

    active = target or lang
    if not active.root_file:
        main_mod = sys.modules.get("__main__")
        main_file = getattr(main_mod, "__file__", None) if main_mod else None
        if main_file:
            active.root_file = os.path.abspath(main_file)
        else:
            active.root_file = os.path.abspath(inspect.stack()[1].filename)

    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    run_all(active, out)
    print(f"[vsc] Built '{active.name}' ({active.id}) -> {out}")


__all__ = ["lang", "Language", "Syntax", "AutoClose", "Scope", "build"]