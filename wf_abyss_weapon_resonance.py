"""Compatibility entry point: this tool now lives in ``wf/tools/abyss/abyss_weapon_resonance.py``.

``python wf_abyss_weapon_resonance.py ...`` and ``import wf_abyss_weapon_resonance`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.abyss.abyss_weapon_resonance")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.abyss.abyss_weapon_resonance")
