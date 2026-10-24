"""Compatibility entry point: this tool now lives in ``wf/tools/core/quest_lib.py``.

``python wf_quest_lib.py ...`` and ``import wf_quest_lib`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.core.quest_lib")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.core.quest_lib")
