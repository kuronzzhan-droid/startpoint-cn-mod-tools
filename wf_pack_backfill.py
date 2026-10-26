"""Compatibility entry point: this tool now lives in ``wf/tools/share/pack_backfill.py``.

``python wf_pack_backfill.py ...`` and ``import wf_pack_backfill`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.share.pack_backfill")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.share.pack_backfill")
