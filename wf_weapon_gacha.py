"""Compatibility entry point: this tool now lives in ``wf/tools/weapon/weapon_gacha.py``.

``python wf_weapon_gacha.py ...`` and ``import wf_weapon_gacha`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.weapon.weapon_gacha")
else:
    from wf.tools.weapon import weapon_gacha as _implementation

    _sys.modules[__name__] = _implementation
