"""Compatibility entry point: this tool now lives in ``wf/tools/boss/five_boss_node.py``.

``python wf_five_boss_node.py ...`` and ``import wf_five_boss_node`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.boss.five_boss_node")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.boss.five_boss_node")
