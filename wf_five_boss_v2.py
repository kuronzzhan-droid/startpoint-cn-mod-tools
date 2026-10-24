"""Compatibility entry point: this tool now lives in ``wf/tools/boss/five_boss_v2.py``.

``python wf_five_boss_v2.py ...`` and ``import wf_five_boss_v2`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.boss.five_boss_v2")
else:
    from wf.tools.boss import five_boss_v2 as _implementation

    _sys.modules[__name__] = _implementation
