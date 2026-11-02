"""深渊武装纯数据构建器测试（合成行，不读取真实 CN store）。"""

from __future__ import annotations

import contextlib

import dataclasses

import copy

import io

import json

import shutil

import subprocess

import sys

import tempfile

import unittest

from pathlib import Path

from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_assets  # noqa: E402

import wf_describe  # noqa: E402

import wf_mod_tool as core  # noqa: E402

import wf_publish  # noqa: E402

import wf_rogue_build as rogue_build  # noqa: E402

import wf_rogue_rewards as rewards  # noqa: E402

import wf_rogue_validate as validator  # noqa: E402

REQUIRED_API = (
    "WEAPONS",
    "IMAGE_PREFIX",
    "MODE_DESCRIPTION",
    "build_equipment_leaf",
    "build_equipment_status",
    "build_soul_leaf",
)

MISSING_API = tuple(name for name in REQUIRED_API if not hasattr(rewards, name))

TASK2_API = (
    "EQUIP_STATUS_T",
    "RUSH_EVENT_T",
    "EVENT_ID",
    "MasterTables",
    "MasterChanges",
    "ServerMirrors",
    "assert_reserved_ownership",
    "build_master_changes",
    "apply_server_mirrors",
    "patch_rush_token",
)

MISSING_TASK2_API = tuple(name for name in TASK2_API if not hasattr(rewards, name))

def fake_release_snapshot(store: Path) -> validator.ReleaseSnapshot:
    return validator.ReleaseSnapshot(
        store=str(store.resolve()),
        entries=tuple(
            validator.ReleaseEntry(
                logical=logical,
                relative=rewards.q.hashed_rel(logical),
                sha256="0" * 64,
                size=0,
            )
            for logical in validator.release_logicals()
        ),
    )

TASK3_API = (
    "validate_source_assets",
    "install_source_assets",
)

MISSING_TASK3_API = tuple(name for name in TASK3_API if not hasattr(rewards, name))

EXPECTED_WEAPON_METADATA = [
    ("8000101", "深渊·灰烬巨剑", "5010060", 0, "Red", "item/equipment/mod/abyss/fire_01", (3, 2)),
    ("8000102", "深渊·熔核法杖", "5020042", 0, "Red", "item/equipment/mod/abyss/fire_02", (3, 2)),
    ("8000103", "深渊·深潮长枪", "5010075", 1, "Blue", "item/equipment/mod/abyss/water_01", (3, 2)),
    ("8000104", "深渊·冻海战锚", "5020031", 1, "Blue", "item/equipment/mod/abyss/water_02", (3, 2)),
    ("8000105", "深渊·雷鸣双刃", "5010077", 2, "Yellow", "item/equipment/mod/abyss/thunder_01", (3, 2)),
    ("8000106", "深渊·轰电战锤", "5020038", 2, "Yellow", "item/equipment/mod/abyss/thunder_02", (3, 2)),
    ("8000107", "深渊·裂空战镰", "5010068", 3, "Green", "item/equipment/mod/abyss/wind_01", (3, 2)),
    ("8000108", "深渊·苍岚长弓", "5020026", 3, "Green", "item/equipment/mod/abyss/wind_02", (3, 2)),
    ("8000109", "深渊·晨星圣剑", "5017716", 4, "White", "item/equipment/mod/abyss/light_01", (3, 2)),
    ("8000110", "深渊·辉环法器", "5020039", 4, "White", "item/equipment/mod/abyss/light_02", (3, 2)),
    ("8000111", "深渊·蚀月大剑", "5010078", 5, "Black", "item/equipment/mod/abyss/dark_01", (3, 2)),
    ("8000112", "深渊·冥灯魔杖", "5020040", 5, "Black", "item/equipment/mod/abyss/dark_02", (3, 2)),
    ("8000113", "深渊·征服者", "5010057", -1, "(None)", "item/equipment/mod/abyss/universal_01", (3, 2)),
    ("8000114", "深渊·轮转核", "5020010", -1, "(None)", "item/equipment/mod/abyss/universal_02", (3, 2)),
    ("8000115", "深渊·万象铳", "5090045", -1, "(None)", "item/equipment/mod/abyss/universal_03", (3, 2)),
]

EXPECTED_EFFECT_ROWS = {'8000101': (('3020011', 0, '51', 150000, '225000'),
             ('300001', 4, '202', 50000, '75000'),
             ('300001', 0, '32', 200000, '300000'),
             ('5020041', 0, '33', 200000, '300000')),
 '8000102': (('3050010', 0, '211', 100000, '100000'),
             ('5050037', 0, '40', 15000, '22500'),
             ('4030004', 0, '190', 20000, '30000'),
             ('5100004', 1, '157', 30000, '45000'),
             ('300001', 0, '32', 200000, '300000')),
 '8000103': (('5090059', 0, '50', 150000, '225000'),
             ('5040033', 4, '56', 20000, '30000'),
             ('5020041', 0, '33', 200000, '300000'),
             ('300001', 0, '32', 200000, '300000'),
             ('5050009', 0, '55', 200000, '300000')),
 '8000104': (('5050020', 1, '227', 20000, '30000'),
             ('4030019', 2, '70', '', ''),
             ('300001', 8, '226', 600000, '900000'),
             ('5080029', 0, '205', 25000, '37500'),
             ('5020024', 0, '34', 400000, '600000'),
             ('3080008', 0, '36', 20000, '30000')),
 '8000105': (('5090054', 0, '213', 12000000, '18000000'),
             ('5030021', 1, '26', '', ''),
             ('5090027', 0, '33', 300000, '450000'),
             ('300001', 0, '32', 300000, '450000')),
 '8000106': (('4030004', 0, '190', 25000, '37500'),
             ('5070040', 0, '38', 15000, '22500'),
             ('3010035', 0, '35', 15000, '16000'),
             ('300001', 0, '32', 250000, '375000')),
 '8000107': (('300001', 8, '226', 600000, '900000'),
             ('5040009', 1, '211', 5000, '7500'),
             ('5070017', 1, '200', 200000, '300000'),
             ('5050009', 0, '55', 200000, '300000'),
             ('300001', 0, '32', 200000, '300000')),
 '8000108': (('4040021', 1, '226', 1000000, '1500000'),
             ('4040007', 0, '191', 20000, '30000'),
             ('5090027', 0, '33', 200000, '300000'),
             ('300001', 0, '32', 200000, '300000')),
 '8000109': (('3010027', 1, '209', 45000, '67500'),
             ('5090029', 0, '388', 250000, '375000'),
             ('300001', 0, '32', 250000, '375000'),
             ('5090054', 0, '213', 4000000, '6000000'),
             ('4060023', 2, '220', '', '')),
 '8000110': (('5050017', 2, '203', 1500000, '2250000'),
             ('4080015', 1, '206', 25000, '37500'),
             ('5040019', 2, '245', 50000, '75000'),
             ('300001', 0, '32', 200000, '300000')),
 '8000111': (('4080016', 2, '67', '', ''),
             ('5080038', 1, '41', 15000, '22500'),
             ('5090024', 2, '28', 300000, '450000'),
             ('5090027', 0, '33', 300000, '450000')),
 '8000112': (('3020003', 0, '59', '', ''),
             ('3020003', 1, '60', '', ''),
             ('5010047', 0, '1', 200000, '300000'),
             ('5050022', 1, '209', 10000, '15000'),
             ('300001', 0, '32', 200000, '300000')),
 '8000113': (('300001', 5, '468', 100000, '100000'),
             ('300002', 6, '16', '', ''),
             ('5045000', 1, '61', '', ''),
             ('5020024', 0, '34', 350000, '525000')),
 '8000114': (('3050010', 0, '211', 15000, '22500'),
             ('3060003', 0, '156', 30000, '45000'),
             ('5040033', 4, '56', 20000, '30000'),
             ('5080029', 0, '205', 50000, '75000'),
             ('3010035', 0, '35', 15000, '16000'),
             ('3080008', 0, '36', 30000, '33000')),
 '8000115': (('3080002', 0, '68', '', ''),
             ('3080002', 1, '69', '', ''),
             ('5080029', 0, '205', 30000, '45000'),
             ('300001', 0, '32', 200000, '300000'),
             ('5090059', 0, '50', 200000, '300000'),
             ('5090029', 0, '388', 200000, '300000'))}

EXPECTED_LEVEL1_STRENGTHS = {'8000101': ('112500', '37500', '150000', '150000'),
 '8000102': ('50000', '11250', '15000', '22500', '150000'),
 '8000103': ('112500', '15000', '150000', '150000', '150000'),
 '8000104': ('15000', '', '450000', '18750', '300000', '15000'),
 '8000105': ('9000000', '', '225000', '225000'),
 '8000106': ('18750', '11250', '8000', '187500'),
 '8000107': ('450000', '3750', '150000', '150000', '150000'),
 '8000108': ('750000', '15000', '150000', '150000'),
 '8000109': ('33750', '187500', '187500', '3000000', ''),
 '8000110': ('1125000', '18750', '37500', '150000'),
 '8000111': ('', '11250', '225000', '225000'),
 '8000112': ('', '', '150000', '7500', '150000'),
 '8000113': ('100000', '', '', '262500'),
 '8000114': ('11250', '22500', '15000', '37500', '8000', '16500'),
 '8000115': ('', '', '22500', '150000', '150000', '150000')}

EXPECTED_DURATION_OVERRIDES = {
    ("8000105", 2): ("120000000", "120000000"),
    ("8000111", 3): ("72000000", "72000000"),
    ("8000112", 3): ("60000000", "60000000"),
}

EXPECTED_BY_EACH_TRIGGER_PULLER = {
    ("8000105", 2): "false",
    ("8000111", 3): "false",
    ("8000112", 3): "false",
}

EXPECTED_5050022_OUTPUT_COLUMNS = {
    3: "8",
    4: "0",
    6: "20000",
    7: "20000",
    24: "23",
    25: "0",
    27: "100000",
    28: "100000",
    31: "(None)",
    32: "0",
    44: "209",
    45: "0",
    46: "",
}

EXPECTED_CONQUEROR_SURVIVAL_COLUMNS = (
    {
        44: "468", 45: "5", 46: "(None)",
        48: "100000", 49: "100000",
        56: "300000", 57: "300000",
        64: "1", 69: "false", 71: "1",
    },
    {
        24: "25", 25: "5", 26: "(None)",
        27: "1000", 28: "1000", 31: "3", 32: "0",
        44: "16", 45: "7", 46: "",
        56: "100000", 57: "100000",
        64: "1", 69: "false",
    },
)

DONOR_KIND_OVERRIDES = {("5050022", 1): "32"}

DURING_DONORS = frozenset({("5030030", 0), ("5040033", 0)})

DONOR_RUNTIME_COLUMNS = {
    ("5030021", 1): {69: "false"},
    ("5090024", 2): {69: "false"},
    ("5010047", 0): {69: "false"},
    ("300001", 5): {
        56: "100000", 57: "100000",
        64: "1", 69: "false", 71: "1",
    },
    ("300002", 6): {
        56: "100000", 57: "100000",
        64: "1", 69: "false",
    },
}

def donor_duration_sentinel(template_id: str, donor_line: int, column: int) -> str:
    """Return a distinct numeric donor value for independent c54/c55 preservation checks."""
    return f"{column}{int(template_id):07d}{donor_line:02d}"

_CONTENT_FIELD_DEFAULTS = {
    "target": "1",
    "strength": "100",
    "strength2": "0",
    "frame": "90000000",
    "number": "100000",
    "max_accumulation": "(None)",
    "flip_limit": "(None)",
    "power_flip_limit": "(None)",
    "end_power_flip_limit": "(None)",
    "end_power_flip_accepted_levels": "(None)",
    "cancelable": "0",
    "unique_condition_id": "0",
    "time": "0",
    "element": "0",
    "initial_multiply": "1",
    "multiply_trigger": "0",
    "by_each_trigger_puller": "false",
}

def _fill_instant_content_defaults(row: list[str]) -> None:
    base = int(wf_describe.layout("ability_soul")["blocks"]["instant_content"])
    fields = wf_describe.enum_map()["block_fields"]["instant_content"]
    for name, value in _CONTENT_FIELD_DEFAULTS.items():
        offsets = [
            int(offset)
            for offset, field, _label in fields
            if field == name or field.startswith(name + ".")
        ]
        if not offsets:
            continue
        col = base + min(offsets)
        if not row[col]:
            row[col] = value

def template_row(
    effect_kind: str, *, template_id: str = "9999999", donor_line: int = 0,
) -> list[str]:
    row = [""] * 123
    row[0], row[1], row[2] = "9", "9", "0"
    # Minimal client-legal instant row. c122 is outside every rewritten block and
    # therefore acts as the independent donor-line marker.
    row[3], row[10], row[17] = "0", "0", "0"
    row[24], row[36], row[43] = "0", "(None)", "0"
    row[44], row[45], row[46] = effect_kind, "1", ""
    row[48], row[49] = "100", "200"
    _fill_instant_content_defaults(row)
    content_case = wf_describe.enum_map()["cases"]["instant_content"].get(effect_kind)
    if content_case is not None and "multiply_trigger" in content_case["fields"]:
        # 官方 ability_soul 里凡是声明 multiply_trigger 的瞬发行都带 c71/c72
        # (live 8000111 槽3 kind 28 就是 '1'/'0');留空 = parseAt72 C7050。
        row[71], row[72] = "1", "0"
    row[54] = donor_duration_sentinel(template_id, donor_line, 54)
    row[55] = donor_duration_sentinel(template_id, donor_line, 55)
    row[122] = f"{template_id}#{donor_line}"
    for column, value in DONOR_RUNTIME_COLUMNS.get(
        (template_id, donor_line), {},
    ).items():
        row[column] = value
    if (template_id, donor_line) == ("5050022", 1):
        # Preserve the audited donor's HpHigh + skill-trigger shape. The output
        # intentionally rewrites donor kind 32 to emitted kind 209.
        row[3], row[4], row[6], row[7] = "8", "0", "50000", "50000"
        row[24], row[25] = "23", "0"
        row[27], row[28], row[31], row[32] = "100000", "100000", "1", "0"
    return row

def during_template_row(
    effect_kind: str, *, template_id: str, donor_line: int,
) -> list[str]:
    """Minimal client-legal during row shaped like official 5030030#0 / 5040033#0."""
    row = [""] * 123
    row[0], row[1], row[2] = "9", "9", "1"
    row[3], row[6], row[7], row[8] = "2", "600000", "600000", "White"
    row[10], row[17] = "0", "0"
    row[82], row[94], row[105] = "(None)", "4", "false"
    row[106], row[107], row[108] = effect_kind, "5", "White"
    row[110], row[111] = "100", "200"
    row[122] = f"{template_id}#{donor_line}"
    return row

def strength_cells(row: list[str]) -> tuple[str, str]:
    """Instant rows keep strength in c48/c49, during rows in c110/c111."""
    return (row[110], row[111]) if row[2] == "1" else (row[48], row[49])

def build_template_fixtures(
    effect_rows: list[tuple[str, int, str]] | tuple[tuple[str, int, str], ...],
) -> dict[str, str]:
    rows_by_template: dict[str, list[list[str]]] = {}
    for template_id, donor_line, emitted_kind in effect_rows:
        rows = rows_by_template.setdefault(template_id, [])
        while len(rows) <= donor_line:
            line = len(rows)
            rows.append(template_row(
                "999", template_id=template_id, donor_line=line,
            ))
        donor_kind = DONOR_KIND_OVERRIDES.get(
            (template_id, donor_line), emitted_kind,
        )
        make_row = (
            during_template_row if (template_id, donor_line) in DURING_DONORS
            else template_row
        )
        rows[donor_line] = make_row(
            donor_kind, template_id=template_id, donor_line=donor_line,
        )
    return {
        template_id: core.write_csv_lines(rows)
        for template_id, rows in rows_by_template.items()
    }

def fake_templates() -> dict[str, str]:
    return build_template_fixtures(tuple(
        (template_id, donor_line, effect_kind)
        for expected_rows in EXPECTED_EFFECT_ROWS.values()
        for template_id, donor_line, effect_kind, _old, _new in expected_rows
    ))

def templates_for_spec(spec) -> dict[str, str]:
    """Build exact donor-line fixtures for one canonical weapon spec."""
    return build_template_fixtures(tuple(
        (effect.template_id, effect.donor_line, effect.effect_kind)
        for effect in spec.effects
    ))

def require_task2(name: str):
    value = getattr(rewards, name, None)
    if value is None:
        raise AssertionError(f"Task 2 API {name} is not implemented")
    return value

def require_task3(name: str):
    value = getattr(rewards, name, None)
    if value is None:
        raise AssertionError(f"Task 3 API {name} is not implemented")
    return value

def write_rgba_fixture(
    path: Path,
    *,
    color: tuple[int, int, int, int] = (200, 80, 40, 255),
    size: tuple[int, int] = (20, 20),
    visible_box: tuple[int, int, int, int] | None = (1, 1, 19, 19),
    background: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> None:
    image = Image.new("RGBA", size, background)
    if visible_box is not None:
        image.paste(color, visible_box)
    image.save(path, format="PNG")

def write_valid_asset_set(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for index, spec in enumerate(rewards.WEAPONS):
        color = (
            20 + (index * 37) % 220,
            20 + (index * 67) % 220,
            20 + (index * 97) % 220,
            255,
        )
        write_rgba_fixture(directory / f"{spec.image_slug}.png", color=color)

def fake_master_tables(*, placeholders: bool = False, binary: bool = False):
    tables_type = require_task2("MasterTables")

    def leaf(rows: list[list[str]]) -> bytes | str:
        text = core.write_csv_lines(rows)
        return text.encode("utf-8") if binary else text

    item_template = [f"item-{index}" for index in range(23)]
    item_template[1] = rewards.TOKEN_TEMPLATE
    item_template[2] = "激战代币"
    items = {rewards.TOKEN_TEMPLATE: leaf([item_template])}

    equipment: dict[str, object] = {}
    equipment_status: dict[str, object] = {}
    for spec in rewards.WEAPONS:
        donor_item = [f"donor-item-{spec.id}-{index}" for index in range(23)]
        donor_item[0] = f"donor_{spec.donor}"
        donor_item[1] = spec.donor
        donor_item[2] = f"donor soul {spec.donor}"
        donor_item[3] = f"item/generated/ability_soul/general/{spec.donor}"
        donor_item[5] = "AbilitySoul"
        donor_item[12] = str(spec.element) if spec.element >= 0 else "0,3,2,1,4,5"
        items[spec.donor] = leaf([donor_item])

        donor = [f"donor-{spec.id}-{index}" for index in range(16)]
        donor[0] = f"donor_{spec.donor}"
        donor[1] = f"供体 {spec.donor}"
        donor[6] = f"item/equipment/donor/{spec.donor}"
        donor[7] = f"供体描述 {spec.donor}"
        donor[8] = "4"
        donor[9] = "true"
        donor[10] = spec.donor
        donor[11] = "4"
        equipment[spec.donor] = leaf([donor])
        equipment_status[spec.donor] = {
            "1": "100,50",
            "5": "500,250",
        }
        if placeholders:
            placeholder = list(donor)
            placeholder[0] = f"mod_abyss_{spec.id}"
            placeholder[1] = f"占位 {spec.id}"
            placeholder[10] = spec.id
            equipment[spec.id] = leaf([placeholder])
            equipment_status[spec.id] = {"placeholder": spec.id}

    souls = {
        key: value.encode("utf-8") if binary else value
        for key, value in fake_templates().items()
    }
    if placeholders:
        for spec in rewards.WEAPONS:
            souls[spec.id] = leaf([[f"placeholder-{spec.id}"]])

    rush_row = [f"rush-{index}" for index in range(18)]
    rush_row[10] = rewards.TOKEN_TEMPLATE
    rush_template = [f"rush-template-{index}" for index in range(18)]
    rush_event = {
        "700099": leaf([rush_row]),
        rogue_build.TEMPLATE_EVENT: leaf([rush_template]),
        "700001": leaf([["untouched"]]),
    }
    return tables_type(
        items=items,
        equipment=equipment,
        equipment_status=equipment_status,
        ability_soul=souls,
        rush_event=rush_event,
    )

def fake_server_mirrors():
    mirrors_type = require_task2("ServerMirrors")
    max_level = {"42": 3}
    element = {"42": 9}
    lookup = {"42": {"name": "保留装备", "rarity": "3", "category": "测试"}}
    for index, spec in enumerate(rewards.WEAPONS):
        max_level[spec.donor] = index + 1
        element[spec.donor] = 99
        lookup[spec.donor] = {
            "name": f"供体 {spec.donor}",
            "rarity": "4",
            "category": f"供体类别 {index}",
        }
    return mirrors_type(
        equipment_max_level=max_level,
        equipment_element=element,
        equipment_lookup=lookup,
        equipment_ids=[42, 7, 42],
        item_ids=[5, 1, 5],
    )

MIRROR_FIELDS = (
    "equipment_max_level",
    "equipment_element",
    "equipment_lookup",
    "equipment_ids",
    "item_ids",
)

def write_temp_mirrors(directory: Path, mirrors) -> dict[str, bytes]:
    result = {}
    for field in MIRROR_FIELDS:
        path = directory / f"{field}.json"
        data = getattr(mirrors, field)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=0 if isinstance(data, list) else 1),
            encoding="utf-8",
        )
        result[field] = path.read_bytes()
    return result

__all__ = [name for name in globals() if not name.startswith("__")]
