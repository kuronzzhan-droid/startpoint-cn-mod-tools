# -*- coding: utf-8 -*-
"""深渊连战活动元数据生成回归测试。"""
import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wf.tools.rogue import rogue_build as rogue_build  # noqa: E402


def thumbnail_pick_fields(field: str) -> dict:
    thumbnail = "quest/thumbnail/test/boss"
    return {
        "thumb": thumbnail,
        "thumbnail_field": field,
        "thumbnail_evidence": {
            "schema": rogue_build.THUMBNAIL_EVIDENCE_SCHEMA,
            "field": field,
            "thumbnail": thumbnail,
            "asset_logical": thumbnail + ".png",
            "asset_exists": True,
            "source_match": "exact_field",
            "source_category": "test",
            "source_logical": "master/quest/test.orderedmap",
            "source_path": ["test"],
            "source_level": 100,
            "floor_key": None,
            "static_verified": True,
            "runtime_simulated": False,
            "gameplay_verified": False,
        },
    }


class TestRushEventMetadata(unittest.TestCase):
    def test_shared_event_folder_remains_the_only_gauntlet_entry(self):
        event_list = {
            "700007": ["template"],
            "700098": ["old fantasy direct entry"],
            "700099": ["old abyss direct entry"],
        }

        actual = rogue_build.enforce_gauntlet_hub_event_list(event_list)

        self.assertIs(event_list, actual)
        self.assertEqual({"700007": ["template"]}, actual)

    def test_generated_single_player_quest_requires_rank_130(self):
        row = [f"column-{index}" for index in range(110)]
        before = list(row)

        actual = rogue_build.enforce_gauntlet_player_rank(row)

        self.assertIs(row, actual)
        self.assertEqual("130", actual[48])
        self.assertEqual(before[:48] + before[49:], actual[:48] + actual[49:])

    def test_existing_rows_in_both_gauntlet_hubs_are_repaired_to_rank_130(self):
        rows = {}
        for event_id in rogue_build.GAUNTLET_HUB_EVENT_IDS:
            row = [f"{event_id}-column-{index}" for index in range(110)]
            row[48] = "(None)"
            rows[event_id] = {"1": rogue_build.join(row, False)}
        unrelated = [f"unrelated-column-{index}" for index in range(110)]
        rows["700007"] = {"1": rogue_build.join(unrelated, False)}

        actual = rogue_build.enforce_gauntlet_quest_table_player_rank(rows)

        self.assertIs(rows, actual)
        for event_id in rogue_build.GAUNTLET_HUB_EVENT_IDS:
            self.assertEqual("130", rogue_build.cells(actual[event_id]["1"])[48])
        self.assertEqual(unrelated, rogue_build.cells(actual["700007"]["1"]))

    def test_abyss_event_always_uses_abyss_token(self):
        row = [f"column-{index}" for index in range(18)]
        row[10] = "2370007"
        before = list(row)

        actual = rogue_build.patch_event_metadata(row)

        self.assertEqual("2370099", actual[10])
        self.assertEqual(before[:10] + before[11:], actual[:10] + actual[11:])

    def test_complete_event_leaf_is_rebuilt_from_template_with_banner_only(self):
        template = [f"template-{index}" for index in range(18)]
        current = [f"foreign-{index}" for index in range(18)]
        current[3] = "custom-banner"
        current[4] = "custom-background"

        actual = rogue_build.build_event_metadata_leaf(
            rogue_build.join(template, False),
            rogue_build.join(current, False),
        )

        expected = list(template)
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
        expected[3:5] = current[3:5]
        expected[10] = rogue_build.TOKEN_ID
        expected[15] = rogue_build.START
        expected[16] = rogue_build.END
        expected[17] = rogue_build.EXCHANGE_END
        self.assertEqual([expected], [rogue_build.cells(actual)])
        self.assertIs(str, type(actual))

    def test_unscaled_hp_keeps_absolute_evidence_and_actual_value(self):
        native = {
            "verified": True,
            "absolute_verified": True,
            "native_hp": 1000.0,
            "components": [{
                "code": "standard_boss", "kind": "standard",
                "evidence_kind": "absolute", "native_hp": 1000.0,
            }],
        }

        audit = rogue_build.unscaled_floor_hp_record(
            7, native, base_duration_s=100.0, duration_s=100.0,
            curse_hp=1.0, raw_c86=2.0, target=50.0,
            scaling_error="standard c86 outside policy window",
        )

        self.assertTrue(audit["verified"])
        self.assertTrue(audit["absolute_verified"])
        self.assertTrue(audit["target_exempt"])
        self.assertEqual(2000.0, audit["true_hp"])
        self.assertEqual(20.0, audit["realized_dps"])
        records = [{"r": 1, "baseline_dps": 1.0,
                    "target_dps": 1.0, "warmup": True}]
        records.extend({"r": r, "baseline_dps": 50.0, "target_dps": 50.0}
                       for r in range(2, 7))
        records.append(audit)
        self.assertEqual([], rogue_build.hp_curve_errors(
            records, 7, last_band=(40.0, 60.0)))
        self.assertEqual([], rogue_build.hp_curve_errors(
            records, 7, last_band=(40.0, 60.0), ramp=True))

    def test_folder_preview_matches_server_fixed_rewards(self):
        import json
        try:
            source = rogue_build.core.resolve_server_dir() / "assets/rush_event_quest_folder.json"
        except ValueError as error:
            self.skipTest(f"configured server reward mirror unavailable: {error}")
        if not source.is_file():
            self.skipTest("configured server is missing assets/rush_event_quest_folder.json")
        rewards = json.loads(source.read_text("utf8"))["700099"]["1"]
        template = [f"template-{index}" for index in range(37)]
        actual = rogue_build.cells(rogue_build.build_deep_abyss_folder_leaf(
            rogue_build.join(template, False), rewards))
        self.assertEqual(["1", "1", rogue_build.EVENT_NAME], actual[:3])
        self.assertEqual(template[3:7], actual[3:7])
        decoded = [dict(zip(("type", "id", "count"), map(int, actual[i:i+3])))
                   for i in range(7, 37, 3) if actual[i] != "(None)"]
        self.assertEqual(rewards, decoded)
        for base in range(7 + 3 * len(rewards), 37, 3):
            self.assertEqual(["(None)", "", "(None)"], actual[base:base + 3])

    def test_folder_preview_tracks_custom_reward_configuration(self):
        rewards = [{"type": 0, "id": 99, "count": 314}]
        leaf = rogue_build.build_deep_abyss_folder_leaf(
            rogue_build.join([""] * 37, True), rewards)
        self.assertIsInstance(leaf, bytes)
        self.assertEqual(["0", "99", "314"], rogue_build.cells(leaf)[7:10])
        with self.assertRaises(ValueError):
            rogue_build.build_deep_abyss_folder_leaf(leaf, rewards * 11)
        with self.assertRaises(ValueError):
            rogue_build.build_deep_abyss_folder_leaf(leaf, [{"type": 0, "id": 99, "count": 0}])


class TestBossKindSynchronization(unittest.TestCase):
    def setUp(self):
        self.previous_special_kind = rogue_build._SPECIAL_KIND
        rogue_build._SPECIAL_KIND = {"special_enemy": 6}

    def tearDown(self):
        rogue_build._SPECIAL_KIND = self.previous_special_kind

    def test_kind_is_corrected_when_boss_table_changes(self):
        kind_of = rogue_build.zone_boss_kind_fixer(
            {"general_enemy": {}},
            {"standard_enemy": {}},
        )

        self.assertEqual(1, kind_of("general_enemy", 0))
        self.assertEqual(0, kind_of("standard_enemy", 1))
        self.assertEqual(6, kind_of("special_enemy", 1))

    def test_matching_kind_requires_no_rewrite(self):
        kind_of = rogue_build.zone_boss_kind_fixer(
            {"general_enemy": {}},
            {"standard_enemy": {}},
        )

        self.assertIsNone(kind_of("general_enemy", 1))
        self.assertIsNone(kind_of("standard_enemy", 0))
        self.assertIsNone(kind_of("special_enemy", 6))


class TestHpAdapterAudit(unittest.TestCase):
    @staticmethod
    def general_native(values, *, evidence="absolute"):
        return {
            "verified": True,
            "absolute_verified": evidence == "absolute",
            "native_hp": float(sum(values)),
            "components": [
                {
                    "code": "duplicate_boss",
                    "boss_occurrence": index,
                    "kind": "general",
                    "hp_curve_kind": "hit",
                    "evidence_kind": evidence,
                    "native_hp": float(value),
                }
                for index, value in enumerate(values, start=1)
            ],
        }

    def test_standard_parser_retains_each_health_form_index(self):
        got = rogue_build.standard_enemy_hp_base({
            "au": [
                {"d": ["T1", 100.0]},
                {"d": ["T2"]},
                {"d": ["T1", 250.0]},
            ],
        })

        self.assertEqual((100.0, 250.0), got["health_terms"])
        self.assertEqual(
            ({"form_index": 0, "base_hp": 100.0},
             {"form_index": 2, "base_hp": 250.0}),
            got["health_forms"],
        )

    def test_standard_readback_floors_once_per_boss_occurrence(self):
        same_boss = {
            "components": [
                {"code": "standard", "boss_occurrence": 1,
                 "kind": "standard", "native_hp": 1.65},
                {"code": "standard", "boss_occurrence": 1,
                 "kind": "standard", "native_hp": 1.65},
            ],
        }
        repeated_boss = {
            "components": [
                {"code": "standard", "boss_occurrence": 1,
                 "kind": "standard", "native_hp": 1.65},
                {"code": "standard", "boss_occurrence": 2,
                 "kind": "standard", "native_hp": 1.65},
            ],
        }

        self.assertEqual(3.0, rogue_build._true_hp_at_c86(same_boss, 1.0))
        self.assertEqual(2.0, rogue_build._true_hp_at_c86(repeated_boss, 1.0))

    def test_floor_native_hp_expands_standard_forms_and_repeated_bosses(self):
        evidence = {
            "code": "standard", "selected_level": 80,
            "logical": "battle/boss/example.esdl.amf3.deflate",
            "form_count": 3,
            "health_terms": (100.0, 250.0),
            "health_forms": (
                {"form_index": 0, "base_hp": 100.0},
                {"form_index": 2, "base_hp": 250.0},
            ),
            "base_hp": 350.0,
        }
        with mock.patch.object(
                rogue_build, "standard_boss_hp_evidence",
                return_value=evidence):
            got = rogue_build.floor_native_hp(
                ["standard", "standard"], 80,
                standard_boss={"standard": {}}, boss_level={}, orochi_ex={},
            )

        self.assertTrue(got["verified"])
        self.assertTrue(got["absolute_verified"])
        self.assertEqual(385.0, got["native_hp"])
        self.assertEqual([1, 1, 2, 2], [part["boss_occurrence"]
                                       for part in got["components"]])
        self.assertEqual(
            ["form[0]", "form[2]", "form[0]", "form[2]"],
            [part["phase"] for part in got["components"]],
        )

    def test_adapter_keeps_duplicate_occurrences_and_reads_final_clone(self):
        native = self.general_native([100.0, 100.0])
        final_native = self.general_native([200.0, 200.0])

        receipt = rogue_build.build_hp_adaptation_audit(
            8, native, family="general", channel="boss_level",
            destination="boss_level.c2",
            baseline_target_hp=200.0, final_target_hp=400.0,
            baseline_c86=1.0, final_c86=1.0,
            readback_native=final_native,
            baseline_component_hp=(100.0, 100.0),
        )

        self.assertEqual(2, len(receipt.components))
        self.assertEqual([1, 2], [part.boss_occurrence
                                  for part in receipt.components])
        self.assertEqual(0.0, receipt.baseline_error_hp)
        self.assertEqual(0.0, receipt.final_error_hp)
        self.assertTrue(receipt.within_tolerance)

    def test_adapter_records_each_boss_destination_instead_of_floor_union(self):
        native = self.general_native([100.0, 300.0])
        final_native = self.general_native([200.0, 600.0])
        native["components"][0]["code"] = "hit"
        native["components"][1]["code"] = "fix"
        final_native["components"][0]["code"] = "clone_hit"
        final_native["components"][1]["code"] = "clone_fix"
        receipt = rogue_build.build_hp_adaptation_audit(
            8, native, family="general", channel="boss_level",
            destination={"hit": "boss_level.c2", "fix": "boss_level.c5"},
            baseline_target_hp=400.0, final_target_hp=800.0,
            baseline_c86=1.0, final_c86=1.0,
            readback_native=final_native,
            baseline_component_hp=(100.0, 300.0),
        )
        self.assertEqual(
            ["boss_level.c2", "boss_level.c5"],
            [part.destination for part in receipt.components])

    def test_strict_gate_rejects_proxy_exemption_and_readback_error(self):
        native = self.general_native([100.0])
        receipt = rogue_build.build_hp_adaptation_audit(
            9, native, family="general", channel="boss_level",
            destination="boss_level.c2",
            baseline_target_hp=90.0, final_target_hp=90.0,
            baseline_c86=1.0, final_c86=1.0,
        )
        audit = {
            "r": 9, "verified": True, "absolute_verified": False,
            "target_exempt": True, "adapter_audit": receipt,
        }

        errors = rogue_build.strict_target_hp_errors([audit])

        self.assertTrue(any("target_exempt" in error for error in errors))
        self.assertTrue(any("代理 HP" in error for error in errors))
        self.assertTrue(any("回读超差" in error for error in errors))

    def test_strict_candidate_requires_absolute_evidence(self):
        metrics = {
            "native": self.general_native([100.0], evidence="proxy"),
            "hp_channel": "boss_level",
        }
        self.assertEqual(
            "strict-proxy-evidence",
            rogue_build.strict_hp_candidate_error(metrics),
        )
        metrics["native"] = self.general_native([100.0])
        self.assertIsNone(rogue_build.strict_hp_candidate_error(metrics))

    def test_quest_hp_plan_separates_enemy_device_and_boss_columns(self):
        boss_plan = rogue_build.quest_hp_multiplier_plan(
            baseline=2.0, final=3.0, has_boss=True)
        self.assertEqual(
            {"enemy": 1.0, "device_or_summon": 1.0, "boss": 2.0},
            boss_plan["baseline"])
        self.assertEqual(
            {"enemy": 1.0, "device_or_summon": 1.0, "boss": 3.0},
            boss_plan["final"])

        warmup_plan = rogue_build.quest_hp_multiplier_plan(
            baseline=2.0, final=3.0, has_boss=False)
        self.assertEqual(
            {"enemy": 3.0, "device_or_summon": 1.0, "boss": 1.0},
            warmup_plan["final"])

        record = {
            "r": 2, "family": "general", "baseline_c86": 2.0, "c86": 3.0,
            "quest_hp_multipliers": boss_plan,
        }
        self.assertEqual([], rogue_build.quest_hp_multiplier_errors([record]))
        coupled = copy.deepcopy(record)
        coupled["quest_hp_multipliers"]["final"]["enemy"] = 3.0
        self.assertTrue(any(
            "错误捆绑三类实体" in error
            for error in rogue_build.quest_hp_multiplier_errors([coupled])))

    def test_verified_audit_renders_deterministic_non_developer_report(self):
        native = self.general_native([100.0])
        receipt = rogue_build.build_hp_adaptation_audit(
            2, native, family="general", channel="boss_level",
            destination="boss_level.c2",
            baseline_target_hp=100.0, final_target_hp=100.0,
            baseline_c86=1.0, final_c86=1.0,
        )
        quest_row = ["(None)"] * 110
        quest_row[86] = quest_row[87] = quest_row[88] = "1"
        document = rogue_build.build_hp_audit_document(
            seed=20260825, rounds=2, difficulty="hell",
            enemy_level="ramp",
            hp_audits=[{
                "r": 2, "adapter_audit": receipt,
                "verified": True, "absolute_verified": True,
                "target_exempt": False,
                "damage_checks": {
                    "duplicate_boss": (
                        rogue_build.general_damage_check_contract(
                            {}, {}, {}, source_max_hp=100.0,
                            baseline_max_hp=100.0, final_max_hp=100.0,
                            source_routine_id="(None)",
                            final_routine_id="(None)", materialized=True)),
                },
                "quest_hp_multipliers": rogue_build.quest_hp_multiplier_plan(
                    baseline=1.0, final=1.0, has_boss=True),
            }],
            floor_records=[{
                "r": 2,
                "row": quest_row,
                "pick": {
                    "field": "source_field", "play_field": "mod_rogue_f2",
                    "level": 100, "bosses": ["duplicate_boss"],
                    "runtime_bosses": ["mod_rogue_boss2"],
                    **thumbnail_pick_fields("source_field"),
                },
                "curse": {
                    "picks": [{"name": "术式扰流"}],
                    "combo": None,
                    "desc": "「术式扰流」技能耐性40%",
                },
            }],
            chain_reports=[
                {"round": "1", "ok": True},
                {"round": "2", "ok": True},
                {"round": "99", "ok": True},
            ],
        )
        expected_hash = document["tool"]["sha256"]
        self.assertEqual("wf-rogue-hp-audit/v4", document["schema"])
        self.assertEqual("static_dry_run", document["verification_scope"])
        self.assertIs(document["gameplay_verified"], False)
        first = rogue_build.render_hp_audit_report(
            document, expected_tool_sha256=expected_hash)
        second = rogue_build.render_hp_audit_report(
            copy.deepcopy(document), expected_tool_sha256=expected_hash)
        self.assertEqual(first, second)
        self.assertIn("静态严格验收通过", first)
        self.assertIn("Boss 关绝对证据：`1/1`", first)
        self.assertIn("`static_dry_run`", first)
        self.assertIn("gameplay_verified=false", first)
        self.assertIn("- [ ] 真机进入关卡", first)
        self.assertIn("不证明已经发布或落库", first)
        self.assertEqual(["术式扰流"], document["floors"][0]["curse_names"])
        self.assertEqual(
            "source_field", document["floors"][0]["thumbnail_source_field"])
        self.assertIn("Boss 封面静态审计", first)
        self.assertIn("## 逐关逐阶段明细", first)
        self.assertIn("「术式扰流」技能耐性40%", first)
        self.assertEqual(0, document["summary"]["source_proxy_components"])
        self.assertEqual(
            rogue_build.curse_capability_matrix_receipt(),
            document["selection_policy"]["curse_capability_matrix"])
        self.assertEqual(
            rogue_build.client_bundled_curve_baseline_receipt(),
            document["selection_policy"]["client_bundled_curve_baseline"])
        capability = document["floors"][0]["curse_capability_profile"]
        self.assertEqual("boss_level", capability["channel"])
        self.assertEqual("general", capability["family"])
        self.assertEqual(
            rogue_build.CURSE_CAPABILITY_MATRIX[("boss_level", "general")],
            capability["declared"])
        quest_receipt = document["floors"][0]["quest_hp_multipliers"]
        self.assertEqual(
            {"enemy": 1.0, "device_or_summon": 1.0, "boss": 1.0},
            quest_receipt["table_readback"])
        hp_columns_forged = copy.deepcopy(document)
        hp_columns_forged["floors"][0]["quest_hp_multipliers"][
            "table_readback"]["enemy"] = 2.0
        hp_columns_forged["document_sha256"] = (
            rogue_build.hp_audit_document_digest(hp_columns_forged))
        self.assertTrue(any(
            "c86/c87/c88 回读与最终计划不一致" in error
            for error in rogue_build.verify_hp_audit_document(
                hp_columns_forged, expected_tool_sha256=expected_hash)))

        thumbnail_forged = copy.deepcopy(document)
        thumbnail_forged["floors"][0]["thumbnail_evidence"][
            "thumbnail"] = "quest/thumbnail/test/other"
        thumbnail_forged["document_sha256"] = (
            rogue_build.hp_audit_document_digest(thumbnail_forged))
        self.assertTrue(any(
            "Boss 封面字段/资源来源不闭合" in error
            for error in rogue_build.verify_hp_audit_document(
                thumbnail_forged, expected_tool_sha256=expected_hash)))

        # source_proxy_components is an optional audit detail.  An older
        # receipt did not distinguish source
        # and final evidence, so it must remain verifiable/renderable using
        # final proxy_components as the conservative fallback.
        legacy = copy.deepcopy(document)
        legacy["summary"].pop("source_proxy_components")
        legacy["document_sha256"] = rogue_build.hp_audit_document_digest(legacy)
        self.assertEqual([], rogue_build.verify_hp_audit_document(
            legacy, expected_tool_sha256=expected_hash))
        self.assertIn("源代理组件：`0`", rogue_build.render_hp_audit_report(
            legacy, expected_tool_sha256=expected_hash))

        tampered = copy.deepcopy(document)
        tampered["summary"]["proxy_components"] = 1
        with self.assertRaisesRegex(ValueError, "拒绝生成绿色报告"):
            rogue_build.render_hp_audit_report(tampered)

        # 即使攻击者重算摘要，静态回执也不能自称真机通过；缺 scope 同样拒绝。
        for key, value, needle in (
                ("gameplay_verified", True, "gameplay_verified"),
                ("verification_scope", None, "verification_scope")):
            forged = copy.deepcopy(document)
            if value is None:
                forged.pop(key)
            else:
                forged[key] = value
            forged["document_sha256"] = rogue_build.hp_audit_document_digest(forged)
            verification_errors = rogue_build.verify_hp_audit_document(
                forged, expected_tool_sha256=expected_hash)
            self.assertTrue(any(needle in error for error in verification_errors))
            with self.assertRaisesRegex(ValueError, "拒绝生成绿色报告"):
                rogue_build.render_hp_audit_report(
                    forged, expected_tool_sha256=expected_hash)

        matrix_forged = copy.deepcopy(document)
        matrix_forged["selection_policy"]["curse_capability_matrix"][0][
            "capabilities"]["hp_multiplier"] = False
        matrix_forged["document_sha256"] = rogue_build.hp_audit_document_digest(
            matrix_forged)
        self.assertTrue(any(
            "诅咒能力矩阵不一致" in error
            for error in rogue_build.verify_hp_audit_document(matrix_forged)))

        profile_forged = copy.deepcopy(document)
        profile_forged["floors"][0]["curse_capability_profile"][
            "declared"]["field_action"] = False
        profile_forged["document_sha256"] = rogue_build.hp_audit_document_digest(
            profile_forged)
        self.assertTrue(any(
            "诅咒能力声明与矩阵不一致" in error
            for error in rogue_build.verify_hp_audit_document(profile_forged)))

        curve_forged = copy.deepcopy(document)
        curve_forged["selection_policy"]["client_bundled_curve_baseline"][
            "member_sha256"] = "0" * 64
        curve_forged["document_sha256"] = rogue_build.hp_audit_document_digest(
            curve_forged)
        self.assertTrue(any(
            "客户端内置曲线基线不一致" in error
            for error in rogue_build.verify_hp_audit_document(curve_forged)))

        identity_closed = copy.deepcopy(document)
        identity_closed["floors"][0]["identity_reference_closures"] = [{
            "kind": "general_enemy_watch.partner_alias",
            "source_code": "duplicate_boss",
            "clone_code": "mod_rogue_boss2",
            "source_reference_count": 2,
            "clone_reference_count": 2,
            "verified": True,
        }]
        identity_closed["summary"]["identity_reference_closure_rounds"] = 1
        identity_closed["summary"]["identity_reference_closures"] = 1
        identity_closed["document_sha256"] = rogue_build.hp_audit_document_digest(
            identity_closed)
        self.assertEqual([], rogue_build.verify_hp_audit_document(
            identity_closed, expected_tool_sha256=expected_hash))
        identity_forged = copy.deepcopy(identity_closed)
        identity_forged["floors"][0]["identity_reference_closures"][0][
            "clone_reference_count"] = 1
        identity_forged["document_sha256"] = rogue_build.hp_audit_document_digest(
            identity_forged)
        self.assertTrue(any(
            "partner 别名未等价回读" in error
            for error in rogue_build.verify_hp_audit_document(identity_forged)))

        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.json"
            report_path = Path(tmp) / "report.md"
            rogue_build.write_hp_audit_document(str(audit_path), document)
            result = subprocess.run(
                [sys.executable, "-m", "wf.tools.rogue.rogue_build",
                 "--verify-audit-json", str(audit_path),
                 "--audit-report", str(report_path)],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("中文验收报告已生成", result.stdout)
            self.assertEqual(report_path.read_text(encoding="utf-8"), first)

            original_json = audit_path.read_bytes()
            overwrite = subprocess.run(
                [sys.executable, "-m", "wf.tools.rogue.rogue_build",
                 "--verify-audit-json", str(audit_path),
                 "--audit-report", str(audit_path)],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30,
            )
            self.assertNotEqual(overwrite.returncode, 0)
            self.assertIn("不得覆盖", overwrite.stdout)
            self.assertEqual(audit_path.read_bytes(), original_json)


if __name__ == "__main__":
    unittest.main()
