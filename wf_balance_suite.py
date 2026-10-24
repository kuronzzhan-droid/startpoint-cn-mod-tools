"""Compatibility entry point: this tool now lives in ``wf/tools/content/balance_suite.py``.

``python wf_balance_suite.py ...`` and ``import wf_balance_suite`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.balance_suite")
else:
    from wf.tools.content import balance_suite as _implementation

    _sys.modules[__name__] = _implementation
