"""Compatibility entry point: this tool now lives in ``wf/tools/release/remediation_baseline.py``.

``python wf_remediation_baseline.py ...`` and ``import wf_remediation_baseline`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.release.remediation_baseline")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.release.remediation_baseline")
