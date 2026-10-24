"""Tools moved here from the repository root (``wf_<name>.py`` -> ``wf/tools/<group>/<name>.py``).

Each old root file stays as a thin entry point, so ``python wf_<name>.py ...``,
``import wf_<name>`` and the ``.bat`` files keep working.
"""
from __future__ import annotations

import importlib.util
import sys


def run_as_main(name: str) -> None:
    """Run module ``name`` as ``__main__``; ``sys.argv[0]`` keeps the old root path."""
    spec = importlib.util.find_spec(name)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot run {name}")
    module = importlib.util.module_from_spec(spec)
    module.__name__ = "__main__"
    sys.modules["__main__"] = module
    exec(spec.loader.get_code(name), module.__dict__)
