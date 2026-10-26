"""Compatibility entry point: this tool now lives in ``wf/tools/wiki/wiki_boss_text.py``.

``python wf_wiki_boss_text.py ...`` and ``import wf_wiki_boss_text`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.wiki.wiki_boss_text")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.wiki.wiki_boss_text")
