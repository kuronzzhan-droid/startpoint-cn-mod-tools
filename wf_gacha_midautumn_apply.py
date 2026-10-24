"""Compatibility entry point: this tool now lives in ``wf/tools/content/gacha_midautumn_apply.py``.

``python wf_gacha_midautumn_apply.py ...`` and ``import wf_gacha_midautumn_apply`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.gacha_midautumn_apply")
else:
    from wf.tools.content import gacha_midautumn_apply as _implementation

    _sys.modules[__name__] = _implementation
