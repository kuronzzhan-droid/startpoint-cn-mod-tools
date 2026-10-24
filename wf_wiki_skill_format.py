"""Compatibility entry point: this tool now lives in ``wf/tools/wiki/wiki_skill_format.py``.

``python wf_wiki_skill_format.py ...`` and ``import wf_wiki_skill_format`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.wiki.wiki_skill_format")
else:
    from wf.tools.wiki import wiki_skill_format as _implementation

    _sys.modules[__name__] = _implementation
