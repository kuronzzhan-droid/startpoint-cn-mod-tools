"""Compatibility entry point: this tool now lives in ``wf/tools/core/story_export.py``.

``python wf_story_export.py ...`` and ``import wf_story_export`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.core.story_export")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.core.story_export")
