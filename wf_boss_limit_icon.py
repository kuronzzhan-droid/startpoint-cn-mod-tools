"""Compatibility entry point: this tool now lives in ``wf/tools/boss/boss_limit_icon.py``.

``python wf_boss_limit_icon.py ...`` and ``import wf_boss_limit_icon`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.boss.boss_limit_icon")
else:
    from wf.tools.boss import boss_limit_icon as _implementation

    _sys.modules[__name__] = _implementation
