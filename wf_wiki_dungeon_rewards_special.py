"""Compatibility entry point: this tool now lives in ``wf/tools/wiki/wiki_dungeon_rewards_special.py``.

``python wf_wiki_dungeon_rewards_special.py ...`` and ``import wf_wiki_dungeon_rewards_special`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.wiki.wiki_dungeon_rewards_special")
else:
    from wf.tools.wiki import wiki_dungeon_rewards_special as _implementation

    _sys.modules[__name__] = _implementation
