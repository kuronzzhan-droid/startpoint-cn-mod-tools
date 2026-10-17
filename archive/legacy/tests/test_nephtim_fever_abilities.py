"""奈芙提姆六能力原生数据合同与条件边界。"""

from wf.paths import root_path
from copy import deepcopy
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

from test_bianca_dragon_abilities import official_sources
import wf_client_legality as legality
import wf_nephtim_fever_abilities as kit

AS3 = Path(('${WF_ROOT}/outputs/re-workspace/decompile/scripts/pinball'.replace("${WF_ROOT}", str(root_path()))))


class NephtimFeverAbilitiesTest(unittest.TestCase):
    def setUp(self):
        self.source, _ = official_sources()
        self.rows = kit.ability_rows(self.source)

    def test_native_columns_sentinels_dark_targets_and_source_immutability(self):
        before = deepcopy(self.source)
        kit.ability_rows(self.source)
        self.assertEqual(before, self.source)
        self.assertEqual({f"169989{i}" for i in range(1, 7)}, set(self.rows))
        for rows in self.rows.values():
            for row in rows:
                self.assertEqual(126, len(row))
                self.assertEqual([], legality.client_legality_problems("ability", row))
                self.assertEqual([], legality.declared_block_field_problems("ability", row))
                self.assertEqual([], legality.ability_element_column_problems("ability", row, 6))
                self.assertNotIn("White", row)
                self.assertNotIn("Green", row)
                self.assertNotIn("Red", row)

    def test_a1_and_a3_are_main_only(self):
        for sid, rows in self.rows.items():
            self.assertEqual({"false" if sid in ("1699891", "1699893") else "true"}, {r[1] for r in rows})

    def test_a1_initially_charges_self_without_increasing_the_maximum(self):
        opening = self.rows["1699891"][0]
        self.assertEqual(("false", "0", "0", "211", "0", "50000", "50000"),
                         (opening[1], opening[6], opening[27], opening[47], opening[48], opening[51], opening[52]))
        self.assertFalse(any(r[47] == "245" for rows in self.rows.values() for r in rows))
        donor = self.source["1110211"][0]  # Christmas Bianca's native opening self charge.
        self.assertEqual((donor[5], donor[27], donor[47], donor[48]),
                         (opening[5], opening[27], opening[47], opening[48]))
        meta = kit.metadata()["opening_skill_charge"]
        self.assertEqual((50, 0, False), (meta["initial_charge_percent"],
                         meta["gauge_maximum_increase_percent"], meta["requires_resonance"]))
        # 作者 2026-09-27（方案B）：I536 强化开关移入队长，六能力里不再有 I536。
        self.assertFalse(any(r[47] == "536" for rows in self.rows.values() for r in rows))
        flag = kit.enhance_row(self.source)
        self.assertEqual(("2", "600000", "600000", "Black", "0", "536"),
                         (flag[6], flag[9], flag[10], flag[11], flag[13], flag[47]))
        self.assertEqual(kit.CHANGE_SKILL_STRING_ID, flag[70])
        # 文案规则2：「技能强化」条目只写强化了什么，不写数字与时间；底层 250%/20 秒未改。
        description = kit.flat_string_rows()[flag[70]][0][0]
        self.assertEqual(kit.CHANGE_SKILL_DESCRIPTION, description)
        self.assertIn("强化『" + kit.SKILL_NAME + "』", description)
        self.assertNotRegex(description, r"[0-9０-９]")
        self.assertNotIn("秒", description)
        self.assertEqual(250, kit.metadata()["skill_enhancement"]["attack_buff_percent"])

    def test_summoning_counts_only_state_frames_and_fever_end_clears_only_that_state(self):
        self.assertEqual(4, len(self.rows["1699891"]))
        summon, clear = self.rows["1699891"][1:3]
        self.assertEqual(("2", "Black", "12", "232", "0", "100000", "100000"),
                         (summon[6], summon[11], summon[13], summon[27], summon[28], summon[30], summon[31]))
        # 作者 2026-09-27：召唤间隔 1.5 秒 → 2 秒（120 帧 × 100000）。
        self.assertEqual(("12000000", "12000000", "(None)", "0", "16998901", "629"),
                         (summon[32], summon[33], summon[34], summon[35], summon[37], summon[47]))
        self.assertEqual(120, kit.SUMMON_PERIOD_FRAMES)
        self.assertEqual(120, kit.metadata()["skill_enhancement"]["period_frames"])
        self.assertEqual([kit.SPAWN_STRING_ID, kit.SPAWN_ACTION_PATH], summon[70:72])
        self.assertEqual(("0", "0", "184", "528", "0", "16998901"),
                         (clear[6], clear[13], clear[27], clear[47], clear[48], clear[68]))
        self.assertEqual(1500, kit.metadata()["skill_enhancement"]["per_ball_duration_frames"])
        custom = kit.ability_rows(self.source, summon_unique_id=12345, spawn_action_path="custom/action")
        self.assertEqual("12345", custom["1699891"][1][37])
        self.assertEqual("12345", custom["1699891"][2][68])
        self.assertEqual("custom/action", custom["1699891"][1][71])

    def test_silent_zone_exit_cleanup_requires_existing_self_state_and_non_fever(self):
        row = self.rows["1699891"][3]
        self.assertEqual(["187", "0", "", "", "", "", "16998901"], row[6:13])
        self.assertEqual(("186", "77", "100000", "100000", "528", "0", "16998901"),
                         (row[13], row[27], row[30], row[31], row[47], row[48], row[68]))
        custom = kit.ability_rows(self.source, summon_unique_id=12345)["1699891"][3]
        self.assertEqual(("12345", "12345"), (custom[12], custom[68]))
        for fever in (False, True):
            for own_state in (False, True):
                # Native P187 checks only self; an unrelated UID remains intact.
                states = {99999} | ({16998901} if own_state else set())
                deletions = 0
                if not fever and int(row[12]) in states:
                    states.remove(int(row[68]))
                    deletions += 1
                self.assertIn(99999, states)
                self.assertEqual(int(own_state and not fever), deletions)
                self.assertEqual(own_state and fever, 16998901 in states)

    @unittest.skipUnless(AS3.is_dir(), "native decompile unavailable")
    def test_summon_state_native_encoffin_cleanup_and_existing_unique_precondition(self):
        import wf_nephtim_fever_skill as skill
        self.assertEqual("true", skill.unique_rows()[str(kit.SUMMON_UNIQUE_ID)][0][13])
        member = (AS3 / "scene/battle/battle/squad/member/MemberImpl.as").read_text()
        encoffin = member[member.index("public function enterEncoffinmentState("):]
        self.assertIn("conditionSlot.purge(coffinNotRemoveConditionUnique)", encoffin[:500])
        conditions = (AS3 / "scene/battle/battle/condition/ConditionSlot.as").read_text()
        purge = conditions[conditions.index("public function purge("):conditions.index("public function matchDirectionForStatistics")]
        self.assertIn("Boolean(_loc7_.params[3])", purge)
        self.assertIn("if(!(param1 || !_loc8_))", purge)
        pre = (AS3 / "common/data/ability/pre/AbilityPreconditionMasterValueTools.as").read_text()
        unique = pre[pre.index("case 187:"):pre.index("case 188:")]
        self.assertIn("ConditionTargetKind.Unique(int(_loc4_.unique_condition_id)),1,Option.Some(1)", unique)

    def test_a2_and_a6_dark_gates_and_native_party_piercing_extension(self):
        extension, direct, maximum = self.rows["1699892"]
        final = self.rows["1699896"][0]
        for row in (extension, direct, final):
            self.assertEqual(("2", "600000", "600000", "Black", "0"),
                             (row[6], row[9], row[10], row[11], row[13]))
        # 作者 2026-09-27：队长那份 20% 并入能力2，单行合计 40%。
        self.assertEqual(("190", "40000", ""), (extension[47], extension[51], extension[48]))
        self.assertEqual(40, kit.metadata()["piercing_extension"]["increase_percent"])
        # 作者 2026-09-27：Fever 中暗属性技能槽上限+10% 由队长移入能力2（c1=true，不加主位限制）。
        self.assertEqual(("true", "1", "2", "600000", "600000", "Black", "12"),
                         (maximum[1], maximum[5], maximum[6], maximum[9], maximum[10], maximum[11], maximum[13]))
        self.assertEqual(("4", "false", "124", "5", "Black", "10000", "10000"),
                         (maximum[97], maximum[108], maximum[109], maximum[110], maximum[111],
                          maximum[113], maximum[114]))
        expected = kit._during(self.source, 124, 10_000, target=5)
        expected[0] = "ruin_girl_campus_2"
        self.assertEqual(expected, maximum)
        self.assertEqual(10, kit.metadata()["skill_gauge_maximum"]["increase_percent"])
        self.assertEqual(("33", "250000", "5", "Black"),
                         (direct[47], direct[51], direct[48], direct[49]))
        self.assertEqual(("33", "100000", "5", "Black"),
                         (final[47], final[51], final[48], final[49]))

    def test_a3_current_combo_independent_term(self):
        combo = self.rows["1699893"][0]
        self.assertEqual(("1", "2", "Black", "12", "2", "100000", "100000", "(None)"),
                         (combo[5], combo[6], combo[11], combo[13], combo[97], combo[100], combo[101], combo[102]))
        # 作者 2026-09-17 减半：每连击 5% → 2.5%（两列同为词条低级/满级，一起取半）。
        self.assertEqual(("410", "5", "Black", "2500", "2500"),
                         (combo[109], combo[110], combo[111], combo[113], combo[114]))
        self.assertEqual(2_500, kit.COMBO_STRENGTH)
        bonuses = [count * int(combo[113]) / 1000 for count in (0, 1, 70, 1000, 2)]
        self.assertEqual([0, 2.5, 175, 2500, 5], bonuses)
        self.assertEqual(2.5, kit.metadata()["combo_bonus"]["per_combo_percent"])
        self.assertEqual(2.5, kit.metadata()["combo_bonus"]["attack_percent_per_combo"])
        attack = self.rows["1699893"][1]
        self.assertEqual(attack[109], "0")  # ordinary attack; not a second independent term
        self.assertEqual(attack[:109] + attack[110:], combo[:109] + combo[110:])
        self.assertEqual(("false", "2", "Black", "12", "(None)"),
                         (attack[1], attack[6], attack[11], attack[13], attack[102]))
        attack_bonuses = [count * int(attack[113]) / 1000 for count in (0, 1, 70, 1000, 2)]
        self.assertEqual(bonuses, attack_bonuses)
        self.assertIsNone(kit.metadata()["combo_bonus"]["trigger_limit"])
        self.assertTrue(kit.metadata()["combo_bonus"]["falls_when_combo_falls"])

    def test_a3_piercing_growth_is_gated_per_frame_and_capped_at_ten_triggers(self):
        # 作者 2026-09-17 减半：贯穿成长 20% → 10%；2026-09-27 第二批：能力3 改成有上限的弱化版
        # （攻击力 +5%、直击 +10%，各最多 10 次），无上限部分搬进队长（+1%/次，见 test_nephtim_leader_growth）。
        for row, content, strength in zip(self.rows["1699893"][2:4], ("32", "33"), ("5000", "10000")):
            self.assertEqual(("2", "Black", "12", "235", "100000", "12000000", "10"),
                             (row[6], row[11], row[13], row[27], row[30], row[32], row[34]))
            self.assertEqual((content, "5", "Black", strength, strength, "", ""),
                             (row[47], row[48], row[49], row[51], row[52], row[57], row[58]))
            self.assertEqual("0", row[35])  # 无 CT
        self.assertEqual((5_000, 10_000, 10, 120),
                         (kit.PIERCING_CAPPED_ATTACK_STRENGTH, kit.PIERCING_CAPPED_DIRECT_STRENGTH,
                          kit.PIERCING_CAPPED_LIMIT, kit.PIERCING_PERIOD_FRAMES))
        growth = kit.metadata()["piercing_growth"]
        self.assertEqual((5, 10, 120), (growth["attack_percent"],
                                        growth["direct_damage_percent"], growth["period_frames"]))
        self.assertEqual(10, growth["trigger_limit"])
        self.assertTrue(growth["persists_after_fever"])
        # 队长无上限部分：第二批 1%/次，第三轮（2026-09-27c）回调到 7%/次。
        self.assertEqual(("leader", 7, None), (growth["uncapped_share"]["location"],
                                               growth["uncapped_share"]["percent_each"],
                                               growth["uncapped_share"]["trigger_limit"]))
        # 队长同形无上限行与能力3两行除限次/强度外逐格相同（队长按列 −2 转换）。
        uncapped = kit.piercing_growth_rows(self.source, 1_000, 1_000)
        for capped, free in zip(self.rows["1699893"][2:4], uncapped):
            self.assertEqual([34, 51, 52], [i for i in range(5, 126) if capped[i] != free[i]])
            self.assertEqual(("(None)", "1000"), (free[34], free[51]))

    def test_a4_covers_dark_members_and_all_cooperative_balls_with_distinct_targets(self):
        members, balls = self.rows["1699894"]
        for row in (members, balls):
            self.assertEqual(("true", "2", "Black", "12"), (row[1], row[6], row[11], row[13]))
        self.assertEqual(("4", "410", "50000", "50000"),
                         (members[97], members[109], members[113], members[114]))
        self.assertEqual(("5", "Black"), (members[110], members[111]))
        # 作者 2026-09-27 多人卡顿修复：T77 每 1 帧 → 每 10 帧（帧 × 100000）。
        self.assertEqual(("77", "1000000", "1000000", "629"),
                         (balls[27], balls[30], balls[31], balls[47]))
        self.assertEqual(kit.multiball_fever.ACTION_PATH, balls[71])
        self.assertEqual([""] * 29, balls[97:])

    def test_only_the_two_invoke_skill_pulses_move_to_a_ten_frame_period(self):
        # 多人卡顿修复只动能力3/4 的 T77→629 行；能力1 的 T77 I528 清理行不调 DSL，仍每帧。
        pulses = {(sid, i): row for sid, rows in self.rows.items()
                  for i, row in enumerate(rows) if row[27] == "77" and row[47] == "629"}
        self.assertEqual({("1699893", 5), ("1699894", 1)}, set(pulses))
        for row in pulses.values():
            self.assertEqual(["1000000", "1000000"], row[30:32])
        self.assertEqual(10, kit.multiball_direct.UPDATE_PERIOD_FRAMES)
        self.assertEqual(10, kit.metadata()["current_multiball_direct_bonus"]["update_period_frames"])
        self.assertEqual(10, kit.metadata()["fever_multiball_direct_bonus"]["update_period_frames"])
        reconcile = self.rows["1699891"][3]
        self.assertEqual(("77", "100000", "100000", "528"),
                         (reconcile[27], reconcile[30], reconcile[31], reconcile[47]))

    def test_a5_has_no_resonance_gate_and_uses_native_timers_and_three_second_status(self):
        for row, gate, trigger, threshold in zip(self.rows["1699895"],
                ("186", "12"), ("77", "248"), ("60000000", "30000000")):
            self.assertEqual(("0", gate, trigger, threshold, "26"),
                             (row[6], row[13], row[27], row[30], row[47]))
            self.assertEqual(("18000000", "18000000", "100000", "100000"), tuple(row[57:61]))
            self.assertEqual("(None)", row[34])

    @unittest.skipUnless(AS3.is_dir(), "native decompile unavailable")
    def test_native_condition_frame_counter_and_precondition_filter_are_not_elapsed_time(self):
        source = (AS3 / "scene/battle/battle/ability/ThresholdConditionKeepFrameCountHandler.as").read_text()
        update = source[source.index("public function update()"):source.index("public function setContinuationDataIfMatch")]
        self.assertIn("conditionCountGetter(targetKind)", update)
        self.assertIn("if(_loc1_ >= triggerCount)", update)
        self.assertIn("countHandler(_loc2_,1)", update)
        handler = (AS3 / "scene/battle/battle/ability/_InstantAbility/AbilityTriggerHandler.as").read_text()
        count = handler[handler.index("public function countHandler("):]
        self.assertLess(count.index("AbilityPrecondition_Impl_.isActive"), count.index("calledCount += param2"))


if __name__ == "__main__":
    unittest.main()
