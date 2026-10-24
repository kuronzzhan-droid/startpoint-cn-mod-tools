"""Compatibility entry point: this tool now lives in ``wf/tools/rogue/rogue_reroll.py``.

``python wf_rogue_reroll.py ...`` and ``import wf_rogue_reroll`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.rogue.rogue_reroll")
else:
    from wf.tools.rogue import rogue_reroll as _implementation

    _sys.modules[__name__] = _implementation
