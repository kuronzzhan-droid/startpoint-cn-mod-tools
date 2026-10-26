"""Register a local APK using actual SWF observations and a pinned reference audit."""
from __future__ import annotations

from copy import deepcopy
import io
import json
from pathlib import Path
import re
import struct
import tempfile
import zipfile
import zlib

from wf.paths import REPOSITORY
from wf.view.safety import local_output
from .common import SWF_MEMBER
from .evidence import digest, payload_digest, v35e_evidence
from .manifest import identity
from .method_snapshot import snapshot

REFERENCE = "wf/apk/data/v35e-method-contexts.json"


def reference():
    return json.loads((REPOSITORY / REFERENCE).read_text("utf-8"))


def verified_evidence(observations):
    """A complete known method set is required; changed/absent/native rows stay withheld."""
    base = v35e_evidence()
    pinned = reference()
    if pinned["swf_sha256"] != base["swf_sha256"]:
        raise ValueError("local method context reference does not match the reviewed SWF")
    expected = {(m["abc"], m["label"]): m for m in pinned["methods"]}
    actual = {(m["abc"], m["label"]): m for m in observations}
    if len(actual) != len(observations) or set(actual) != set(expected):
        raise ValueError("local observations must cover each reference method exactly once")
    withheld = []

    def proven(method):
        key = method["abc"], method["label"]
        old, new = expected.get(key), actual.get(key)
        return bool(old and new and method["sha256"] == old["sha256"]
                    and new.get("sha256") == old["sha256"]
                    and new.get("context_sha256") == old["context_sha256"])

    def observed(method):
        row = deepcopy(method)
        row["source"] = "实际APK内SWF方法code及引用上下文；与固定v35e基线一致"
        return row

    patches = []
    for patch in base["patches"]:
        unproven = [m for m in patch["methods"] if not proven(m)]
        if unproven:
            withheld.append({"patch": patch["number"], "reason": "未证明等价，不声明支持或不支持",
                             "methods": [m["label"] for m in unproven],
                             "kind": "method_changed" if all(m["sha256"] for m in unproven)
                             else "non_swf_evidence_required"})
        else:
            patches.append({**patch, "methods": [observed(m) for m in patch["methods"]],
                            "basis": "实际方法code与引用上下文均等于固定v35e基线"})
    standalone = []
    for cap in base.get("method_capabilities", []):
        if all(proven(m) for m in cap["methods"]):
            standalone.append({**cap, "methods": [observed(m) for m in cap["methods"]]})
        else:
            withheld.append({"id": cap["id"], "reason": "独立方法未证明等价，不授予能力"})
    return {"schema": "wf-apk-summary/1", "patches": patches,
            "method_capabilities": standalone, "official_systems": False}, withheld


def inspect_local(filename):
    try:
        return _inspect_local(filename)
    except (KeyError, IndexError, struct.error, zipfile.BadZipFile, zlib.error, AssertionError) as error:
        raise ValueError("cannot parse local APK: " + type(error).__name__) from error


def _inspect_local(filename):
    path = Path(filename).resolve()
    if path.suffix.lower() != ".apk":
        raise ValueError("register-local requires an actual .apk")
    data = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        payload_sha = payload_digest(archive)
        package = identity(archive.read("AndroidManifest.xml"))
        if package["package_name"] != "com.leiting.wf":
            raise ValueError("register-local only accepts local package com.leiting.wf, not test-server packages")
        swf = archive.read(SWF_MEMBER)
    old = reference()
    observations = snapshot(swf, {(m["abc"], m["label"]) for m in old["methods"]})
    rows = [{"abc": a, "label": label, **value} for (a, label), value in sorted(observations.items())]
    record, withheld = verified_evidence(rows)
    if not record["patches"]:
        raise ValueError("no complete reviewed patch evidence; local client registration refused")
    source = {"kind": "apk", "path": str(path), "sha256": digest(data),
              "swf_sha256": digest(swf), "payload_sha256": payload_sha,
              "basis": "实际APK/SWF方法code和引用上下文与固定v35e基线比较；本地自用，非测试服包"}
    return {"schema": "wf-local-client/1", "source": source, "package": package,
            "reference_swf_sha256": old["swf_sha256"], "observations": rows,
            "withheld": withheld}


def provides_for(registration, registry=None):
    from wf.caps.registry import load_registry
    from .local_registry import with_registration
    from .provides import derive_provides
    record, withheld = verified_evidence(registration["observations"])
    record["swf_sha256"] = registration["source"]["swf_sha256"]
    registry = with_registration(registry or load_registry(), registration)
    result = derive_provides(record, registration["source"], registry)
    result["warnings"].extend(withheld)
    result["limitations"].append("只提供已证明等价的方法能力；withheld表示证据不足，不等于不支持；未授予官方系统或native/ANE能力")
    return result


def encode(document):
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def profile_for(registration, provides, filename):
    from wf.caps.profiles import load_profiles
    _, profiles = load_profiles()
    prior = profiles["test-v35e"]
    available = {row["id"] for row in provides["provides"]}
    catalog = json.loads((REPOSITORY / "wfx_registry.json").read_text("utf-8"))
    legacy = []
    for name in prior["capabilities"]:
        item = catalog["capabilities"].get(name, {})
        cid = item.get("capability_id") or prior["evidence"].get("capability_methods", {}).get(name, {}).get("capability_id")
        patches = prior["evidence"].get("capability_patches", {}).get(name, [])
        if ((cid and cid in available) or
                (patches and all(f"client.apk.patch{n:03d}@1" in available for n in patches))):
            legacy.append(name)
    sha = digest(encode(provides))
    return {"label": registration["profile_id"] + "（本地自用，非测试服包）",
            "description": "本地自用com.leiting.wf；不是测试服包；仅静态方法证据，不声明安装或部署",
            **registration["package"], "provides": filename, "provides_sha256": sha,
            "capabilities": sorted(legacy), "m2_capabilities": sorted(available),
            "evidence": {"apk_sha256": registration["source"]["sha256"],
                         "swf_sha256": registration["source"]["swf_sha256"],
                         "swf_path": registration["source"]["path"],
                         "verification": "local_offline_only",
                         "test_server_package": False},
            "update_rule": "wf apk register-local <apk>；真实方法及上下文比较；不根据版本名授予能力"}


def register_local(filename, *, profile=None):
    from .local_registry import LOCAL, registrations
    path = Path(filename)
    if profile is None:
        match = re.match(r"(v35[a-z0-9]*)-", path.name, re.I)
        if not match:
            raise ValueError("APK filename must start v35...- or specify --profile local-...")
        profile = "local-" + match[1].lower()
    if not re.fullmatch(r"local-[a-z0-9][a-z0-9-]{0,63}", profile):
        raise ValueError("local profile ID must match local-[a-z0-9-]+")
    registration = inspect_local(path)
    registration["profile_id"] = profile
    current = next((r for r in registrations() if r["profile_id"] == profile), None)
    if current:
        if current["source"]["sha256"] != registration["source"]["sha256"]:
            raise ValueError("profile already identifies another APK; choose a new --profile")
        return {"ok": True, "profile": profile, "status": "already_registered",
                "apk_sha256": registration["source"]["sha256"], "withheld": registration["withheld"]}
    from wf.caps.profiles import load_profiles
    if profile in load_profiles()[1]:
        raise ValueError("profile ID belongs to an existing client profile")
    out = local_output(REPOSITORY / LOCAL / profile, root=REPOSITORY)
    if out.exists():
        raise ValueError("registration output already exists; refusing to overwrite")
    provides = provides_for(registration)
    registration["profile"] = profile_for(registration, provides, f"{LOCAL}/{profile}/provides.json")
    pending = local_output(REPOSITORY / LOCAL / ".pending", root=REPOSITORY)
    pending.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=profile + "-", dir=pending) as folder:
        staged = Path(folder)
        (staged / "provides.json").write_bytes(encode(provides))
        (staged / "registration.json").write_bytes(encode(registration))
        if out.exists():
            raise ValueError("registration output appeared concurrently; refusing to overwrite")
        staged.rename(out)
    return {"ok": True, "profile": profile, "status": "registered",
            "apk_sha256": registration["source"]["sha256"],
            "swf_sha256": registration["source"]["swf_sha256"],
            "capabilities": len(provides["provides"]), "withheld": registration["withheld"]}
