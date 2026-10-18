"""Reuse delivery inference for a complete per-character reference closure."""
from __future__ import annotations

from wf_quest_lib import build_node

from .facts import CHARACTER
from .requirements import infer_requirements, parse_table


class CharacterRequirements:
    """Whole-roster input is deliberately scanned against an empty character set."""

    def __init__(self, source, registry):
        self.source, self.registry = source, registry
        self.characters = parse_table(source.view.read_raw(CHARACTER)[0], CHARACTER)
        self.cache = {CHARACTER: build_node({})}

    def read_raw(self, logical):
        if logical not in self.cache:
            self.cache[logical] = self.source.view.read_raw(logical)[0]
        return self.cache[logical]

    def infer(self, cid, *, declared=()):
        raw = build_node({cid: self.characters[cid]})
        return infer_requirements({CHARACTER: (raw, {"logical_path": CHARACTER, "root": "common"})},
                                  declared=declared, read_raw=self.read_raw, registry=self.registry)


def merge_requirements(record, inferred, registry):
    """Retain legacy documented facts and add evidence from the delivery scanner."""
    evidence = record["capability_evidence"]
    for item in inferred["capabilityEvidence"]:
        evidence.setdefault(item["id"], []).extend(
            {"source": "requires引用闭包", "detail": detail} for detail in item["evidence"])
    record["capabilities"] = sorted(evidence)
    record["capability_layers"] = {layer: [cid for cid in record["capabilities"]
        if registry[cid]["layer"] == layer] for layer in ("A", "B", "C", "platform")}
    wfx_evidence = any(detail.get("signal") == "unique_string" and
        str(detail.get("value", "")).startswith("wfx:") for item in inferred["capabilityEvidence"]
        for detail in item["evidence"])
    if wfx_evidence:
        record["unregistered_mechanisms"] = [label for label in record["unregistered_mechanisms"]
                                             if label not in {"WFX框架(未上)", "WFX客户端扩展（需注册能力核对）"}]
    for cid in sorted(set(record["capabilities"]) - set(inferred["clientCapabilities"])):
        inferred["capabilityEvidence"].append({"id": cid, "evidence": [{
            "logical_path": "caps.scan/" + record["id"], "signal": "matrix_evidence",
            "value": cid, "details": evidence[cid]}]})
    inferred["clientCapabilities"] = record["capabilities"]
    inferred["clientPatches"] = [f"#{n}" for n in sorted({n for cid in record["capabilities"]
        for n in registry[cid]["provided_by"]["patches"]})]
    inferred["serverFeatures"] = sorted({feature for cid in record["capabilities"]
        for feature in registry[cid]["server"].get("features", [])})
    record["requires"] = inferred
    return record
