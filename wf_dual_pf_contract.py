"""Compatibility entry point: this tool now lives in ``wf/tools/content/dual_pf_contract.py``.

``python wf_dual_pf_contract.py ...`` and ``import wf_dual_pf_contract`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.dual_pf_contract")
else:
    from wf.tools.content import dual_pf_contract as _implementation

    _sys.modules[__name__] = _implementation
