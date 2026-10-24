"""Compatibility entry point: this tool now lives in ``wf/tools/character/character_rollback.py``.

``python wf_character_rollback.py ...`` and ``import wf_character_rollback`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.character.character_rollback")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.character.character_rollback")
