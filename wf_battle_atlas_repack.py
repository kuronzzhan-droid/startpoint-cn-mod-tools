"""Compatibility entry point: this tool now lives in ``wf/tools/art/battle_atlas_repack.py``.

``python wf_battle_atlas_repack.py ...`` and ``import wf_battle_atlas_repack`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.art.battle_atlas_repack")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.art.battle_atlas_repack")
