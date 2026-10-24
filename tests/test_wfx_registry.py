# -*- coding: utf-8 -*-
"""wfx_registry.json(扩展词条框架唯一真源)与各处常量的一致性。

- wf_client_legality / wf_client_patch_scope 的补丁构造表由注册表派生:这里钉住派生结果
  与 B1-0 之前的手写表逐项相同(另加 422 的解析器范围,见 test_client_patch_kinds);
- ability_enum_map.json 的补丁构造与 requires_client_capability、保留号表;
- client-patch 构建器声明的 capability 与 client_profiles.json 档案;
- 「当前没有任何客户端消费 wfx 效果码」:wfx-* capability 是 planned,任何档案都不许声明。
"""
from __future__ import annotations

from external_sources import client_patch_path, require_external_source

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MOD_DIR = Path(__file__).resolve().parents[1]
REPO = MOD_DIR.parent
sys.path.insert(0, str(MOD_DIR))

import wf_client_legality as legality  # noqa: E402
import wf_client_patch_scope as scope  # noqa: E402
import wf_describe  # noqa: E402
import wfx_gate  # noqa: E402
import wfx_registry  # noqa: E402

# B1-0 之前的手写表(2026-09-28 取自 HEAD 5a004c84 的源码),派生后必须逐项相同。
LEGACY_CLIENT_PATCH_CONTENT_KINDS = {
    "instant_content": {"724": "kyubi-fever-ratio-v1"},
    "during_content": {"422": "dash-parameter-v1", "423": "gauge-gain-rules-v1",
                       "424": "damage-type-rules-v1"},
}
LEGACY_PATCH_PARSER_TABLES = {
    ("instant_content", "724"): frozenset({"ability"}),
    ("during_content", "423"): frozenset({
        "ability", "ability_soul", "equipment_enhancement_ability",
    }),
    ("during_content", "424"): frozenset({"ability"}),
}
LEGACY_PATCH_PARSER_CAPABILITIES = {
    ("during_content", "423"): {
        "ability_soul": "equipment-gauge-gain-rules-v1",
        "equipment_enhancement_ability": "equipment-gauge-gain-rules-v1",
    },
}
# B1-0 唯一的有意改动:补 422 盲区
ADDED_PARSER_TABLES = {("during_content", "422"): frozenset({"ability"})}
BLOCK_CLASS = {"instant_content": "InstantAbilityContentMasterValue",
               "during_content": "CommonAbilityContentMasterValue"}


def load_patch_module(relative: str, name: str):
    path = client_patch_path(relative)
    spec = importlib.util.spec_from_file_location(name, require_external_source(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module     # dataclass 注解解析需要模块已登记
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


class RegistryDerivationTests(unittest.TestCase):
    def test_derived_tables_equal_the_legacy_hand_tables(self):
        self.assertEqual(LEGACY_CLIENT_PATCH_CONTENT_KINDS, legality.CLIENT_PATCH_CONTENT_KINDS)
        # 顺序也不变:required_client_capabilities 的输出顺序依赖块的遍历顺序
        self.assertEqual(["instant_content", "during_content"],
                         list(legality.CLIENT_PATCH_CONTENT_KINDS))
        self.assertEqual({**LEGACY_PATCH_PARSER_TABLES, **ADDED_PARSER_TABLES},
                         scope.PATCH_PARSER_TABLES)
        self.assertEqual(LEGACY_PATCH_PARSER_CAPABILITIES, scope.PATCH_PARSER_CAPABILITIES)
        self.assertIsInstance(scope.PATCH_PARSER_TABLES, dict)   # mock.patch.dict 需要可变 dict

    def test_scope_and_legality_track_the_registry(self):
        self.assertEqual(wfx_registry.client_patch_content_kinds(), legality.CLIENT_PATCH_CONTENT_KINDS)
        self.assertEqual(wfx_registry.patch_parser_tables(), scope.PATCH_PARSER_TABLES)
        self.assertEqual(wfx_registry.patch_parser_capabilities(), scope.PATCH_PARSER_CAPABILITIES)
        self.assertEqual(scope.EQUIPMENT_GAUGE_CAP,
                         scope.PATCH_PARSER_CAPABILITIES["during_content", "423"]["ability_soul"])

    def test_enum_map_agrees_with_the_registry(self):
        enum_map = wf_describe.enum_map()
        gated = {(block, value): case.get("requires_client_capability")
                 for block, cases in enum_map["cases"].items()
                 for value, case in cases.items() if case.get("requires_client_capability")}
        self.assertEqual({(entry["block"], entry["value"]): entry["capability"]
                          for entry in wfx_registry.patch_content_kinds()}, gated)
        for entry in wfx_registry.patch_content_kinds():
            case = enum_map["cases"][entry["block"]][entry["value"]]
            self.assertEqual(entry["ctor"], case["ctor"])
            self.assertEqual(entry["ctor"], enum_map["enums"][BLOCK_CLASS[entry["block"]]][entry["value"]])
            # 借用 unique_condition_id 列装参数/规则码的构造,enum_map 里确实声明了该列
            if entry["unique_condition_id_column"] in ("param_id", "rule_code"):
                self.assertIn("unique_condition_id", case["fields"])

    def test_reserved_numbers_are_free_and_occupied_numbers_exist(self):
        enums = wf_describe.enum_map()["enums"]
        reserved = wfx_registry.load()["reserved_numbers"]
        for enum_name in ("CommonAbilityContentMasterValue", "InstantAbilityContentMasterValue"):
            table = reserved[enum_name]
            self.assertFalse(set(table["occupied"]) & set(table["reserved"]), enum_name)
            for value, ctor in table["occupied"].items():
                self.assertEqual(ctor, enums[enum_name][value], (enum_name, value))
            for value in table["reserved"]:
                self.assertNotIn(value, enums[enum_name], (enum_name, value))
        for name, table in reserved.items():
            self.assertFalse(set(table["occupied"]) & set(table["reserved"]), name)

    def test_effect_codes_keep_plans_separate_from_v35e_local_evidence(self):
        registry = wfx_registry.load()
        codes = wfx_registry.effect_codes()
        planned_codes = {10, 20, 21, 22, 23, 30, 31, 40, 50, 51, 52}
        candidate_codes = {24, 25, 26, 27, 28, 29, 60, 61, 62, 71}
        self.assertEqual(planned_codes | candidate_codes, set(codes))
        for code, effect in codes.items():
            with self.subTest(code=code):
                band = next(item for item in registry["effect_code_ranges"]
                            if item["from"] <= code <= item["to"])
                capability = wfx_registry.capabilities()[effect["capability"]]
                if code in planned_codes:
                    self.assertEqual(1, band["batch"])
                    self.assertEqual("planned", capability["status"])
                    self.assertIn("wfx-core-v1", wfx_registry.capability_closure([effect["capability"]]))
                else:
                    self.assertEqual("local_candidate", capability["status"])
                    self.assertEqual(64, len(capability["integration_evidence"]["swf_sha256"]))
                    self.assertNotIn("wfx-core-v1", wfx_registry.capability_closure([effect["capability"]]))
                self.assertTrue(effect["hooks"])
        self.assertEqual({"0": "wfx-core-v1"},
                         {bit: entry["capability"] for bit, entry in registry["flags"]["bits"].items()})

    def test_code_20_follows_author_ruling_two(self):
        """作者裁决 2026-09-28 #2(优先于设计稿正文):不新开乘区,码 20 并入官方独立乘区池、
        与原生同池相加;池 = 全伤害 723/421、直击 693/410、技能 694/411、能力 695/412、
        强化弹射 696/413;属性限定 = 满足属性条件才计入。码 21/22/23 不受影响。"""
        registry = wfx_registry.load()
        effect = wfx_registry.effect_codes()[20]
        self.assertEqual("sum", effect["reduce"])                  # 与原生同池相加,不是 prod
        self.assertTrue(effect["merges_into_official_pool"])
        self.assertEqual("damage_pool", effect["arg"])
        for text in (effect["label"], effect["text_template"], effect["name"]):
            self.assertNotIn("独立", text)
            self.assertNotIn("mul", text)
        pools = registry["arg_kinds"]["damage_pool"]["pools"]
        self.assertEqual(
            {"all": ("723", "421"), "direct": ("693", "410"), "skill": ("694", "411"),
             "ability": ("695", "412"), "power_flip": ("696", "413")},
            {entry["name"]: (entry["instant_content"], entry["during_content"]) for entry in pools.values()})
        # 每个池的瞬发/持续构造都存在、同名,且都是官方 SeparatedTerm* 独立乘区
        enum_map = wf_describe.enum_map()
        for number, entry in pools.items():
            with self.subTest(pool=entry["name"]):
                instant = enum_map["enums"]["InstantAbilityContentMasterValue"][entry["instant_content"]]
                during = enum_map["enums"]["CommonAbilityContentMasterValue"][entry["during_content"]]
                self.assertEqual(entry["ctor"], instant)
                self.assertEqual(entry["ctor"], during)
                self.assertTrue(instant.startswith("SeparatedTerm"))
                self.assertLessEqual(int(number), registry["arg_kinds"]["damage_pool"]["pool_field_mask"])
        # 属性组与码 21–23 的伤害掩码同位
        damage_mask = registry["arg_kinds"]["damage_mask"]
        damage_pool = registry["arg_kinds"]["damage_pool"]
        for key in ("element_group_mask", "element_shift", "elements"):
            self.assertEqual(damage_mask[key], damage_pool[key], key)
        self.assertFalse(damage_pool["pool_field_mask"] & damage_pool["element_group_mask"])
        for code in (21, 22, 23):
            self.assertEqual("damage_mask", wfx_registry.effect_codes()[code]["arg"], code)
        self.assertEqual("prod", wfx_registry.effect_codes()[22]["reduce"])   # 22 不受裁决影响

    def test_every_capability_named_by_the_tools_is_registered(self):
        catalog = wfx_registry.capabilities()
        named = ({capability for gated in legality.CLIENT_PATCH_CONTENT_KINDS.values()
                  for capability in gated.values()}
                 | {capability for by_table in scope.PATCH_PARSER_CAPABILITIES.values()
                    for capability in by_table.values()}
                 | {legality.PANEL_OVERRIDE_V1, legality.PANEL_OVERRIDE_V2,
                    legality.EQUIPMENT_DESC_OVERRIDE, legality.EQUIPMENT_ENHANCED_LOOK,
                    legality.EQUIPMENT_ENHANCED_PARTY_FRAME}
                 | set(legality.ENHANCED_LOOK_PREFIX_CAPABILITIES.values())
                 | set(legality.EQUIPMENT_KEY_PREFIX_CAPABILITIES.values()))
        for capability in named:
            self.assertEqual("shipped", catalog[capability]["status"], capability)
        self.assertEqual("cosmetic", catalog[legality.EQUIPMENT_DESC_OVERRIDE]["level"])
        self.assertEqual("cosmetic", catalog[legality.EQUIPMENT_ENHANCED_LOOK]["level"])
        self.assertEqual("cosmetic", catalog[legality.EQUIPMENT_ENHANCED_PARTY_FRAME]["level"])
        # 觉醒专属素材缺补丁 = 受限装备仍被提供星铁钢、服务端 400(静默失效);置顶缺补丁 = 原生顺序
        self.assertEqual("semantic", catalog[legality.EQUIPMENT_AWAKENING_MATERIAL]["level"])
        self.assertEqual("cosmetic", catalog[legality.EQUIPMENT_SORT_PIN]["level"])
        self.assertEqual("crash", catalog[scope.EQUIPMENT_GAUGE_CAP]["level"])

    def test_enhanced_look_string_keys_track_the_legality_prefixes(self):
        """注册表 string_keys 里的两个外观前缀 = wf_client_legality 的前缀,且都指向同一 capability(cosmetic)。"""
        rules = wfx_registry.load()["string_keys"]
        look = {prefix: rule for prefix, rule in rules.items()
                if rule["capability"] == legality.EQUIPMENT_ENHANCED_LOOK}
        self.assertEqual(set(legality.ENHANCED_LOOK_KEY_PREFIXES), set(look))
        for prefix, rule in look.items():
            self.assertEqual("cosmetic", rule["level"], prefix)
        for prefix, rule in rules.items():
            self.assertIn(rule["capability"], wfx_registry.capabilities(), prefix)
            self.assertIn(rule["level"], wfx_registry.LEVELS, prefix)
        # 面板覆盖前缀与外观前缀互不包含:同一个键不会被两条规则同时认领
        for prefix in legality.ENHANCED_LOOK_KEY_PREFIXES:
            self.assertIsNone(legality.panel_override_capability(prefix + "item/x"))
            self.assertFalse(prefix.startswith(legality.PANEL_OVERRIDE_KEY_PREFIX))

    def test_every_look_family_string_key_tracks_the_legality_mapping(self):
        """注册表 string_keys 与 legality 的外观族「前缀 → capability」逐项相同;编成槽框归自己的 capability。"""
        rules = wfx_registry.load()["string_keys"]
        family = legality.ENHANCED_LOOK_PREFIX_CAPABILITIES
        self.assertEqual(family, {prefix: rule["capability"] for prefix, rule in rules.items() if prefix in family})
        self.assertEqual(set(family), {prefix for prefix, rule in rules.items()
                                       if rule["capability"] in set(family.values())})
        party = rules[legality.ENHANCED_PARTY_FRAME_OVERRIDE_KEY_PREFIX]
        self.assertEqual((legality.EQUIPMENT_ENHANCED_PARTY_FRAME, "cosmetic"), (party["capability"], party["level"]))
        # 任意两个 string_keys 前缀互不为前缀:wfx_gate 按 startswith 认领,一个键只归一条规则
        for a in rules:
            for b in rules:
                self.assertTrue(a == b or not a.startswith(b), (a, b))

    def test_equipment_behaviour_string_keys_track_the_legality_mapping(self):
        """注册表 string_keys 与 legality 的装备行为键「前缀 → capability」逐项相同,且 string_keys 的 level
        就是 capability 自己的 level(awakening_material_ 是 semantic:门禁拒绝把它发给没打补丁的接收端)。"""
        rules = wfx_registry.load()["string_keys"]
        family = legality.EQUIPMENT_KEY_PREFIX_CAPABILITIES
        self.assertEqual(family, {prefix: rule["capability"] for prefix, rule in rules.items() if prefix in family})
        self.assertEqual(set(family), {prefix for prefix, rule in rules.items()
                                       if rule["capability"] in set(family.values())})
        for prefix, capability in family.items():
            self.assertEqual(wfx_registry.capability_level(capability), rules[prefix]["level"], prefix)
        self.assertEqual("semantic", rules[legality.AWAKENING_MATERIAL_KEY_PREFIX]["level"])
        self.assertEqual("cosmetic", rules[legality.EQUIPMENT_SORT_PIN_KEY_PREFIX]["level"])


class ClientPatchConstantTests(unittest.TestCase):
    def test_equipment_rules_capabilities_are_registered(self):
        rules = load_patch_module("equipment-rules/rules.py", "_wfx_registry_equipment_rules")
        catalog = wfx_registry.capabilities()
        for capability in (rules.CAPABILITY_RULES, rules.CAPABILITY_GAUGE, *rules.INHERITED_CAPABILITIES):
            self.assertEqual("shipped", catalog[capability]["status"], capability)
        self.assertEqual({"ability", *rules.GAUGE_PARSERS}, set(scope.PATCH_PARSER_TABLES["during_content", "423"]))

    def test_description_override_capabilities_are_registered(self):
        rules = load_patch_module("equipment-description-override/rules.py", "_wfx_registry_desc_rules")
        catalog = wfx_registry.capabilities()
        self.assertEqual(legality.EQUIPMENT_DESC_OVERRIDE, rules.CAPABILITY)
        for capability in (rules.CAPABILITY, *rules.INHERITED_CAPABILITIES):
            self.assertEqual("shipped", catalog[capability]["status"], capability)

    def test_enhanced_look_capabilities_are_registered(self):
        rules = load_patch_module("equipment-enhanced-look/rules.py", "_wfx_registry_look_rules")
        desc = load_patch_module("equipment-description-override/rules.py", "_wfx_registry_look_desc_rules")
        catalog = wfx_registry.capabilities()
        self.assertEqual(legality.EQUIPMENT_ENHANCED_LOOK, rules.CAPABILITY)
        self.assertEqual((legality.ENHANCED_PIXELART_TIER2_KEY_PREFIX, legality.ENHANCED_FRAME_OVERRIDE_KEY_PREFIX),
                         (rules.TIER2_PREFIX, rules.FRAME_PREFIX))
        # 叠在 cf91b29b 上:继承层 = 说明覆盖 APK 的 10 项
        self.assertEqual(set(desc.INHERITED_CAPABILITIES) | {desc.CAPABILITY}, set(rules.INHERITED_CAPABILITIES))
        for capability in (rules.CAPABILITY, *rules.INHERITED_CAPABILITIES):
            self.assertEqual("shipped", catalog[capability]["status"], capability)
        self.assertEqual("cosmetic", catalog[rules.CAPABILITY]["level"])

    def test_item_rarity_frame_override_capabilities_are_registered(self):
        rules = load_patch_module("item-rarity-frame-override/rules.py", "_wfx_registry_rarity_frame_rules")
        catalog = wfx_registry.capabilities()
        self.assertEqual(legality.ITEM_RARITY_FRAME_OVERRIDE, rules.CAPABILITY)
        self.assertEqual(legality.ITEM_RARITY_FRAME_OVERRIDE_KEY_PREFIX, rules.PREFIX)
        self.assertEqual(("cosmetic", "shipped"), (catalog[rules.CAPABILITY]["level"],
                                                   catalog[rules.CAPABILITY]["status"]))
        rule = wfx_registry.load()["string_keys"][rules.PREFIX]
        self.assertEqual((rules.CAPABILITY, "cosmetic"), (rule["capability"], rule["level"]))
        # 每个登记底包声明的能力都已登记,且都不含本补丁(候选 APK = 底包 + 1)
        for base, entry in rules.KNOWN_BASES.items():
            self.assertNotIn(rules.CAPABILITY, entry["capabilities"], base[:8])
            for capability in entry["capabilities"]:
                self.assertEqual("shipped", catalog[capability]["status"], (base[:8], capability))

    def test_enhanced_party_frame_capabilities_are_registered(self):
        rules = load_patch_module("equipment-enhanced-party-frame/rules.py", "_wfx_registry_party_rules")
        look = load_patch_module("equipment-enhanced-look/rules.py", "_wfx_registry_party_look_rules")
        catalog = wfx_registry.capabilities()
        self.assertEqual(legality.EQUIPMENT_ENHANCED_PARTY_FRAME, rules.CAPABILITY)
        self.assertEqual(legality.ENHANCED_PARTY_FRAME_OVERRIDE_KEY_PREFIX, rules.PREFIX)
        self.assertNotEqual(look.CAPABILITY, rules.CAPABILITY)
        # 叠在 7056f7dc 上:继承层 = v1 APK 的 11 项
        self.assertEqual(set(look.INHERITED_CAPABILITIES) | {look.CAPABILITY}, set(rules.INHERITED_CAPABILITIES))
        for capability in (rules.CAPABILITY, *rules.INHERITED_CAPABILITIES):
            self.assertEqual("shipped", catalog[capability]["status"], capability)
        self.assertEqual("cosmetic", catalog[rules.CAPABILITY]["level"])
        self.assertIn(rules.PREFIX, wfx_registry.load()["string_keys"])

    def test_awakening_material_capabilities_are_registered(self):
        rules = load_patch_module("equipment-awakening-material/rules.py", "_wfx_registry_awaken_rules")
        party = load_patch_module("equipment-enhanced-party-frame/rules.py", "_wfx_registry_awaken_party_rules")
        catalog = wfx_registry.capabilities()
        self.assertEqual(legality.EQUIPMENT_AWAKENING_MATERIAL, rules.CAPABILITY)
        self.assertEqual(legality.AWAKENING_MATERIAL_KEY_PREFIX, rules.PREFIX)
        # 叠在编成槽框 b 版 2f085757 上:继承层 = 编成槽框 APK 的 12 项(与现装 a 版 14396ce0 相同)
        self.assertEqual(set(party.INHERITED_CAPABILITIES) | {party.CAPABILITY}, set(rules.INHERITED_CAPABILITIES))
        for capability in (rules.CAPABILITY, *rules.INHERITED_CAPABILITIES):
            self.assertEqual("shipped", catalog[capability]["status"], capability)
        self.assertEqual("semantic", catalog[rules.CAPABILITY]["level"])
        self.assertIn(rules.PREFIX, wfx_registry.load()["string_keys"])

    def test_sort_pin_capabilities_are_registered(self):
        rules = load_patch_module("equipment-sort-pin/rules.py", "_wfx_registry_sort_pin_rules")
        awaken = load_patch_module("equipment-awakening-material/rules.py", "_wfx_registry_sort_pin_awaken_rules")
        catalog = wfx_registry.capabilities()
        self.assertEqual(legality.EQUIPMENT_SORT_PIN, rules.CAPABILITY)
        self.assertEqual(legality.EQUIPMENT_SORT_PIN_KEY_PREFIX, rules.PREFIX)
        # 叠在觉醒专属素材上:继承层 = 编成槽框的 12 项 + 觉醒专属素材
        self.assertEqual(set(awaken.INHERITED_CAPABILITIES) | {awaken.CAPABILITY}, set(rules.INHERITED_CAPABILITIES))
        for capability in (rules.CAPABILITY, *rules.INHERITED_CAPABILITIES):
            self.assertEqual("shipped", catalog[capability]["status"], capability)
        self.assertEqual("cosmetic", catalog[rules.CAPABILITY]["level"])
        self.assertIn(rules.PREFIX, wfx_registry.load()["string_keys"])


class ClientProfileTests(unittest.TestCase):
    def setUp(self):
        self.profiles = wfx_gate.load_profiles()

    def test_the_three_profiles_and_the_default(self):
        self.assertEqual({"local-mumu", "gray-1047", "official", "test-v34", "test-v35e", "local-v35k3"}, set(self.profiles))
        self.assertEqual("local-mumu", wfx_gate.default_publish_profile())
        self.assertEqual(frozenset(), self.profiles["official"].capabilities)

    def test_local_mumu_equals_the_installed_b0b13112_capabilities(self):
        """b0b13112 = 编成槽框 b → 觉醒专属素材 → 装备置顶 → 物品底色覆盖(2026-09-28 装本机):置顶 APK 的 14 项 + 本层 1 项。"""
        sort_pin = load_patch_module("equipment-sort-pin/rules.py", "_wfx_profile_sort_pin_rules")
        rarity = load_patch_module("item-rarity-frame-override/rules.py", "_wfx_profile_rarity_rules")
        self.assertEqual(frozenset(sort_pin.INHERITED_CAPABILITIES) | {sort_pin.CAPABILITY, rarity.CAPABILITY},
                         self.profiles["local-mumu"].capabilities)
        self.assertEqual(15, len(self.profiles["local-mumu"].capabilities))
        data = json.loads(wfx_gate.PROFILES_PATH.read_text(encoding="utf-8"))
        evidence = data["profiles"]["local-mumu"]["evidence"]
        self.assertTrue(evidence["apk_sha256"].startswith("b0b13112"))
        self.assertTrue(evidence["swf_sha256"].startswith("b4a22c8a"))

    def test_gray_1047_is_the_1047_base_without_equipment_layers(self):
        rules = load_patch_module("equipment-rules/rules.py", "_wfx_profile_equipment_rules")
        gray = self.profiles["gray-1047"].capabilities
        self.assertEqual(frozenset(rules.INHERITED_CAPABILITIES), gray)
        for absent in ("equipment-rules-v1", "equipment-gauge-gain-rules-v1",
                       "equipment-description-override-v1"):
            self.assertNotIn(absent, gray)
        self.assertIn("gauge-gain-rules-v1", gray)       # 作者 0928 确认灰方装了 1047 系回槽限制补丁
        import wf_cursed_weapons
        self.assertEqual(wf_cursed_weapons.BASE_CLIENT_CAPABILITIES, gray)

    def test_only_v35e_profile_can_consume_implemented_wfx_effects(self):
        for code, effect in wfx_registry.effect_codes().items():
            needed = set(wfx_registry.capability_closure([effect["capability"]]))
            for name, profile in self.profiles.items():
                with self.subTest(code=code, profile=name):
                    implemented = wfx_registry.capabilities()[effect["capability"]]["status"] == "local_candidate"
                    self.assertEqual(name == "test-v35e" and implemented, needed <= profile.capabilities)
        planned = {name for name, entry in wfx_registry.capabilities().items() if entry["status"] == "planned"}
        for name, profile in self.profiles.items():
            self.assertFalse(planned & profile.capabilities, name)

    def test_loader_rejects_planned_or_unknown_capabilities(self):
        for bad, message in ((["wfx-core-v1"], "planned"), (["no-such-capability-v9"], "没有")):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "client_profiles.json"
                path.write_text(json.dumps({
                    "schema_version": 1, "default_publish_profile": "x",
                    "profiles": {"x": {"capabilities": bad}}}), encoding="utf-8")
                with self.assertRaisesRegex(wfx_gate.GateError, message):
                    wfx_gate.load_profiles(path)

    def test_unknown_profile_name_is_an_error(self):
        with self.assertRaisesRegex(wfx_gate.GateError, "未知客户端档案"):
            wfx_gate.resolve_profile("gray-9999")


if __name__ == "__main__":
    unittest.main()
