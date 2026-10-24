"""Compatibility entry point: this tool now lives in ``wf/tools/assets/decrypt_all.py``.

``python wf_decrypt_all.py ...`` and ``import wf_decrypt_all`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.assets.decrypt_all")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.assets.decrypt_all")
