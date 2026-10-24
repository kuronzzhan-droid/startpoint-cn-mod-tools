"""Compatibility entry point: this tool now lives in ``wf/tools/wiki/wiki_equipment_forms.py``.

``python wf_wiki_equipment_forms.py ...`` and ``import wf_wiki_equipment_forms`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.wiki.wiki_equipment_forms")
else:
    from wf.tools.wiki import wiki_equipment_forms as _implementation

    _sys.modules[__name__] = _implementation
