"""Compatibility entry point: this tool now lives in ``wf/tools/release/contract_json.py``.

``python wf_contract_json.py ...`` and ``import wf_contract_json`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.release.contract_json")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.release.contract_json")
