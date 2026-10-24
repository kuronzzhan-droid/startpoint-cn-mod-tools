"""Compatibility entry point: this tool now lives in ``wf/tools/core/openai.py``.

``python wf_openai.py ...`` and ``import wf_openai`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.core.openai")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.core.openai")
