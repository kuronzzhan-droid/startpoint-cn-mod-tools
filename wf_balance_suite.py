"""Compatibility entry point: this tool now lives in ``wf/tools/content/balance_suite.py``.

``python wf_balance_suite.py ...`` and ``import wf_balance_suite`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.balance_suite")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.content.balance_suite")
