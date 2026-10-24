"""Compatibility entry point: this tool now lives in ``wf/tools/art/voice_additions_install.py``.

``python wf_voice_additions_install.py ...`` and ``import wf_voice_additions_install`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.art.voice_additions_install")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.art.voice_additions_install")
