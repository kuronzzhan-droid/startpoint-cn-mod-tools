"""Conservative runtime closure for registrations compared with the v35e audit.

The context snapshot follows direct method indices, but callproperty only records
its multiname. These reviewed downstream edges therefore need separate proof.
This gate never grants capabilities and does not change pinned method hashes.
"""

# Resistance/charge helpers call ConditionSlot.wfxCollect -> wfxSpec (#112).
# UID rendering (#128) also requires dual-form resource preloading (#21).
PATCH_DEPENDENCIES = {5: {112}, 53: {112}, 115: {112}, 116: {112}, 128: {21}}
# The two R3 table parsers construct GaugeGainRestriction; #31 consumes it.
METHOD_DEPENDENCIES = {"client.equipment.gauge_gain_rules@1": {31}}
# A matching SWF alone cannot close these evidence gaps. Re-enable only after
# adding a reviewed complete method/asset proof, never by version or filename.
PENDING_PATCHES = {
    108: "O8 台座资源未绑定非 SWF 资产证据",
    129: "装备规则的方法基准未覆盖 wfCountEquipment 及完整预载调用上下文",
}


def required_runtime_patches(capability):
    """Dependencies of a capability from a v35e-based registration."""
    needed = set(METHOD_DEPENDENCIES.get(capability["id"], set()))
    for number in capability["provided_by"]["patches"]:
        needed.update(PATCH_DEPENDENCIES.get(number, set()))
    return needed


def filter_runtime_dependencies(patches, standalone, withheld):
    available = {p["number"] for p in patches}
    for number in sorted(available & PENDING_PATCHES.keys()):
        withheld.append({"patch": number, "kind": "incomplete_runtime_evidence",
                         "reason": PENDING_PATCHES[number] + "，待验证，不授予能力"})
        available.remove(number)
    while True:
        rejected = {n for n in available if PATCH_DEPENDENCIES.get(n, set()) - available}
        if not rejected:
            break
        for number in sorted(rejected):
            withheld.append({"patch": number, "kind": "runtime_dependency_unproven",
                             "dependencies": sorted(PATCH_DEPENDENCIES[number] - available),
                             "reason": "下游运行时或资源预载未证明等价，不授予能力"})
        available -= rejected
    methods = []
    for cap in standalone:
        missing = METHOD_DEPENDENCIES.get(cap["id"], set()) - available
        if missing:
            withheld.append({"id": cap["id"], "kind": "runtime_dependency_unproven",
                             "dependencies": sorted(missing),
                             "reason": "解析方法相同不足以证明运行时等价，不授予能力"})
        else:
            methods.append(cap)
    return [p for p in patches if p["number"] in available], methods
