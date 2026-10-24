"""Compatibility entry point: this tool now lives in ``wf/tools/wiki/wiki_variants.py``.

``python wf_wiki_variants.py ...`` and ``import wf_wiki_variants`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.wiki.wiki_variants")
else:
    from wf.tools.wiki import wiki_variants as _implementation

    _sys.modules[__name__] = _implementation
