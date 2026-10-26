"""Compatibility entry point: this tool now lives in ``wf/tools/content/chain_squash.py``.

``python wf_chain_squash.py ...`` and ``import wf_chain_squash`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.chain_squash")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.content.chain_squash")
