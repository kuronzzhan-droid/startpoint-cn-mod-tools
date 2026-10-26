"""Compatibility entry point: this tool now lives in ``wf/tools/release/server_auth.py``.

``python wf_server_auth.py ...`` and ``import wf_server_auth`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.release.server_auth")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.release.server_auth")
