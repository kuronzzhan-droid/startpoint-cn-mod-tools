"""Compatibility entry point: this tool now lives in ``wf/tools/share/share_assets_receive.py``.

``python wf_share_assets_receive.py ...`` and ``import wf_share_assets_receive`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.share.share_assets_receive")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.share.share_assets_receive")
