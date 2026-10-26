"""Compatibility entry point: this tool now lives in ``wf/tools/core/battle_rules.py``.

``python wf_battle_rules.py ...`` and ``import wf_battle_rules`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.core.battle_rules")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.core.battle_rules")
