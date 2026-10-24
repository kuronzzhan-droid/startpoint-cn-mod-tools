"""Compatibility entry point: this tool now lives in ``wf/tools/share/share_update_tables.py``.

``python wf_share_update_tables.py ...`` and ``import wf_share_update_tables`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.share.share_update_tables")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.share.share_update_tables")
