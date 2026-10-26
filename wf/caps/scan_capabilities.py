"""Project scanned facts into registry IDs, retaining the evidence for each claim."""
from .scan_facts import PER_CHAR_APK, SYSTEM_KINDS

LABEL_IDS = {
    SYSTEM_KINDS[("during", "422")]: "client.kind422.dash@1",
    SYSTEM_KINDS[("during", "423")]: "client.kind423.gauge_source_limit@1",
    SYSTEM_KINDS[("during", "424")]: "client.kind424.damage_convert@1",
    SYSTEM_KINDS[("instant", "724")]: "client.kind724.fever_ratio@1",
    "伤害类型转换buffTargetAs(APK#20)": "client.kind424.damage_convert@1",
    "PF Lv4(APK#87-89)": "client.pf.level4@1",
    "Fever箭头换道具(APK#90-93)": "client.fever.items@1",
    "超限Lv120(APK#78-86,101,108-111+服务端)": "client.overlimit.lv120@1",
    "充能上限固有13999010(APK#53)": "client.charge.cap@1",
    "hidden_固有隐藏(APK#58)": "client.unique.hidden@1",
    "ModDualForm双形态(APK#21)": "client.dual_form@1",
    "凯尔直击参数(APK#54/#56)": "client.direct.parameters@1",
    "文案覆盖desc_override(APK#02)": "client.text.desc_override@1",
    "通用准备语音轮换(APK#94-96)": "client.voice.rotation@1",
    "白晒伤减抗(APK#05)": "client.unique.sunburn@1",
    "白Fever语音路由(APK#06)": "client.apk.patch006@1",
    "准备音轮换129992(APK#07/#15)": ("client.apk.patch007@1", "client.apk.patch015@1"),
    "准备音(APK#15)": "client.apk.patch015@1",
    "准备音轮换149999(APK#65)": "client.apk.patch065@1",
    "PF追加命中静默(APK#55)": "client.apk.patch055@1",
    "稻穗视觉预载(APK#32)": "client.apk.patch032@1",
    "九尾PF连击快照(APK#01)": "client.apk.patch001@1",
}


def project_character(record, names, registry, *, unison_abilities=()):
    evidence = {}

    def add(capability_id, source, detail):
        if capability_id not in registry:
            raise ValueError(f"unregistered scanner capability: {capability_id}")
        evidence.setdefault(capability_id, []).append({"source": source, "detail": detail})

    unknown = []
    for label in record["apk"]:
        ids = LABEL_IDS.get(label)
        if ids is None:
            unknown.append(label)
            continue
        source = "文档中的角色专用补丁映射" if label in PER_CHAR_APK.get(record["id"], []) else "扫描数据"
        for capability_id in (ids if isinstance(ids, tuple) else (ids,)):
            add(capability_id, source, label)
    for field, capability_id in (("pf_overrides", "official.pf.special@1"),
                                 ("invoke", "official.kind629.invoke_skill@1"),
                                 ("unison", "official.unison@1")):
        if record[field]:
            add(capability_id, "扫描数据", field)
    if record["awake_rows"] or record["awake_event"] != "无":
        add("official.awakening@1", "扫描数据", "awake_rows / awake_event")
    if unison_abilities:
        add("official.unison@1", "扫描数据", {"first_row_c1_true": list(unison_abilities)})
    layers = {layer: [] for layer in ("A", "B", "C", "platform")}
    for capability_id in sorted(evidence):
        layers[registry[capability_id]["layer"]].append(capability_id)
    return {**record, "capabilities": sorted(evidence), "capability_layers": layers,
            "capability_evidence": evidence, "unregistered_mechanisms": unknown,
            "layer_c": names.get(record["id"], {"mech": [], "docs": []})}


def compare_records(records, reference):
    """Compare every historical fact, not just counts or selected badges."""
    if not isinstance(reference, list) or any(not isinstance(r, dict) or "id" not in r for r in reference):
        raise ValueError("reference scan must be a list of character records")
    before = {r["id"]: r for r in reference}
    after = {r["id"]: r for r in records}
    if len(before) != len(reference) or len(after) != len(records):
        raise ValueError("duplicate character ID in matrix comparison")
    differences = []
    for cid in sorted(before.keys() | after.keys()):
        if cid not in before or cid not in after:
            differences.append({"id": cid, "field": "character", "before": before.get(cid),
                                "after": after.get(cid), "reason": "角色在所选链尾新增或删除"})
            continue
        for field in sorted(before[cid].keys() | after[cid].keys()):
            if before[cid].get(field) == after[cid].get(field):
                continue
            reason = ("四张战斗表的逐版本改写记录延伸到所选链尾" if field == "provenance" else
                      "所选链尾的扫描字段发生变化；before/after 保留完整值，须核对对应版本数据")
            differences.append({"id": cid, "field": field, "before": before[cid].get(field),
                                "after": after[cid].get(field), "reason": reason})
    return {"reference_count": len(before), "current_count": len(after),
            "same_ids": before.keys() == after.keys(), "difference_count": len(differences),
            "differences": differences}
