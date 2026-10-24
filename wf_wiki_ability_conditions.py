"""Compatibility entry point: this tool now lives in ``wf/tools/wiki/wiki_ability_conditions.py``.

``python wf_wiki_ability_conditions.py ...`` and ``import wf_wiki_ability_conditions`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.wiki.wiki_ability_conditions")
else:
    from wf.tools.wiki import wiki_ability_conditions as _implementation

    _sys.modules[__name__] = _implementation
