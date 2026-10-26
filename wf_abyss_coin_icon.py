"""Compatibility entry point: this tool now lives in ``wf/tools/abyss/abyss_coin_icon.py``.

``python wf_abyss_coin_icon.py ...`` and ``import wf_abyss_coin_icon`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.abyss.abyss_coin_icon")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.abyss.abyss_coin_icon")
