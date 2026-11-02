"""Optional presentation metadata; the original curse/channel text stays intact."""
import json
import math
import re
from urllib.parse import quote


def should_enable(requested: bool | None, existing_subtitles) -> bool:
    """Retain the already-enabled client capability on an ordinary reroll."""
    return requested is True or any("【关卡资料：" in text for text in existing_subtitles)


def for_generated_floor(floor: dict) -> str:
    """Refresh from this roll's final HP audit, never a copied template label."""
    audit = floor["hp_audit"]
    if audit["family"] != "no-boss" and not audit.get("absolute_verified"):
        raise ValueError(f"第 {floor['r']} 层缺少绝对 HP 证据，不能显示估算血量")
    hp = None if audit["family"] == "no-boss" else float(audit["true_hp"])
    return with_details(floor["row"][3], display_enemy(floor["pick"]), hp)


def display_enemy(pick: dict) -> str:
    label = str(pick["label"])
    label = re.sub(r"^(?:HP重排·|血量保底·|专用多阶段·|终局Boss·)+", "", label)
    if re.search(r"[a-z]+_[a-z_0-9]+", label):
        visible = [x.split("\x00", 1)[0] for x in pick.get("thumbnail_evidence", {}).get("boss_visual_identity", [])]
        visible = [x for x in visible if re.search(r"[\u4e00-\u9fff]", x) and "_" not in x]
        return "、".join(dict.fromkeys(visible)) if visible else "多阶段 Boss 战斗"
    return label


def with_details(subtitle: str, enemy: str, hp: float | None) -> str:
    if hp is not None and (not math.isfinite(hp) or hp <= 0):
        raise ValueError("Only verified positive HP may be displayed")
    text = (f"Boss 总血量约 {hp / 1e8:.2f} 亿（包含本关血量诅咒）"
            if hp is not None else "小怪关卡，血量随出场波次分别计算。")
    data = {"enemy": enemy.replace("\x00", ""), "hp": text}
    clean = re.sub(r"\s*【关卡资料：[^】]*】", "", subtitle)
    return clean + " 【关卡资料：" + quote(json.dumps(data, ensure_ascii=False, separators=(",", ":")), safe="") + "】"
