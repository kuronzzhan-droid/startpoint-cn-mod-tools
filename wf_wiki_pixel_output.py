"""Compatibility entry point: this tool now lives in ``wf/tools/wiki/wiki_pixel_output.py``.

``python wf_wiki_pixel_output.py ...`` and ``import wf_wiki_pixel_output`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.wiki.wiki_pixel_output")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.wiki.wiki_pixel_output")
