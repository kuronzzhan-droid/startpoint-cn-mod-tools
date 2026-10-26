"""Compatibility entry point: this tool now lives in ``wf/tools/content/paradox_weapon.py``.

``python wf_paradox_weapon.py ...`` and ``import wf_paradox_weapon`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.paradox_weapon")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.content.paradox_weapon")
