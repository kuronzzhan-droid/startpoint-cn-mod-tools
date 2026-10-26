"""Digest-bound local registrations supplement, never replace, reviewed registry data."""
from copy import deepcopy
import json
from pathlib import Path

from wf.paths import REPOSITORY

BUILTIN = "wf/apk/data/local-v35k3-registration.json"
LOCAL = "work/local-clients"


def registrations(root=None):
    root = Path(root or REPOSITORY)
    paths = [root / BUILTIN, *sorted((root / LOCAL).glob("*/registration.json"))]
    seen = {}
    for path in paths:
        if not path.is_file():
            continue
        record = json.loads(path.read_text("utf-8"))
        if record.get("schema") != "wf-local-client/1":
            raise ValueError("invalid local client registration")
        name = record["profile_id"]
        if name in seen:
            if seen[name]["source"]["sha256"] != record["source"]["sha256"]:
                raise ValueError("conflicting local client registration: " + name)
            continue
        seen[name] = record
        yield record


def find(swf_sha256, *, apk_sha256=None):
    return next((row for row in registrations()
                 if row["source"]["swf_sha256"] == swf_sha256
                 and (apk_sha256 is None or row["source"]["sha256"] == apk_sha256)), None)


def with_registration(registry, registration):
    """Use only method records whose context matches the checked-in v35e snapshot."""
    from .register_local import verified_evidence
    from wf.caps.method_evidence import selected_method_hash
    evidence, _ = verified_evidence(registration["observations"])
    swf_sha = registration["source"]["swf_sha256"]
    actual = {(m["patch"], m["abc"], m["label"]): m["sha256"]
              for patch in evidence["patches"] for m in patch["methods"]}
    for cap in evidence["method_capabilities"]:
        actual.update({(m["patch"], m["abc"], m["label"]): m["sha256"] for m in cap["methods"]})
    output = deepcopy(registry)
    for capability in output.values():
        provider = capability["provided_by"]
        methods = provider["methods"]
        if not methods or any((m["patch"], m["abc"], m["label"]) not in actual for m in methods):
            continue
        if any(selected_method_hash(m, registration["reference_swf_sha256"]) !=
               actual[(m["patch"], m["abc"], m["label"])] for m in methods):
            continue  # A caller's stricter/custom registry must not be broadened.
        if any(v["swf_sha256"] == swf_sha and v["sha256"] != actual[(m["patch"], m["abc"], m["label"])]
               for m in methods for v in m.get("accepted_variants", [])):
            continue
        for method in methods:
            key = method["patch"], method["abc"], method["label"]
            variants = [v for v in method.get("accepted_variants", []) if v["swf_sha256"] != swf_sha]
            variants.append({"swf_sha256": swf_sha, "sha256": actual[key],
                             "source": "wf apk register-local: actual method/context comparison",
                             "reason": "实际方法code、引用常量/namespace/签名/异常表与已核v35e逐项相同"})
            method["accepted_variants"] = variants
        if provider.get("swf_sha256") and swf_sha not in provider["swf_sha256"]:
            provider["swf_sha256"].append(swf_sha)
    return output


def for_swf(registry, swf_sha256):
    record = find(swf_sha256) if swf_sha256 else None
    return with_registration(registry, record) if record else registry
