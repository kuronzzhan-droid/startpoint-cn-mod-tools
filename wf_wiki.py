"""Compatibility entry point: this tool now lives in ``wf/tools/wiki/wiki.py``.

``python wf_wiki.py ...`` and ``import wf_wiki`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.wiki.wiki")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.wiki.wiki")
