"""Compatibility entry point for the packaged prepush checker."""
from wf.deliver.prepush import *

if __name__ == "__main__":
    raise SystemExit(main())
