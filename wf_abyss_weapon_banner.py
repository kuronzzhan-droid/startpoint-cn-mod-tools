"""Compatibility entry point: this tool now lives in ``wf/tools/abyss/abyss_weapon_banner.py``.

``python wf_abyss_weapon_banner.py ...`` and ``import wf_abyss_weapon_banner`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.abyss.abyss_weapon_banner")
else:
    from wf.tools.abyss import abyss_weapon_banner as _implementation

    _sys.modules[__name__] = _implementation
