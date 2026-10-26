"""Compatibility entry point: this tool now lives in ``wf/tools/content/gacha_seasonal7_pools.py``.

``python wf_gacha_seasonal7_pools.py ...`` and ``import wf_gacha_seasonal7_pools`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.gacha_seasonal7_pools")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.content.gacha_seasonal7_pools")
