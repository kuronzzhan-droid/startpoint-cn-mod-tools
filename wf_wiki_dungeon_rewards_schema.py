"""Compatibility entry point: this tool now lives in ``wf/tools/wiki/wiki_dungeon_rewards_schema.py``.

``python wf_wiki_dungeon_rewards_schema.py ...`` and ``import wf_wiki_dungeon_rewards_schema`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.wiki.wiki_dungeon_rewards_schema")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.wiki.wiki_dungeon_rewards_schema")
