"""Compatibility entry point: this tool now lives in ``wf/tools/content/enhancement_category_order.py``.

``python wf_enhancement_category_order.py ...`` and ``import wf_enhancement_category_order`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.enhancement_category_order")
else:
    from wf.tools.content import enhancement_category_order as _implementation

    _sys.modules[__name__] = _implementation
