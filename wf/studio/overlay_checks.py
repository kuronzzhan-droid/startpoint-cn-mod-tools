"""Eligibility checks for a pure CDN Overlay, independent of output staging."""
from wf.deliver.changeset import validate_document

from .delivery_checks import delivery_checks
from .drafts import DraftError
from .rehearsal_io import inside, read_json


def check_delivery(folder):
    delivery_checks(folder)
    manifest = read_json(inside(folder, "delivery-manifest.json"))
    requirements = read_json(inside(folder, manifest.get("requires", "requires.json")))
    validate_document(requirements, "requires.schema.json")
    required = requirements["requires"]
    if (manifest.get("server_changes") or required.get("serverFeatures") or required.get("minServerVersion")
            or any(p.is_file() for name in ("server", "server-entries")
                   for p in inside(folder, name).rglob("*") if p.name not in {"README.md", "merge-manifest.json"})):
        raise DraftError("纯 CDN Overlay 不支持服务端改动或服务端依赖")
    assertions = inside(folder, manifest.get("assertions", "assert-box.json"))
    if assertions.is_file() and any(r.get("kind") == "server" for r in read_json(assertions).get("files", [])):
        raise DraftError("纯 CDN Overlay 不支持服务端改动")
    # The repository has no verified vanilla CN 1.8.1 provides profile. Do not
    # borrow test-v34 capabilities or infer them from the compatibleClient label.
    if (required.get("clientCapabilities") or required.get("clientPatches")
            or required.get("capabilityResolution") != "resolved" or required.get("unresolved")):
        raise DraftError("Overlay 无法证明 CN 1.8.1 满足客户端扩展能力；只允许依赖已解析且无扩展的交付")
    return requirements
