"""Compatibility entry point: this tool now lives in ``wf/tools/art/art_voice_enablement.py``.

``python wf_art_voice_enablement.py ...`` and ``import wf_art_voice_enablement`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.art.art_voice_enablement")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.art.art_voice_enablement")
