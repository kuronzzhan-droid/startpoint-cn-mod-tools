"""Compatibility entry point: this tool now lives in ``wf/tools/content/degree_shop.py``.

``python wf_degree_shop.py ...`` and ``import wf_degree_shop`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.degree_shop")
else:
    from wf.tools.content import degree_shop as _implementation

    _sys.modules[__name__] = _implementation
