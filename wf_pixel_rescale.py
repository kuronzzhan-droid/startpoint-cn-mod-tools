"""Compatibility entry point: this tool now lives in ``wf/tools/art/pixel_rescale.py``.

``python wf_pixel_rescale.py ...`` and ``import wf_pixel_rescale`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.art.pixel_rescale")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.art.pixel_rescale")
