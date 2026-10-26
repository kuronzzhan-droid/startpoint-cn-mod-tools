"""Validate p12/p13 delivery tables against the exact delivery baseline."""
from __future__ import annotations

import csv
import io
import re
from collections.abc import Mapping

from wf.caps.p13 import PREFIXES, config_problems, decode_config_row
from wf.caps.requirements import parse_table
from wf.rules.catalog import result

STRINGS = "master/string/custom_ability_string.orderedmap"
MULTIBALL = "master/battle/multiball/multiball.orderedmap"
PF = "master/skill/power_flip_action.orderedmap"
UNIQUE = "master/character/unique_condition.orderedmap"


def _read(view, logical):
    if view is None:
        raise FileNotFoundError(logical)
    data = view[logical] if isinstance(view, Mapping) else view.read_raw(logical)
    return data[0] if isinstance(data, tuple) else data


def check_client_extensions(outputs, baseline_view=None, *, bundled_keys=None, bundle_error=None):
    """Return JSON checks for logical-path bytes; None APK keys means unchecked.

    ``bundled_keys`` maps normal CDN logical paths to the union of keys from all
    target APKs. Output tables replace baseline tables, as they do in delivery.
    Missing baseline tables are empty; corrupt tables always block validation.
    """
    checks, entries, required, tables = [], [], set(), {}

    def issue(code, message, key=None, *, blocking=True, logical=STRINGS, **detail):
        checks.append(result(code, "问题" if blocking else "待验证", message,
                             blocking=blocking, logical=logical, key=key, **detail))

    def table(logical):
        if logical not in tables:
            try:
                raw = outputs[logical] if logical in outputs else _read(baseline_view, logical)
            except (KeyError, FileNotFoundError):
                tables[logical] = {}
            else:
                tables[logical] = parse_table(raw, logical)
        return tables[logical]

    try:
        if STRINGS in outputs:
            for key, raw_value in table(STRINGS).items():
                prefix = next((p for p in PREFIXES if key.startswith(p)), None)
                if prefix is None:
                    continue
                capability = PREFIXES[prefix]
                required.add(capability)
                entry = {"logical": STRINGS, "key": key, "capability": capability}
                entries.append(entry)
                try:
                    value = decode_config_row(raw_value)
                except (ValueError, csv.Error) as error:
                    issue("CLIENT_EXTENSION_FORMAT", str(error), key)
                    continue
                entry["value"] = value
                problems = config_problems(key, value)
                for message in problems:
                    issue("CLIENT_EXTENSION_FORMAT", message, key)
                if problems:
                    continue
                ball = key[len(prefix):]
                if ball not in table(MULTIBALL):
                    issue("CLIENT_EXTENSION_MULTIBALL_MISSING", f"multiball 行不存在：{ball}", key)
                if prefix == "wfx_ball_pf_action_":
                    if value not in table(PF):
                        issue("CLIENT_EXTENSION_ACTION_MISSING", f"PF 动作键不存在：{value}", key)
                    if bundle_error is not None:
                        issue("CLIENT_EXTENSION_BUNDLE_ERROR", "目标 APK 内置表读取失败：" + bundle_error,
                              key, action=value)
                    elif bundled_keys is None:
                        issue("CLIENT_EXTENSION_BUNDLE_UNCHECKED", "未核对内置键：未提供目标 APK", key,
                              blocking=False, action=value)
                    elif value in set(bundled_keys.get(PF, ())):
                        issue("CLIENT_EXTENSION_ACTION_COLLISION", f"PF 动作键与 APK 内置表撞名：{value}", key,
                              action=value)
        if MULTIBALL in outputs:
            for key, value in table(MULTIBALL).items():
                if isinstance(value, str):
                    rows = list(csv.reader(io.StringIO(value, newline=""), strict=True))
                    if any(len(row) > 9 and row[9] not in {"", "0", "(None)"} for row in rows):
                        required.add("client.summon.cutin_preload@1")
        if UNIQUE in outputs:
            import wf_wfx
            for key, value in table(UNIQUE).items():
                if not isinstance(value, str):
                    continue
                for row in csv.reader(io.StringIO(value, newline=""), strict=True):
                    if not row or not re.match(r"^wfx:(41|42)(?::|$)", row[0], re.IGNORECASE):
                        continue
                    capability = "client.combo.base@1" if row[0].lower().split(":")[1] == "41" else "client.pf.dual@1"
                    required.add(capability)
                    entries.append({"logical": UNIQUE, "key": key, "capability": capability, "value": row[0]})
                    try:
                        from wf.caps.signals_v35 import wfx_problem
                        problem = wfx_problem(row[0])
                        if problem:
                            raise ValueError(problem)
                        spec = wf_wfx.decode_sid(row[0])
                    except ValueError as error:
                        issue("CLIENT_EXTENSION_FORMAT", str(error), key, logical=UNIQUE)
                    else:
                        if spec.code == 42 and str(spec.value) not in table(MULTIBALL):
                            issue("CLIENT_EXTENSION_MULTIBALL_MISSING", f"multiball 行不存在：{spec.value}", key,
                                  logical=UNIQUE)
    except (ValueError, csv.Error, OSError) as error:
        issue("CLIENT_EXTENSION_TABLE_INVALID", str(error), logical=None)
    status = "error" if any(c["blocking"] for c in checks) else "warning" if checks else "ok"
    return {"status": status, "requires": sorted(required), "checks": checks, "keys": entries}
