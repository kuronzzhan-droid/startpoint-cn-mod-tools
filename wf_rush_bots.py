"""Compatibility entry point: this tool now lives in ``wf/tools/content/rush_bots.py``.

``python wf_rush_bots.py ...`` and ``import wf_rush_bots`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.rush_bots")
else:
    from wf.tools.content import rush_bots as _implementation

    _sys.modules[__name__] = _implementation
