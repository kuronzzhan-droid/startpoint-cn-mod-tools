"""Compatibility entry point: this tool now lives in ``wf/tools/content/gacha_odds_sync.py``.

``python wf_gacha_odds_sync.py ...`` and ``import wf_gacha_odds_sync`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.gacha_odds_sync")
else:
    from wf.tools.content import gacha_odds_sync as _implementation

    _sys.modules[__name__] = _implementation
