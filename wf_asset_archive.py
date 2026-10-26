"""Compatibility entry point: this tool now lives in ``wf/tools/assets/asset_archive.py``.

``python wf_asset_archive.py ...`` and ``import wf_asset_archive`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.assets.asset_archive")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.assets.asset_archive")
