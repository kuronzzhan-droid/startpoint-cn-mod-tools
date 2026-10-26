"""Reported p12/p13 extensions; no implicit inheritance of older APK evidence."""
import csv
import io
import re

PREFIXES = {
    "wfx_summon_flip_pf_": "client.summon.flip_pf@1",
    "wfx_ball_pf_action_": "client.ball.pf_action@1",
}
DEGRADED = {
    "client.summon.cutin_preload@1": "召唤球主动技能 cutin 预载不可确认",
    "client.combo.base@1": "常驻连击基数不可用",
    "client.pf.dual@1": "双实体同批强化弹射不可用",
    "client.summon.flip_pf@1": "召唤球弹起 PF 不可用",
    "client.ball.pf_action@1": "协力球退回原生类型 PF",
}


def decimal_int32(value, *, positive=False):
    pattern = r"[1-9][0-9]*" if positive else r"(?:0|[1-9][0-9]*)"
    return bool(re.fullmatch(pattern, value)) and len(value) <= 10 and int(value) <= 2147483647


def config_problems(key, value):
    """Validate a decoded single-column value; references are checked by studio."""
    prefix = next((p for p in PREFIXES if key.startswith(p)), None)
    if prefix is None:
        return []
    errors = []
    if not decimal_int32(key[len(prefix):], positive=True):
        errors.append("multiball 编号须为规范十进制正 int32（不允许前导零）")
    if value is None:
        return errors
    if prefix == "wfx_summon_flip_pf_":
        fields = value.split(":")
        if not (fields == ["1"] or (len(fields) == 2 and fields[0] == "1"
                                   and decimal_int32(fields[1]))):
            errors.append("值须为 1 或 1:<规范十进制非负 int32 最小间隔帧>")
    elif not value or value.strip() != value or any(c in value for c in "\r\n"):
        errors.append("PF 动作键须为非空、无首尾空白的单列值")
    return errors


def decode_config_row(value):
    """Use the table CSV contract, including quoted one-column values."""
    if not isinstance(value, str):
        raise ValueError("扩展配置须为 CSV 单列行")
    rows = list(csv.reader(io.StringIO(value, newline=""), strict=True))
    if len(rows) != 1 or len(rows[0]) != 1:
        raise ValueError("扩展配置须为 CSV 单列行")
    return rows[0][0]


def is_extension_leaf(logical, trail, text):
    """These declarations apply whenever their containing table is delivered."""
    if logical == "master/string/custom_ability_string.orderedmap":
        return bool(trail and str(trail[-1]).startswith(tuple(PREFIXES)))
    if logical not in {"master/character/unique_condition.orderedmap", "master/battle/multiball/multiball.orderedmap"}:
        return False
    for row in csv.reader(io.StringIO(text, newline=""), strict=True):
        if logical.endswith("/unique_condition.orderedmap"):
            if row and row[0].startswith(("wfx:41:", "wfx:42:")):
                return True
        elif len(row) > 9 and row[9] not in {"", "0", "(None)"}:
            return True
    return False
