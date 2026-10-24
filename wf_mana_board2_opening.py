"""Compatibility entry point: this tool now lives in ``wf/tools/content/mana_board2_opening.py``.

``python wf_mana_board2_opening.py ...`` and ``import wf_mana_board2_opening`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.mana_board2_opening")
else:
    from wf.tools.content import mana_board2_opening as _implementation

    _sys.modules[__name__] = _implementation
