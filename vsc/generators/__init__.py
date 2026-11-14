import importlib
import pkgutil
from pathlib import Path


def run_all(lang, out_dir: Path):
    for mod_info in pkgutil.iter_modules(__path__):
        mod = importlib.import_module(f"{__name__}.{mod_info.name}")
        gen = getattr(mod, "generate", None)
        if callable(gen):
            gen(lang, out_dir)