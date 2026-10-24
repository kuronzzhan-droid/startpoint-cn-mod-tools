"""Compatibility entry point: this tool now lives in ``wf/tools/weapon/cursed_weapons.py``.

``python wf_cursed_weapons.py ...`` and ``import wf_cursed_weapons`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.weapon.cursed_weapons")
else:
    from wf.tools.weapon import cursed_weapons as _implementation

    _sys.modules[__name__] = _implementation
