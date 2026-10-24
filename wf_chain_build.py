"""Compatibility entry point: this tool now lives in ``wf/tools/content/chain_build.py``.

``python wf_chain_build.py ...`` and ``import wf_chain_build`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.chain_build")
else:
    from wf.tools.content import chain_build as _implementation

    _sys.modules[__name__] = _implementation
