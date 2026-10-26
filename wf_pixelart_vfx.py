"""Compatibility entry point: this tool now lives in ``wf/tools/art/pixelart_vfx.py``.

``python wf_pixelart_vfx.py ...`` and ``import wf_pixelart_vfx`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.art.pixelart_vfx")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.art.pixelart_vfx")
