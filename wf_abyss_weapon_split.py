"""Compatibility entry point: this tool now lives in ``wf/tools/abyss/abyss_weapon_split.py``.

``python wf_abyss_weapon_split.py ...`` and ``import wf_abyss_weapon_split`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.abyss.abyss_weapon_split")
else:
    from wf.tools.abyss import abyss_weapon_split as _implementation

    _sys.modules[__name__] = _implementation
