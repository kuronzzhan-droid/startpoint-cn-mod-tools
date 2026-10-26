"""Compatibility entry point: this tool now lives in ``wf/tools/art/studio_effect_pack.py``.

``python wf_studio_effect_pack.py ...`` and ``import wf_studio_effect_pack`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.art.studio_effect_pack")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.art.studio_effect_pack")
