"""Compatibility entry point: this tool now lives in ``wf/tools/content/content_gacha_candidate.py``.

``python wf_content_gacha_candidate.py ...`` and ``import wf_content_gacha_candidate`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.content_gacha_candidate")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.content.content_gacha_candidate")
