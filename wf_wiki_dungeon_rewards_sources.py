"""Compatibility entry point: this tool now lives in ``wf/tools/wiki/wiki_dungeon_rewards_sources.py``.

``python wf_wiki_dungeon_rewards_sources.py ...`` and ``import wf_wiki_dungeon_rewards_sources`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.wiki.wiki_dungeon_rewards_sources")
else:
    from wf.tools.wiki import wiki_dungeon_rewards_sources as _implementation

    _sys.modules[__name__] = _implementation
