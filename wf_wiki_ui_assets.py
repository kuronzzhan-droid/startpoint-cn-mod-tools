"""Compatibility entry point: this tool now lives in ``wf/tools/wiki/wiki_ui_assets.py``.

``python wf_wiki_ui_assets.py ...`` and ``import wf_wiki_ui_assets`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.wiki.wiki_ui_assets")
else:
    from wf.tools.wiki import wiki_ui_assets as _implementation

    _sys.modules[__name__] = _implementation
