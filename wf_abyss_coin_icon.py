"""Compatibility entry point: this tool now lives in ``wf/tools/abyss/abyss_coin_icon.py``.

``python wf_abyss_coin_icon.py ...`` and ``import wf_abyss_coin_icon`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.abyss.abyss_coin_icon")
else:
    from wf.tools.abyss import abyss_coin_icon as _implementation

    _sys.modules[__name__] = _implementation
