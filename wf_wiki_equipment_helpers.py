"""Compatibility entry point: this tool now lives in ``wf/tools/wiki/wiki_equipment_helpers.py``.

``python wf_wiki_equipment_helpers.py ...`` and ``import wf_wiki_equipment_helpers`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.wiki.wiki_equipment_helpers")
else:
    from wf.tools.wiki import wiki_equipment_helpers as _implementation

    _sys.modules[__name__] = _implementation
