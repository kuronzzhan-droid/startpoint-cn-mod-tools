"""Compatibility entry point: this tool now lives in ``wf/tools/weapon/weapon_gacha_banner.py``.

``python wf_weapon_gacha_banner.py ...`` and ``import wf_weapon_gacha_banner`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.weapon.weapon_gacha_banner")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.weapon.weapon_gacha_banner")
