"""Compatibility entry point: this tool now lives in ``wf/tools/wiki/wiki_dungeon_rewards_mapping.py``.

``python wf_wiki_dungeon_rewards_mapping.py ...`` and ``import wf_wiki_dungeon_rewards_mapping`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.wiki.wiki_dungeon_rewards_mapping")
else:
    from wf.tools.wiki import wiki_dungeon_rewards_mapping as _implementation

    _sys.modules[__name__] = _implementation
