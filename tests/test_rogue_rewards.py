# -*- coding: utf-8 -*-
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


# v3.3 canonical metadata and all 75 uplift slots are deliberately static.  Do not
# derive these oracles from WEAPONS/resolve_effect_strength: the test must catch a
# production declaration and its resolver drifting together.
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

# (template_id, donor_line, emitted_kind, v3.3 strength, expected strength after uplift)
# 强度列:瞬发行 c48/c49,持续行(EffectSpec.during)c110/c111;×1 规则的行写的就是满级合计。
EXPECTED_EFFECT_ROWS = {
    "8000101": (
        ("3020011", 0, "51", 150000, "225000"),
        ("300001", 4, "202", 50000, "75000"),
        ("300001", 0, "32", 200000, "300000"),
        ("5020041", 0, "33", 200000, "300000"),
        # 作者 2026-09-28:同值镜像给协力球(target 8)
        ("300001", 0, "32", 200000, "300000"),
        ("5020041", 0, "33", 200000, "300000"),
    ),
    "8000102": (
        ("3050010", 0, "211", 100000, "100000"),
        ("5050037", 0, "40", 15000, "22500"),
        ("4030004", 0, "190", 20000, "30000"),
        ("5100004", 1, "157", 30000, "45000"),
        ("300001", 0, "32", 200000, "300000"),
        ("300001", 0, "32", 200000, "300000"),
    ),
    "8000103": (
        ("5090059", 0, "50", 150000, "225000"),
        ("5040033", 4, "56", 20000, "30000"),
        ("5020041", 0, "33", 200000, "300000"),
        ("300001", 0, "32", 200000, "300000"),
        ("5050009", 0, "55", 200000, "300000"),
    ),
    "8000104": (
        ("5050020", 1, "227", 20000, "30000"),
        ("4030019", 2, "70", "", ""),
        ("300001", 8, "226", 600000, "900000"),
        ("5080029", 0, "205", 25000, "37500"),
        ("5020024", 0, "34", 400000, "600000"),
        ("3080008", 0, "36", 20000, "30000"),
    ),
    "8000105": (
        ("5090054", 0, "213", 12000000, "18000000"),
        ("5030021", 1, "26", "", ""),
        ("5090027", 0, "33", 300000, "450000"),
        ("300001", 0, "32", 300000, "450000"),
    ),
    # 作者 2026-09-28 重做:数值 = 游戏内满级合计(本体 + 强化 120),觉醒拆分再对半拆。
    "8000106": (
        ("5050009", 0, "55", 200000, "300000"),
        ("300001", 0, "32", 200000, "300000"),
        ("5070040", 1, "253", 500000, "500000"),     # ×1 规则:5 倍
        ("4010014", 0, "629", "", ""),
    ),
    "8000107": (
        ("300001", 8, "226", 600000, "900000"),
        ("5040009", 1, "211", 5000, "7500"),
        ("5070017", 1, "200", 200000, "300000"),
        ("5050009", 0, "55", 200000, "300000"),
        ("300001", 0, "32", 200000, "300000"),
    ),
    "8000108": (
        ("4040021", 1, "226", 1000000, "1500000"),
        ("4040007", 0, "191", 20000, "30000"),
        ("5090027", 0, "33", 200000, "300000"),
        ("300001", 0, "32", 200000, "300000"),
    ),
    "8000109": (
        ("3010027", 1, "209", 45000, "67500"),
        ("5090029", 0, "388", 250000, "375000"),
        ("300001", 0, "32", 250000, "375000"),
        ("5090054", 0, "213", 4000000, "6000000"),
        ("4060023", 2, "220", "", ""),
    ),
    "8000110": (
        ("5050017", 2, "203", 1500000, "2250000"),
        ("4080015", 1, "206", 25000, "37500"),
        ("5040019", 2, "245", 50000, "50000"),       # ×1 规则:合计 +50%
        ("5030030", 0, "0", 250000, "250000"),       # 持续·Fever 队伍攻击力(c110/c111)
        ("5040033", 0, "1", 250000, "250000"),       # 持续·Fever 队伍直接攻击伤害
    ),
    "8000111": (
        ("4080016", 2, "67", "", ""),
        ("5080038", 1, "41", 15000, "22500"),
        ("5090024", 2, "28", 300000, "450000"),
        ("5090027", 0, "33", 300000, "450000"),
    ),
    "8000112": (
        ("3020003", 0, "59", "", ""),
        ("3020003", 1, "60", "", ""),
        ("5010047", 0, "1", 200000, "300000"),
        ("5050022", 1, "209", 10000, "15000"),
        ("300001", 0, "32", 200000, "300000"),
    ),
    "8000113": (
        ("300001", 5, "468", 100000, "100000"),
        ("300002", 6, "16", "", ""),
        ("5045000", 1, "61", "", ""),
        ("5020024", 0, "34", 350000, "525000"),
    ),
    "8000114": (
        ("3050010", 0, "211", 15000, "22500"),
        ("3060003", 0, "156", 30000, "45000"),
        ("5040033", 4, "56", 20000, "30000"),
        ("5080029", 0, "205", 50000, "75000"),
        ("3010035", 0, "35", 15000, "16000"),
        ("3080008", 0, "36", 30000, "33000"),
    ),
    "8000115": (
        ("3080002", 0, "68", "", ""),
        ("3080002", 1, "69", "", ""),
        ("5080029", 0, "205", 30000, "45000"),
        ("300001", 0, "32", 200000, "300000"),
        ("5090059", 0, "50", 200000, "300000"),
        ("5090029", 0, "388", 200000, "300000"),
    ),
}

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

# 8000112 slot 4 must keep the donor's HpHigh + skill-trigger shape while changing
# the donor kind 32 into the audited self-damage kind 209.
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
# 持续(during, c2=1)捐赠行:官方 5030030#0 / 5040033#0 的形状(pre1 = 光属性 ≥6 门、Fever 持续触发)。
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


# 捐赠行的 instant_content 块默认值(空列才填)。build_soul_leaf 会把 c44 换成
# 发射 kind,而新 kind 往往比捐赠 kind 多声明几列;官方 ability_soul 451 键 1001 行
# 里这些列**一行都没留空**,留空即 Std.parseInt('')=NaN(部分列直接 C7050)。
# 真实 store 捐赠行本来就是填满的 —— 15 个武器规格跑 build_soul_leaf 全过 ——
# 所以这里补的是 fixture 与官方形状的差距,不是放宽门禁。
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


class TestApiSurface(unittest.TestCase):
    def test_canonical_builder_api_exists(self):
        self.assertEqual((), MISSING_API)

    def test_task2_writer_api_exists(self):
        self.assertEqual((), MISSING_TASK2_API)

    def test_task3_asset_api_exists(self):
        self.assertEqual((), MISSING_TASK3_API)


class TestSourceAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._fixture_temp = tempfile.TemporaryDirectory()
        cls._fixture_dir = Path(cls._fixture_temp.name) / "valid-assets"
        write_valid_asset_set(cls._fixture_dir)

    @classmethod
    def tearDownClass(cls):
        cls._fixture_temp.cleanup()

    def setUp(self):
        self._test_temp = tempfile.TemporaryDirectory()
        self.asset_dir = Path(self._test_temp.name) / "assets"
        shutil.copytree(self._fixture_dir, self.asset_dir)

    def tearDown(self):
        self._test_temp.cleanup()

    def validate(self) -> dict[str, Path]:
        return require_task3("validate_source_assets")(
            self.asset_dir, rewards.WEAPONS
        )

    def test_valid_rgba_sources_are_returned_by_fixed_slug(self):
        sources = self.validate()

        self.assertEqual(
            [spec.image_slug for spec in rewards.WEAPONS], list(sources)
        )
        self.assertEqual(
            {
                spec.image_slug: self.asset_dir / f"{spec.image_slug}.png"
                for spec in rewards.WEAPONS
            },
            sources,
        )

    def test_client_native_20px_sources_are_accepted(self):
        for index, spec in enumerate(rewards.WEAPONS):
            color = (
                20 + (index * 37) % 220,
                20 + (index * 67) % 220,
                20 + (index * 97) % 220,
                255,
            )
            write_rgba_fixture(
                self.asset_dir / f"{spec.image_slug}.png",
                color=color,
                size=(20, 20),
                visible_box=(1, 1, 19, 19),
            )

        sources = self.validate()

        self.assertEqual(15, len(sources))

    def test_wrong_dimensions_are_rejected(self):
        spec = rewards.WEAPONS[0]
        write_rgba_fixture(
            self.asset_dir / f"{spec.image_slug}.png", size=(21, 20)
        )

        with self.assertRaises(ValueError):
            self.validate()

    def test_rgb_without_alpha_is_rejected(self):
        spec = rewards.WEAPONS[0]
        Image.new("RGB", (20, 20), (20, 40, 60)).save(
            self.asset_dir / f"{spec.image_slug}.png", format="PNG"
        )

        with self.assertRaises(ValueError):
            self.validate()

    def test_fully_opaque_image_is_rejected(self):
        spec = rewards.WEAPONS[0]
        write_rgba_fixture(
            self.asset_dir / f"{spec.image_slug}.png",
            visible_box=None,
            background=(20, 40, 60, 255),
        )

        with self.assertRaises(ValueError):
            self.validate()

    def test_fully_transparent_image_is_rejected(self):
        spec = rewards.WEAPONS[0]
        write_rgba_fixture(
            self.asset_dir / f"{spec.image_slug}.png", visible_box=None
        )

        with self.assertRaises(ValueError):
            self.validate()

    def test_edge_touching_visible_bounds_match_official_atlas_contract(self):
        spec = rewards.WEAPONS[0]
        write_rgba_fixture(
            self.asset_dir / f"{spec.image_slug}.png",
            visible_box=(0, 0, 20, 19),
        )

        sources = self.validate()

        self.assertIn(spec.image_slug, sources)

    def test_duplicate_sha256_content_is_rejected(self):
        first, second = rewards.WEAPONS[:2]
        shutil.copyfile(
            self.asset_dir / f"{first.image_slug}.png",
            self.asset_dir / f"{second.image_slug}.png",
        )

        with self.assertRaises(ValueError):
            self.validate()

    def test_missing_source_name_is_rejected(self):
        spec = rewards.WEAPONS[0]
        (self.asset_dir / f"{spec.image_slug}.png").unlink()

        with self.assertRaises(ValueError):
            self.validate()

    def test_unexpected_source_name_is_rejected(self):
        write_rgba_fixture(self.asset_dir / "unexpected.png")

        with self.assertRaises(ValueError):
            self.validate()

    def test_unexpected_non_png_file_is_rejected(self):
        (self.asset_dir / "unexpected.jpg").write_bytes(b"not an allowed asset")

        with self.assertRaisesRegex(ValueError, "unexpected"):
            self.validate()

    def test_unexpected_subdirectory_is_rejected(self):
        (self.asset_dir / "nested").mkdir()

        with self.assertRaisesRegex(ValueError, "unexpected"):
            self.validate()

    def test_non_png_bytes_are_rejected(self):
        spec = rewards.WEAPONS[0]
        (self.asset_dir / f"{spec.image_slug}.png").write_bytes(b"not a png")

        with self.assertRaises(ValueError):
            self.validate()

    def test_install_uses_only_png_magic_encoding_and_exact_hashed_paths(self):
        sources = self.validate()
        original = {slug: path.read_bytes() for slug, path in sources.items()}
        store = Path(self._test_temp.name) / "upload"

        installed = require_task3("install_source_assets")(
            store, sources, rewards.WEAPONS
        )

        expected = [
            rewards.q.hashed_rel(
                f"{rewards.IMAGE_PREFIX}/{spec.image_slug}.png"
            )
            for spec in rewards.WEAPONS
        ]
        self.assertEqual(expected, installed)
        self.assertEqual(
            len(rewards.WEAPONS),
            sum(1 for path in store.rglob("*") if path.is_file()),
        )
        for spec, relative in zip(rewards.WEAPONS, installed):
            with self.subTest(asset=spec.image_slug):
                source_bytes = original[spec.image_slug]
                stored_bytes = (store / relative).read_bytes()
                self.assertEqual(source_bytes, sources[spec.image_slug].read_bytes())
                self.assertEqual(wf_assets.png_encode(source_bytes), stored_bytes)
                self.assertEqual(source_bytes, wf_assets.png_decode(stored_bytes))

    def test_validate_assets_flag_reports_fixed_paths_without_touching_profile(self):
        output = io.StringIO()
        with (
            mock.patch.object(rewards, "SOURCE_ASSET_DIR", self.asset_dir),
            mock.patch.object(rewards, "require_cn_profile") as require_profile,
            mock.patch.object(rewards.q, "load_table") as load_table,
            mock.patch.object(sys, "argv", ["wf_rogue_rewards.py", "--validate-assets"]),
            contextlib.redirect_stdout(output),
        ):
            result = rewards.main()

        self.assertEqual(0, result)
        require_profile.assert_not_called()
        load_table.assert_not_called()
        report = output.getvalue()
        self.assertIn("15/15 valid", report)
        self.assertIn("15 distinct SHA-256", report)
        self.assertIn("item/equipment/mod/abyss/fire_01.png", report)
        self.assertIn("item/equipment/mod/abyss/universal_03.png", report)


class TestCnProfilePreflight(unittest.TestCase):
    def test_active_global_fails_before_any_read_write_or_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active_global = core.VersionProfile(
                id="global",
                label="Global",
                store=root / "global",
                fallback=None,
            )
            explicit_cn = core.VersionProfile(
                id="cn",
                label="CN",
                store=root / "cn",
                fallback=None,
            )
            active_global.store.mkdir()
            explicit_cn.store.mkdir()

            def resolve_profile(profile_id=None):
                return explicit_cn if profile_id == "cn" else active_global

            with (
                mock.patch.object(rewards.core, "resolve_profile", side_effect=resolve_profile),
                mock.patch.object(rewards.q, "load_table", return_value={}) as load_table,
                mock.patch.object(rewards.q, "save_table") as save_table,
                mock.patch.object(rewards, "load_json", return_value={}) as load_json,
                mock.patch.object(rewards, "save_json") as save_json,
                mock.patch.object(rewards.subprocess, "run") as publish,
                mock.patch.object(sys, "argv", ["wf_rogue_rewards.py"]),
            ):
                result = rewards.main()

            self.assertNotEqual(0, result)
            load_table.assert_not_called()
            save_table.assert_not_called()
            load_json.assert_not_called()
            save_json.assert_not_called()
            publish.assert_not_called()

    def test_profile_is_rechecked_immediately_before_publish(self):
        tables = fake_master_tables(placeholders=True)
        mirrors = fake_server_mirrors()
        cn_profile = core.VersionProfile(
            id="cn", label="CN", store=Path("cn-store"), fallback=None
        )
        stored_tables = {
            rewards.ITEM_T: copy.deepcopy(tables.items),
            rewards.EQUIP_T: copy.deepcopy(tables.equipment),
            rewards.EQUIP_STATUS_T: copy.deepcopy(tables.equipment_status),
            rewards.SOUL_T: copy.deepcopy(tables.ability_soul),
            rewards.RUSH_EVENT_T: copy.deepcopy(tables.rush_event),
        }
        stored_json = {
            "equipment_max_level.json": copy.deepcopy(mirrors.equipment_max_level),
            "equipment_element.json": copy.deepcopy(mirrors.equipment_element),
            "equipment_lookup.json": copy.deepcopy(mirrors.equipment_lookup),
            "equipment_ids.json": copy.deepcopy(mirrors.equipment_ids),
            "item_ids.json": copy.deepcopy(mirrors.item_ids),
        }

        def load_table(logical):
            return copy.deepcopy(stored_tables[logical])

        def save_table(logical, data):
            stored_tables[logical] = copy.deepcopy(data)

        def load_json(name):
            return copy.deepcopy(stored_json[name])

        def save_json(name, data):
            stored_json[name] = copy.deepcopy(data)

        with (
            mock.patch.object(
                rewards,
                "require_cn_profile",
                side_effect=[cn_profile, ValueError("active changed")],
            ) as preflight,
            mock.patch.object(rewards.q, "load_table", side_effect=load_table),
            mock.patch.object(rewards.q, "save_table", side_effect=save_table),
            mock.patch.object(rewards, "load_json", side_effect=load_json),
            mock.patch.object(rewards, "save_json", side_effect=save_json),
            # 写盘/发布机制本身的测试:失败关闭条件由 TestLegacyWriteBlockers 单测
            mock.patch.object(rewards, "legacy_write_blockers", return_value=[]),
            mock.patch.object(
                rewards,
                "validate_source_assets",
                return_value={spec.image_slug: Path(f"{spec.image_slug}.png")
                              for spec in rewards.WEAPONS},
            ),
            mock.patch.object(
                rewards,
                "install_source_assets",
                return_value=[f"hash-{index}" for index in range(15)],
            ),
            mock.patch.object(rewards, "_print_asset_validation"),
            mock.patch.object(rewards, "_print_plan"),
            mock.patch.object(rewards.subprocess, "run") as publish,
            mock.patch.object(
                sys,
                "argv",
                [
                    "wf_rogue_rewards.py",
                    "--write",
                    "--publish",
                    "--client-verification",
                    "client-verification.json",
                    "--ffdec",
                    "client-ffdec.jar",
                    "--java",
                    "client-java.exe",
                ],
            ),
        ):
            result = rewards.main()

        self.assertNotEqual(0, result)
        self.assertEqual(2, preflight.call_count)
        publish.assert_not_called()

    def test_write_validates_and_installs_sources_in_the_cn_store(self):
        tables = fake_master_tables(placeholders=True)
        mirrors = fake_server_mirrors()
        stored_tables = {
            rewards.ITEM_T: copy.deepcopy(tables.items),
            rewards.EQUIP_T: copy.deepcopy(tables.equipment),
            rewards.EQUIP_STATUS_T: copy.deepcopy(tables.equipment_status),
            rewards.SOUL_T: copy.deepcopy(tables.ability_soul),
            rewards.RUSH_EVENT_T: copy.deepcopy(tables.rush_event),
        }
        stored_json = {
            "equipment_max_level.json": copy.deepcopy(mirrors.equipment_max_level),
            "equipment_element.json": copy.deepcopy(mirrors.equipment_element),
            "equipment_lookup.json": copy.deepcopy(mirrors.equipment_lookup),
            "equipment_ids.json": copy.deepcopy(mirrors.equipment_ids),
            "item_ids.json": copy.deepcopy(mirrors.item_ids),
        }

        def load_table(logical):
            return copy.deepcopy(stored_tables[logical])

        def save_table(logical, data):
            stored_tables[logical] = copy.deepcopy(data)

        def load_json(name):
            return copy.deepcopy(stored_json[name])

        def save_json(name, data):
            stored_json[name] = copy.deepcopy(data)

        with tempfile.TemporaryDirectory() as directory:
            profile = core.VersionProfile(
                id="cn", label="CN", store=Path(directory), fallback=None
            )
            sources = {
                spec.image_slug: Path(directory) / f"{spec.image_slug}.png"
                for spec in rewards.WEAPONS
            }
            with (
                mock.patch.object(rewards, "require_cn_profile", return_value=profile),
                mock.patch.object(rewards.q, "load_table", side_effect=load_table),
                mock.patch.object(rewards.q, "save_table", side_effect=save_table),
                mock.patch.object(rewards, "load_json", side_effect=load_json),
                mock.patch.object(rewards, "save_json", side_effect=save_json),
                mock.patch.object(rewards, "legacy_write_blockers", return_value=[]),
                mock.patch.object(
                    rewards, "validate_source_assets", return_value=sources
                ) as validate,
                mock.patch.object(
                    rewards,
                    "install_source_assets",
                    return_value=[f"hash-{index}" for index in range(15)],
                ) as install,
                mock.patch.object(rewards, "_print_asset_validation"),
                mock.patch.object(rewards, "_print_plan"),
                mock.patch.object(sys, "argv", ["wf_rogue_rewards.py", "--write"]),
            ):
                result = rewards.main()

        self.assertEqual(0, result)
        validate.assert_called_once_with(rewards.SOURCE_ASSET_DIR, rewards.WEAPONS)
        install.assert_called_once_with(profile.store, sources, rewards.WEAPONS)

    def test_publish_collects_all_fifteen_installed_asset_paths(self):
        tables = fake_master_tables(placeholders=True)
        mirrors = fake_server_mirrors()
        stored_tables = {
            rewards.ITEM_T: copy.deepcopy(tables.items),
            rewards.EQUIP_T: copy.deepcopy(tables.equipment),
            rewards.EQUIP_STATUS_T: copy.deepcopy(tables.equipment_status),
            rewards.SOUL_T: copy.deepcopy(tables.ability_soul),
            rewards.RUSH_EVENT_T: copy.deepcopy(tables.rush_event),
        }
        stored_json = {
            "equipment_max_level.json": copy.deepcopy(mirrors.equipment_max_level),
            "equipment_element.json": copy.deepcopy(mirrors.equipment_element),
            "equipment_lookup.json": copy.deepcopy(mirrors.equipment_lookup),
            "equipment_ids.json": copy.deepcopy(mirrors.equipment_ids),
            "item_ids.json": copy.deepcopy(mirrors.item_ids),
        }

        def load_table(logical):
            return copy.deepcopy(stored_tables[logical])

        def save_table(logical, data):
            stored_tables[logical] = copy.deepcopy(data)

        def load_json(name):
            return copy.deepcopy(stored_json[name])

        def save_json(name, data):
            stored_json[name] = copy.deepcopy(data)

        with tempfile.TemporaryDirectory() as directory:
            profile = core.VersionProfile(
                id="cn", label="CN", store=Path(directory), fallback=None
            )
            sources = {
                spec.image_slug: Path(directory) / f"{spec.image_slug}.png"
                for spec in rewards.WEAPONS
            }
            expected_asset_paths = {
                rewards.q.hashed_rel(
                    f"{rewards.IMAGE_PREFIX}/{spec.image_slug}.png"
                )
                for spec in rewards.WEAPONS
            }
            snapshot = fake_release_snapshot(profile.store)
            published_manifest: dict[str, object] = {}

            def publish_snapshot(command, **_kwargs):
                manifest_path = Path(command[command.index("--snapshot") + 1])
                published_manifest.update(
                    json.loads(manifest_path.read_text(encoding="utf-8"))
                )
                return mock.Mock(returncode=0)

            with (
                mock.patch.object(rewards, "require_cn_profile", return_value=profile),
                mock.patch.object(rewards.q, "load_table", side_effect=load_table),
                mock.patch.object(rewards.q, "save_table", side_effect=save_table),
                mock.patch.object(rewards, "load_json", side_effect=load_json),
                mock.patch.object(rewards, "save_json", side_effect=save_json),
                mock.patch.object(rewards, "legacy_write_blockers", return_value=[]),
                mock.patch.object(
                    rewards, "validate_source_assets", return_value=sources
                ),
                mock.patch.object(
                    rewards,
                    "install_source_assets",
                    return_value=sorted(expected_asset_paths),
                ),
                mock.patch.object(rewards, "_print_asset_validation"),
                mock.patch.object(rewards, "_print_plan"),
                mock.patch.object(
                    validator,
                    "require_release_ready",
                    return_value=snapshot,
                ),
                mock.patch.object(
                    rewards.subprocess,
                    "run",
                    side_effect=publish_snapshot,
                ) as publish,
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        "wf_rogue_rewards.py",
                        "--write",
                        "--publish",
                        "--client-verification",
                        "client-verification.json",
                        "--ffdec",
                        "client-ffdec.jar",
                        "--java",
                        "client-java.exe",
                    ],
                ),
            ):
                result = rewards.main()

        self.assertEqual(0, result)
        publish.assert_called_once()
        command = publish.call_args.args[0]
        publish_argument = command[command.index("--tables") + 1]
        collected = set(wf_publish.collect_files(mock.Mock(tables=publish_argument)))
        published_assets = collected.intersection(expected_asset_paths)
        missing_assets = expected_asset_paths.difference(collected)
        self.assertEqual(
            15,
            len(published_assets),
            f"PUBLISHED_ASSET_PATHS={len(published_assets)}",
        )
        self.assertEqual(set(), missing_assets, f"missing={sorted(missing_assets)}")
        self.assertEqual(1, published_manifest["schema_version"])
        self.assertEqual(
            validator.release_logicals(),
            [entry["logical"] for entry in published_manifest["entries"]],
        )


class TestReleaseGate(unittest.TestCase):
    def test_publish_without_write_is_rejected_before_reads_writes_or_subprocess(self):
        with (
            mock.patch.object(rewards, "validate_source_assets") as validate_assets,
            mock.patch.object(rewards, "require_cn_profile") as profile,
            mock.patch.object(rewards.q, "load_table") as load_table,
            mock.patch.object(rewards.q, "save_table") as save_table,
            mock.patch.object(rewards.subprocess, "run") as publish,
            mock.patch.object(
                sys,
                "argv",
                [
                    "wf_rogue_rewards.py",
                    "--publish",
                    "--client-verification",
                    "client-verification.json",
                ],
            ),
        ):
            result = rewards.main()

        self.assertNotEqual(0, result)
        validate_assets.assert_not_called()
        profile.assert_not_called()
        load_table.assert_not_called()
        save_table.assert_not_called()
        publish.assert_not_called()

    def test_publish_without_client_verification_is_rejected_before_any_write(self):
        with (
            mock.patch.object(rewards, "validate_source_assets") as validate_assets,
            mock.patch.object(rewards, "require_cn_profile") as profile,
            mock.patch.object(rewards.q, "save_table") as save_table,
            mock.patch.object(rewards.subprocess, "run") as publish,
            mock.patch.object(
                sys, "argv", ["wf_rogue_rewards.py", "--write", "--publish"]
            ),
        ):
            result = rewards.main()

        self.assertNotEqual(0, result)
        validate_assets.assert_not_called()
        profile.assert_not_called()
        save_table.assert_not_called()
        publish.assert_not_called()

    def test_publish_without_client_toolchain_is_rejected_before_any_write(self):
        with (
            mock.patch.object(rewards, "validate_source_assets") as validate_assets,
            mock.patch.object(rewards, "require_cn_profile") as profile,
            mock.patch.object(rewards.q, "save_table") as save_table,
            mock.patch.object(rewards.subprocess, "run") as publish,
            mock.patch.object(
                sys,
                "argv",
                [
                    "wf_rogue_rewards.py",
                    "--write",
                    "--publish",
                    "--client-verification",
                    "client-verification.json",
                ],
            ),
        ):
            result = rewards.main()

        self.assertNotEqual(0, result)
        validate_assets.assert_not_called()
        profile.assert_not_called()
        save_table.assert_not_called()
        publish.assert_not_called()

    def _run_write_publish(self, *, gate_error=None, publisher_error=None):
        tables = fake_master_tables(placeholders=True)
        mirrors = fake_server_mirrors()
        stored_tables = {
            rewards.ITEM_T: copy.deepcopy(tables.items),
            rewards.EQUIP_T: copy.deepcopy(tables.equipment),
            rewards.EQUIP_STATUS_T: copy.deepcopy(tables.equipment_status),
            rewards.SOUL_T: copy.deepcopy(tables.ability_soul),
            rewards.RUSH_EVENT_T: copy.deepcopy(tables.rush_event),
        }
        stored_json = {
            "equipment_max_level.json": copy.deepcopy(mirrors.equipment_max_level),
            "equipment_element.json": copy.deepcopy(mirrors.equipment_element),
            "equipment_lookup.json": copy.deepcopy(mirrors.equipment_lookup),
            "equipment_ids.json": copy.deepcopy(mirrors.equipment_ids),
            "item_ids.json": copy.deepcopy(mirrors.item_ids),
        }
        events: list[str] = []

        def load_table(logical):
            events.append(f"load:{logical}")
            return copy.deepcopy(stored_tables[logical])

        def save_table(logical, data):
            events.append(f"save:{logical}")
            stored_tables[logical] = copy.deepcopy(data)

        def load_json(name):
            events.append(f"load_json:{name}")
            return copy.deepcopy(stored_json[name])

        def save_json(name, data):
            events.append(f"save_json:{name}")
            stored_json[name] = copy.deepcopy(data)

        profile = core.VersionProfile(
            id="cn", label="CN", store=Path("cn-store"), fallback=None
        )
        sources = {
            spec.image_slug: Path(f"{spec.image_slug}.png")
            for spec in rewards.WEAPONS
        }
        snapshot = fake_release_snapshot(profile.store)
        published_manifest: dict[str, object] = {}

        def install(*_args):
            events.append("install_pngs")
            return [f"hash-{index}" for index in range(15)]

        def gate(*_args, **_kwargs):
            events.append("release_gate")
            if gate_error is not None:
                raise gate_error
            return snapshot

        def publish(command, **_kwargs):
            events.append("publisher")
            if publisher_error is not None:
                raise publisher_error
            manifest_path = Path(command[command.index("--snapshot") + 1])
            published_manifest.update(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
            return mock.Mock(returncode=0)

        with (
            mock.patch.object(rewards, "require_cn_profile", return_value=profile) as preflight,
            mock.patch.object(rewards.q, "load_table", side_effect=load_table),
            mock.patch.object(rewards.q, "save_table", side_effect=save_table),
            mock.patch.object(rewards, "load_json", side_effect=load_json),
            mock.patch.object(rewards, "save_json", side_effect=save_json),
            mock.patch.object(rewards, "legacy_write_blockers", return_value=[]),
            mock.patch.object(rewards, "validate_source_assets", return_value=sources),
            mock.patch.object(rewards, "install_source_assets", side_effect=install),
            mock.patch.object(rewards, "_print_asset_validation"),
            mock.patch.object(rewards, "_print_plan"),
            mock.patch.object(validator, "require_release_ready", side_effect=gate) as gate_mock,
            mock.patch.object(rewards.subprocess, "run", side_effect=publish) as publish_mock,
            mock.patch.object(
                sys,
                "argv",
                [
                    "wf_rogue_rewards.py",
                    "--write",
                    "--publish",
                    "--client-verification",
                    "client-verification.json",
                    "--ffdec",
                    "client-ffdec.jar",
                    "--java",
                    "client-java.exe",
                ],
            ),
        ):
            result = rewards.main()

        return (
            result,
            events,
            profile,
            preflight,
            gate_mock,
            publish_mock,
            published_manifest,
        )

    def test_release_validation_failure_never_invokes_publisher(self):
        (
            result,
            events,
            _profile,
            preflight,
            gate,
            publish,
            _manifest,
        ) = self._run_write_publish(
            gate_error=RuntimeError("invalid release")
        )

        self.assertNotEqual(0, result)
        self.assertEqual(2, preflight.call_count)
        gate.assert_called_once()
        publish.assert_not_called()
        self.assertNotIn("publisher", events)
        self.assertGreater(events.index("release_gate"), events.index("install_pngs"))

    def test_valid_release_invokes_publisher_once_with_exact_allowlist_and_check(self):
        (
            result,
            events,
            profile,
            preflight,
            gate,
            publish,
            manifest,
        ) = self._run_write_publish()

        self.assertEqual(0, result)
        self.assertEqual(2, preflight.call_count)
        gate.assert_called_once_with(
            profile.store,
            Path(rewards.ROOT) / "assets",
            Path("client-verification.json"),
            ffdec=Path("client-ffdec.jar"),
            java=Path("client-java.exe"),
        )
        publish.assert_called_once()
        command = publish.call_args.args[0]
        self.assertEqual(
            [
                sys.executable,
                str(Path(rewards.ROOT) / "mod-tools" / "wf_publish.py"),
                "--tables",
                ",".join(validator.release_logicals()),
            ],
            command[:4],
        )
        self.assertEqual("--snapshot", command[4])
        self.assertEqual(rewards.ROOT, publish.call_args.kwargs["cwd"])
        self.assertIs(True, publish.call_args.kwargs["check"])
        self.assertEqual(1, manifest["schema_version"])
        self.assertEqual(
            validator.release_logicals(),
            [entry["logical"] for entry in manifest["entries"]],
        )
        self.assertEqual("release_gate", events[-2])
        self.assertEqual("publisher", events[-1])
        self.assertNotIn("pending", " ".join(command).lower())

    def test_publisher_nonzero_exit_is_propagated(self):
        failure = subprocess.CalledProcessError(9, ["wf_publish.py"])
        (
            result,
            events,
            _profile,
            _preflight,
            gate,
            publish,
            _manifest,
        ) = self._run_write_publish(
            publisher_error=failure
        )

        self.assertEqual(9, result)
        gate.assert_called_once()
        publish.assert_called_once()
        self.assertEqual(1, events.count("publisher"))


@unittest.skipUnless(not MISSING_API, "canonical builder API is not implemented yet")
class TestWeaponContract(unittest.TestCase):
    def test_all_canonical_fields_are_fixed(self):
        actual_metadata = [
            (spec.id, spec.name, spec.donor, spec.element, spec.group,
             f"{rewards.IMAGE_PREFIX}/{spec.image_slug}", spec.status_multiplier)
            for spec in rewards.WEAPONS
        ]
        self.assertEqual(EXPECTED_WEAPON_METADATA, actual_metadata)

        actual_effect_rows = {
            spec.id: tuple(
                (effect.template_id, effect.donor_line, effect.effect_kind, effect.strength)
                for effect in spec.effects
            )
            for spec in rewards.WEAPONS
        }
        expected_effect_rows = {
            weapon_id: tuple(row[:4] for row in rows)
            for weapon_id, rows in EXPECTED_EFFECT_ROWS.items()
        }
        self.assertEqual(expected_effect_rows, actual_effect_rows)

    def test_specs_and_strength_rules_are_immutable_and_complete(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            rewards.WEAPONS[0].name = "changed"
        with self.assertRaises(dataclasses.FrozenInstanceError):
            rewards.WEAPONS[0].effects[0].strength = 1

        expected_rule_keys = {
            (template_id, donor_line, effect_kind)
            for expected_rows in EXPECTED_EFFECT_ROWS.values()
            for template_id, donor_line, effect_kind, _old, _new in expected_rows
        }
        self.assertEqual(75, sum(map(len, EXPECTED_EFFECT_ROWS.values())))
        self.assertEqual(48, len(expected_rule_keys))
        self.assertEqual(expected_rule_keys, set(rewards.EFFECT_STRENGTH_RULES))
        with self.assertRaises(TypeError):
            rewards.EFFECT_STRENGTH_RULES[("x", 0, "0")] = object()

        templates = fake_templates()
        for spec in rewards.WEAPONS:
            with self.subTest(weapon=spec.id):
                rows = core.read_csv_lines(
                    rewards.build_soul_leaf(templates, spec, validate=False)
                )
                expected_rows = EXPECTED_EFFECT_ROWS[spec.id]
                expected_strengths = [expected[4] for expected in expected_rows]
                self.assertEqual(
                    expected_strengths, [strength_cells(row)[0] for row in rows]
                )
                self.assertEqual(
                    [strength_cells(row)[0] for row in rows],
                    [strength_cells(row)[1] for row in rows],
                )
                expected_durations = []
                for slot, (expected, effect) in enumerate(
                    zip(expected_rows, spec.effects), start=1,
                ):
                    template_id, donor_line = expected[:2]
                    if effect.during:
                        # 持续行不带瞬发块:c54/c55 维持捐赠行的空值
                        expected_durations.append(("", ""))
                        continue
                    expected_durations.append(EXPECTED_DURATION_OVERRIDES.get(
                        (spec.id, slot),
                        (
                            donor_duration_sentinel(template_id, donor_line, 54),
                            donor_duration_sentinel(template_id, donor_line, 55),
                        ),
                    ))
                self.assertEqual(
                    expected_durations,
                    [(row[54], row[55]) for row in rows],
                    "c54/c55 must preserve each donor sentinel except the three audited overrides",
                )

        legacy_effect = rewards.EffectSpec("3020006", "32", 1_200_000)
        legacy_spec = dataclasses.replace(rewards.WEAPONS[0], effects=(legacy_effect,))
        with self.assertRaisesRegex(ValueError, "no audited strength rule"):
            rewards.resolve_effect_strength(legacy_spec, legacy_effect)

        max_gauge_spec = next(spec for spec in rewards.WEAPONS if spec.id == "8000110")
        # 2026-09-28:245 改为 ×1 满额规则(作者给的是合计 +50%),上限 100% 照旧。
        max_gauge_probe = dataclasses.replace(
            max_gauge_spec.effects[2], strength=120000
        )
        resolution = rewards.resolve_effect_strength(max_gauge_spec, max_gauge_probe)
        self.assertEqual((100000, 120000, True), (
            resolution.value, resolution.raw_scaled, resolution.capped,
        ))

        inherited_effect = dataclasses.replace(rewards.WEAPONS[0].effects[0], strength=None)
        inherited_spec = dataclasses.replace(rewards.WEAPONS[0], effects=(inherited_effect,))
        inherited_row = core.read_csv_lines(rewards.build_soul_leaf(
            templates_for_spec(inherited_spec), inherited_spec, validate=False,
        ))[0]
        self.assertEqual(["100", "200"], inherited_row[48:50])


@unittest.skipUnless(not MISSING_API, "canonical builder API is not implemented yet")
class TestEquipmentGeneration(unittest.TestCase):
    def test_canonical_columns_match_verified_cn_schema(self):
        donor = [f"donor-{index}" for index in range(16)]
        leaf = rewards.build_equipment_leaf(core.write_csv_lines([donor]), rewards.WEAPONS[0])
        rows = core.read_csv_lines(leaf)

        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual(16, len(row))
        self.assertEqual("mod_abyss_8000101", row[0])
        # 2026-08-05:编成选装备页按 rarity↓ / numeric id↑ 排序
        # (EquipmentSelectThumbnailListRepository.sortByRarity:81-88)。保留高 ID 的
        # 方案 1 不改 APK,因此这里只锁定「深渊·」检索前缀与稳定 ID,不声明置顶。
        self.assertEqual("深渊·灰烬巨剑", row[1])
        self.assertEqual(donor[2:6], row[2:6])
        self.assertEqual("item/equipment/mod/abyss/fire_01", row[6])
        self.assertEqual(rewards.MODE_DESCRIPTION, row[7])
        self.assertEqual("5", row[8])
        self.assertEqual("true", row[9])
        self.assertEqual("8000101", row[10])
        self.assertEqual("5", row[11])
        self.assertEqual(donor[12:16], row[12:16])

    def test_equipment_leaf_preserves_string_or_bytes_type(self):
        donor_text = core.write_csv_lines([[f"donor-{index}" for index in range(16)]])
        for template_leaf in (donor_text, donor_text.encode("utf-8")):
            with self.subTest(leaf_type=type(template_leaf).__name__):
                result = rewards.build_equipment_leaf(template_leaf, rewards.WEAPONS[0])
                self.assertIs(type(template_leaf), type(result))

    def test_equipment_status_scales_every_effective_level_with_ceiling(self):
        cases = (
            (
                rewards.WEAPONS[0],
                {"1": "334,147", "5": "500,220"},
                {
                    "1": "501,221", "2": "564,249", "3": "626,276",
                    "4": "689,303", "5": "750,330",
                },
            ),
            (
                rewards.WEAPONS[1],
                {"1": "330,148", "5": "495,221"},
                {
                    "1": "495,222", "2": "558,251", "3": "620,278",
                    "4": "681,305", "5": "743,332",
                },
            ),
            (
                rewards.WEAPONS[-1],
                {"1": "544,85", "5": "815,127"},
                {
                    "1": "816,128", "2": "918,144", "3": "1020,159",
                    "4": "1122,176", "5": "1223,191",
                },
            ),
        )
        for spec, donor_levels, expected in cases:
            with self.subTest(weapon=spec.id):
                status_table = {spec.donor: donor_levels}
                result = rewards.build_equipment_status(status_table, spec)
                self.assertEqual(expected, result)
                self.assertEqual(donor_levels, status_table[spec.donor])

        doubled = dataclasses.replace(rewards.WEAPONS[0], status_multiplier=(2, 1))
        self.assertEqual(
            {
                "1": "668,294", "2": "752,332", "3": "834,368",
                "4": "918,404", "5": "1000,440",
            },
            rewards.build_equipment_status(
                {doubled.donor: {"1": "334,147", "5": "500,220"}}, doubled
            ),
        )

        descending = dataclasses.replace(rewards.WEAPONS[0], donor="descending")
        with self.assertRaisesRegex(ValueError, "monotonic"):
            rewards.build_equipment_status(
                {"descending": {"1": "500,220", "5": "334,147"}}, descending
            )


@unittest.skipUnless(not MISSING_API, "canonical builder API is not implemented yet")
class TestTokenGeneration(unittest.TestCase):
    def test_token_leaf_is_the_complete_canonical_template_clone(self):
        template = [f"template-{index}" for index in range(23)]
        template[1] = rewards.TOKEN_TEMPLATE
        template[2] = "激战代币"
        original = core.write_csv_lines([template])

        actual = rewards.build_token_leaf(original)

        expected = list(template)
        expected[0] = "rogue_event_item_99"
        expected[1] = rewards.TOKEN_ID
        expected[2] = "深渊代币"
        expected[5] = rewards.TOKEN_DESCRIPTION
        self.assertEqual([expected], core.read_csv_lines(actual))
        self.assertIs(str, type(actual))


@unittest.skipUnless(not MISSING_API, "canonical builder API is not implemented yet")
class TestSoulGeneration(unittest.TestCase):
    def test_fire_greatsword_uses_only_requested_template_lines(self):
        templates = fake_templates()
        donor_mismatch = core.read_csv_lines(templates["5050022"])[1]
        self.assertEqual(["32", "5050022#1"], [donor_mismatch[44], donor_mismatch[122]])

        leaf = rewards.build_soul_leaf(templates, rewards.WEAPONS[0])
        rows = core.read_csv_lines(leaf)
        self.assertEqual(6, len(rows))
        self.assertEqual(["51", "202", "32", "33", "32", "33"], [row[44] for row in rows])
        self.assertEqual(["5", "0", "5", "5", "8", "8"], [row[45] for row in rows])
        self.assertEqual(
            ["(None)", "", "(None)", "(None)", "", ""], [row[46] for row in rows]
        )
        self.assertEqual(
            ["225000", "75000", "300000", "300000", "300000", "300000"],
            [row[48] for row in rows],
        )
        self.assertEqual([row[48] for row in rows], [row[49] for row in rows])

    def test_fire_weapons_mirror_attack_and_direct_to_multiballs(self):
        """作者 2026-09-28:火深渊武器的攻击力/直击加成同值给协力球。

        协力球行必须是全队行的逐列镜像,只允许槽号 c0、target c45(5→8)、组 c46((None)→空)不同;
        target=8 Multiball 解析器(soul parseAt45,32/33 共用)不读 c46。先例:官方 soul 32/8
        4 行(4030008#0 等)c46 皆空;soul 无 33/8,33/8 先例在官方 ability 表(1110061#0 等)
        与自家诅咒武器。
        """
        templates = fake_templates()
        expected_kinds = {"8000101": ["32", "33"], "8000102": ["32"]}
        for spec in rewards.WEAPONS:
            rows = core.read_csv_lines(rewards.build_soul_leaf(templates, spec))
            multiball = [row for row in rows if row[45] == "8"]
            with self.subTest(weapon=spec.id):
                self.assertEqual(
                    expected_kinds.get(spec.id, []), [row[44] for row in multiball]
                )
                for row in multiball:
                    twins = [t for t in rows if t[44] == row[44] and t[45] == "5"]
                    self.assertEqual(1, len(twins))
                    diff = {
                        column for column, (a, b) in enumerate(zip(twins[0], row))
                        if a != b
                    }
                    self.assertEqual({0, 45, 46}, diff)
                    self.assertEqual(("(None)", ""), (twins[0][46], row[46]))
                    self.assertEqual(rows[-len(multiball):], multiball,
                                     "协力球行追加在末尾,旧槽号不动")

    def test_each_effect_uses_its_templates_first_line_and_fixed_columns(self):
        templates = fake_templates()
        for spec in rewards.WEAPONS:
            with self.subTest(weapon=spec.id):
                rows = core.read_csv_lines(rewards.build_soul_leaf(templates, spec))
                expected_rows = EXPECTED_EFFECT_ROWS[spec.id]
                self.assertEqual(len(expected_rows), len(rows))
                for slot, (row, effect, expected) in enumerate(
                    zip(rows, spec.effects, expected_rows), start=1,
                ):
                    template_id, donor_line, effect_kind, _old, uplift = expected
                    kind_col, target_col, group_col, (low, high) = (
                        rewards.SOUL_DURING_CONTENT if effect.during
                        else rewards.SOUL_INSTANT_CONTENT
                    )
                    self.assertEqual(123, len(row))
                    self.assertEqual(
                        [str(slot), "1", "1" if effect.during else "0"], row[:3]
                    )
                    self.assertEqual(f"{template_id}#{donor_line}", row[122])
                    self.assertEqual(effect_kind, row[kind_col])
                    donor_target = "5" if effect.during else "1"
                    self.assertEqual(
                        effect.target if effect.target is not None else donor_target,
                        row[target_col],
                    )
                    expected_group = (
                        spec.group if effect.target_groups is rewards.WEAPON_GROUP
                        else effect.target_groups if effect.target_groups is not None
                        else ""
                    )
                    self.assertEqual(expected_group, row[group_col])
                    self.assertEqual(uplift, row[low])
                    self.assertEqual(row[low], row[high])
                    expected_bool = EXPECTED_BY_EACH_TRIGGER_PULLER.get(
                        (spec.id, slot)
                    )
                    if expected_bool is not None:
                        self.assertEqual(expected_bool, row[69])
                if spec.id == "8000112":
                    self.assertEqual(
                        EXPECTED_5050022_OUTPUT_COLUMNS,
                        {
                            column: rows[3][column]
                            for column in EXPECTED_5050022_OUTPUT_COLUMNS
                        },
                        "5050022#1 must remain HpHigh + skill-triggered self damage",
                    )
                if spec.id == "8000113":
                    actual = tuple(
                        {column: row[column] for column in expected}
                        for row, expected in zip(
                            rows[:2], EXPECTED_CONQUEROR_SURVIVAL_COLUMNS,
                        )
                    )
                    self.assertEqual(EXPECTED_CONQUEROR_SURVIVAL_COLUMNS, actual)

    def test_universal_effects_use_none_sentinel_for_unfiltered_party_target(self):
        templates = fake_templates()
        expected_groups = {
            "8000113": ["(None)", "", "", "(None)"],
            "8000114": ["(None)", "(None)", "", "(None)", "(None)", ""],
            "8000115": ["", "", "(None)", "(None)", "", "(None)"],
        }
        for spec in rewards.WEAPONS[-3:]:
            with self.subTest(weapon=spec.id):
                rows = core.read_csv_lines(rewards.build_soul_leaf(templates, spec))
                self.assertEqual(expected_groups[spec.id], [row[46] for row in rows])


class TestMasterChanges(unittest.TestCase):
    def test_registers_same_id_ability_soul_items_for_every_weapon(self):
        tables = fake_master_tables()

        result = require_task2("build_master_changes")(tables)

        for spec in rewards.WEAPONS:
            with self.subTest(weapon=spec.id):
                self.assertIn(spec.id, result.items)
                donor = core.read_csv_lines(tables.items[spec.donor])[0]
                actual = core.read_csv_lines(result.items[spec.id])[0]
                expected = list(donor)
                expected[0] = f"mod_abyss_{spec.id}"
                expected[1] = spec.id
                expected[2] = f"{spec.name}魂珠"
                expected[3] = f"{rewards.IMAGE_PREFIX}/{spec.image_slug}"
                expected[12] = (
                    str(spec.element) if spec.element >= 0 else "0,3,2,1,4,5"
                )
                self.assertEqual(expected, actual)

    def test_first_run_materializes_exactly_fifteen_owned_rows_per_table(self):
        tables = fake_master_tables()
        result = require_task2("build_master_changes")(tables)
        generated = {spec.id for spec in rewards.WEAPONS}

        self.assertEqual(generated, generated.intersection(result.equipment))
        self.assertEqual(generated, generated.intersection(result.equipment_status))
        self.assertEqual(generated, generated.intersection(result.ability_soul))
        self.assertEqual(15, len(generated.intersection(result.equipment)))
        self.assertEqual(15, len(generated.intersection(result.equipment_status)))
        self.assertEqual(15, len(generated.intersection(result.ability_soul)))
        self.assertFalse(generated.intersection(tables.equipment))
        self.assertFalse(generated.intersection(tables.equipment_status))
        self.assertFalse(generated.intersection(tables.ability_soul))

    def test_second_run_is_byte_for_byte_idempotent(self):
        tables = fake_master_tables(placeholders=True, binary=True)
        builder = require_task2("build_master_changes")
        first = builder(tables)
        tables_type = require_task2("MasterTables")
        second = builder(tables_type(
            items=first.items,
            equipment=first.equipment,
            equipment_status=first.equipment_status,
            ability_soul=first.ability_soul,
            rush_event=first.rush_event,
        ))

        self.assertEqual(first, second)
        for spec in rewards.WEAPONS:
            self.assertIs(bytes, type(first.equipment[spec.id]))
            self.assertIs(bytes, type(first.ability_soul[spec.id]))
            self.assertEqual(first.equipment[spec.id], second.equipment[spec.id])
            self.assertEqual(first.ability_soul[spec.id], second.ability_soul[spec.id])
        self.assertEqual(first.items[rewards.TOKEN_ID], second.items[rewards.TOKEN_ID])
        self.assertEqual(first.rush_event["700099"], second.rush_event["700099"])

    def test_foreign_reserved_equipment_fails_without_mutating_any_table(self):
        tables = fake_master_tables(placeholders=True)
        spec = rewards.WEAPONS[0]
        foreign = [f"foreign-{index}" for index in range(16)]
        foreign[0] = "not_owned_by_abyss"
        tables.equipment[spec.id] = core.write_csv_lines([foreign])
        before = copy.deepcopy(tables)

        with self.assertRaisesRegex(ValueError, spec.id):
            require_task2("build_master_changes")(tables)

        self.assertEqual(before, tables)

    def test_foreign_reserved_ability_soul_item_fails_without_mutation(self):
        tables = fake_master_tables(placeholders=True)
        spec = rewards.WEAPONS[0]
        foreign = [f"foreign-item-{index}" for index in range(23)]
        foreign[0] = "not_owned_by_abyss"
        foreign[1] = spec.id
        tables.items[spec.id] = core.write_csv_lines([foreign])
        before = copy.deepcopy(tables)

        with self.assertRaisesRegex(ValueError, spec.id):
            require_task2("build_master_changes")(tables)

        self.assertEqual(before, tables)

    def test_orphan_soul_or_status_requires_an_owned_equipment_row(self):
        spec = rewards.WEAPONS[0]
        for field, occupant in (
            ("ability_soul", core.write_csv_lines([["foreign-soul"]])),
            ("equipment_status", {"foreign": "status"}),
        ):
            with self.subTest(field=field):
                tables = fake_master_tables()
                getattr(tables, field)[spec.id] = occupant
                before = copy.deepcopy(tables)

                with self.assertRaisesRegex(ValueError, spec.id):
                    require_task2("build_master_changes")(tables)

                self.assertEqual(before, tables)

    def test_recognized_placeholders_may_be_replaced(self):
        tables = fake_master_tables(placeholders=True)
        result = require_task2("build_master_changes")(tables)

        for spec in rewards.WEAPONS:
            row = core.read_csv_lines(result.equipment[spec.id])[0]
            self.assertEqual(f"mod_abyss_{spec.id}", row[0])
            self.assertEqual(spec.name, row[1])
            self.assertEqual(f"{rewards.IMAGE_PREFIX}/{spec.image_slug}", row[6])
            self.assertEqual(
                rewards.build_equipment_status(tables.equipment_status, spec),
                result.equipment_status[spec.id],
            )
            self.assertNotEqual(tables.ability_soul[spec.id], result.ability_soul[spec.id])

    def test_token_and_rush_event_are_complete_canonical_clones(self):
        tables = fake_master_tables()
        result = require_task2("build_master_changes")(tables)

        template = core.read_csv_lines(tables.items[rewards.TOKEN_TEMPLATE])[0]
        token = core.read_csv_lines(result.items[rewards.TOKEN_ID])[0]
        self.assertEqual("2370099", token[1])
        self.assertEqual("深渊代币", token[2])
        self.assertEqual(
            [value for index, value in enumerate(template) if index not in (0, 1, 2, 5)],
            [value for index, value in enumerate(token) if index not in (0, 1, 2, 5)],
        )

        before = core.read_csv_lines(tables.rush_event["700099"])[0]
        template_event = core.read_csv_lines(
            tables.rush_event[rogue_build.TEMPLATE_EVENT]
        )[0]
        after = core.read_csv_lines(result.rush_event["700099"])[0]
        expected = list(template_event)
        expected[0] = rogue_build.EVENT_STRING_ID
        expected[1] = rogue_build.EVENT_NAME
        expected[2] = ",".join(
            (
                rogue_build.START,
                rogue_build.END,
                rogue_build.RESULT_END,
                rogue_build.EXCHANGE_END,
            )
        )
        expected[3:5] = before[3:5]
        expected[10] = rewards.TOKEN_ID
        expected[15] = rogue_build.START
        expected[16] = rogue_build.END
        expected[17] = rogue_build.EXCHANGE_END
        self.assertEqual(expected, after)
        self.assertEqual(tables.rush_event["700001"], result.rush_event["700001"])

    def test_patch_rush_token_preserves_leaf_type(self):
        row = [f"rush-{index}" for index in range(18)]
        row[10] = rewards.TOKEN_TEMPLATE
        text = core.write_csv_lines([row])
        patcher = require_task2("patch_rush_token")

        for leaf in (text, text.encode("utf-8")):
            with self.subTest(leaf_type=type(leaf).__name__):
                result = patcher(leaf)
                self.assertIs(type(leaf), type(result))
                changed = core.read_csv_lines(result.decode("utf-8") if isinstance(result, bytes) else result)[0]
                self.assertEqual(rewards.TOKEN_ID, changed[10])
                self.assertEqual(row[:10] + row[11:], changed[:10] + changed[11:])


class TestServerMirrors(unittest.TestCase):
    def test_canonical_lookup_elements_and_donor_metadata_are_applied(self):
        mirrors = fake_server_mirrors()
        result = require_task2("apply_server_mirrors")(mirrors)

        self.assertEqual(
            [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, -1, -1, -1],
            [result.equipment_element[spec.id] for spec in rewards.WEAPONS],
        )
        for spec in rewards.WEAPONS:
            donor = mirrors.equipment_lookup[spec.donor]
            self.assertEqual({
                "name": spec.name,
                "rarity": "5",
                "category": donor["category"],
            }, result.equipment_lookup[spec.id])
            self.assertEqual(
                mirrors.equipment_max_level[spec.donor],
                result.equipment_max_level[spec.id],
            )
        self.assertEqual(mirrors.equipment_lookup["42"], result.equipment_lookup["42"])

    def test_id_mirrors_are_sorted_unique_integer_arrays(self):
        result = require_task2("apply_server_mirrors")(fake_server_mirrors())

        self.assertEqual(sorted(set(result.equipment_ids)), result.equipment_ids)
        self.assertEqual(sorted(set(result.item_ids)), result.item_ids)
        self.assertTrue(all(isinstance(value, int) for value in result.equipment_ids))
        self.assertTrue(all(isinstance(value, int) for value in result.item_ids))
        self.assertEqual(
            {int(spec.id) for spec in rewards.WEAPONS},
            {int(spec.id) for spec in rewards.WEAPONS}.intersection(result.equipment_ids),
        )
        self.assertIn(int(rewards.TOKEN_ID), result.item_ids)

    def test_second_run_produces_identical_json_bytes(self):
        applier = require_task2("apply_server_mirrors")
        first = applier(fake_server_mirrors())
        second = applier(first)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            first_bytes = write_temp_mirrors(path, first)
            second_bytes = write_temp_mirrors(path, second)

        self.assertEqual(first, second)
        self.assertEqual(first_bytes, second_bytes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
