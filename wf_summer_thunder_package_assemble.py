#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility facade for the split summer-thunder package assembler."""

from wf_summer_thunder_package_contract import *  # noqa: F401,F403
from wf_summer_thunder_package_sources import *  # noqa: F401,F403
from wf_summer_thunder_package_workspace import *  # noqa: F401,F403


if __name__ == "__main__":
    from wf_summer_thunder_package_cli import main

    raise SystemExit(main())
