"""Compatibility entry point: this tool now lives in ``wf/tools/content/degree.py``.

``python wf_degree.py ...`` and ``import wf_degree`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.degree")
else:
    from wf.tools.content import degree as _implementation

    _sys.modules[__name__] = _implementation
