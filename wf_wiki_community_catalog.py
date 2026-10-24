"""Compatibility entry point: this tool now lives in ``wf/tools/wiki/wiki_community_catalog.py``.

``python wf_wiki_community_catalog.py ...`` and ``import wf_wiki_community_catalog`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.wiki.wiki_community_catalog")
else:
    from wf.tools.wiki import wiki_community_catalog as _implementation

    _sys.modules[__name__] = _implementation
