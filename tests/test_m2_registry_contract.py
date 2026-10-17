"""Registration cannot silently omit one component's method evidence."""
from copy import deepcopy

import pytest
from wf.caps.registry import load_registry, validate_capability


def test_each_required_patch_needs_method_or_explicit_null():
    cap = deepcopy(load_registry()["client.pf.level4@1"])
    cap["provided_by"]["methods"] = [m for m in cap["provided_by"]["methods"] if m["patch"] == 87]
    with pytest.raises(ValueError, match="lack method evidence"):
        validate_capability(cap)


def test_duplicate_method_evidence_is_rejected():
    cap = deepcopy(load_registry()["client.pf.level4@1"])
    cap["provided_by"]["methods"].append(deepcopy(cap["provided_by"]["methods"][0]))
    with pytest.raises(ValueError, match="duplicate method"):
        validate_capability(cap)
