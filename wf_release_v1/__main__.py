"""Module entry point for ``python -m wf_release_v1``."""

from __future__ import annotations

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
