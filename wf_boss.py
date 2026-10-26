"""Compatibility entry point: this tool now lives in ``wf/tools/boss/boss.py``.

``python wf_boss.py ...`` and ``import wf_boss`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.boss.boss")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.boss.boss")
