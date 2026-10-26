"""Compatibility entry point: this tool now lives in ``wf/tools/assets/export_assets.py``.

``python wf_export_assets.py ...`` and ``import wf_export_assets`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.assets.export_assets")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.assets.export_assets")
