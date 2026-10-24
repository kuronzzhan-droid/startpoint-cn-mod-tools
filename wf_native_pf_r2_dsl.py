"""Compatibility entry point: this tool now lives in ``wf/tools/content/native_pf_r2_dsl.py``.

``python wf_native_pf_r2_dsl.py ...`` and ``import wf_native_pf_r2_dsl`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.native_pf_r2_dsl")
else:
    from wf.tools.content import native_pf_r2_dsl as _implementation

    _sys.modules[__name__] = _implementation
