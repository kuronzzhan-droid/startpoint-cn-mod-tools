"""Compatibility entry point: this tool now lives in ``wf/tools/content/enhancement_policy.py``.

``python wf_enhancement_policy.py ...`` and ``import wf_enhancement_policy`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.enhancement_policy")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.content.enhancement_policy")
