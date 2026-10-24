"""Compatibility entry point: this tool now lives in ``wf/tools/content/bond_weapon_enhance.py``.

``python wf_bond_weapon_enhance.py ...`` and ``import wf_bond_weapon_enhance`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.bond_weapon_enhance")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.content.bond_weapon_enhance")
