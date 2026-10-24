"""Compatibility entry point: this tool now lives in ``wf/tools/content/content_gacha_candidate.py``.

``python wf_content_gacha_candidate.py ...`` and ``import wf_content_gacha_candidate`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.content_gacha_candidate")
else:
    from wf.tools.content import content_gacha_candidate as _implementation

    _sys.modules[__name__] = _implementation
