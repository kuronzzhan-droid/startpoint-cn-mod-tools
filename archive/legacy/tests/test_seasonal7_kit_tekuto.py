# -*- coding: utf-8 -*-
"""特克托 kit 的离线单元测试（不写包、不读 live store 大表）。

python -m unittest mod-tools/tests/test_seasonal7_kit_tekuto.py
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_assets  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402
import wf_seasonal7_kit_tekuto as K  # noqa: E402
import wf_seasonal7_specs as S  # noqa: E402

ROOT = TOOLS.parent
DESIGN = ROOT / K.DESIGN_REL
PLAN = ROOT / K.REVISION_REL


def plan():
    return K.load_revision_plan(ROOT)


def tree(level="2"):
    return K.donor_tree(level, plan())


def fake_families():
    """与 clone_effect_family 返回形状一致（只含 rewrite_effect_refs 需要的键）。"""
    out = []
    for src_dir, sub, fx in K.FAMILIES:
        donor = src_dir.rsplit("/", 1)[-1]
        out.append({"src_dir": src_dir, "dst_dir": f"battle/effect/skill_unique/{K.CODE}/{sub}",
                    "donor": donor, "dst_name": sub, "copied_bases": sorted(fx)})
    return out


def _design_ability_rows(design):
    """设计稿里的 6 键词条行（= 改版前的包内现行行），供 revision_ability_rows 的幂等/重建用例使用。"""
    pre = {key: [] for key in (f"{K.CID}{i}" for i in range(1, 7))}
    for slot in range(1, 7):
        key = design["ability_keys"][f"slot{slot}"]["key"]
        pre[key] = [list(rec["row"]) for rec in design["abilities"][f"slot{slot}"]]
    return pre


def _slv_terms(node, out=None):
    """树里所有 SLv 项（带 min/max 或 alvN_* 的 dict）。"""
    out = [] if out is None else out
    if isinstance(node, dict):
        if any(k.startswith("alv") or k in ("min", "max") for k in node):
            out.append(node)
        for v in node.values():
            _slv_terms(v, out)
    elif isinstance(node, list):
        for v in node:
            _slv_terms(v, out)
    return out


def png_bytes(size, color, store=True):
    from PIL import Image
    img = Image.new("RGBA", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()
    return wf_assets.png_encode(raw) if store else raw


@unittest.skipUnless(DESIGN.is_file() and PLAN.is_file(), "design/revision json not present")
class TreeAssemblyTest(unittest.TestCase):
    def setUp(self):
        self.design = json.loads(DESIGN.read_text(encoding="utf-8"))
        self.plan = plan()

    def test_donor_tree_satisfies_revision_plan(self):
        """改版树必须逐条满足 plan.json，且静态门禁全绿（特效引用改写前后都成立）。"""
        for lv in ("1", "2"):
            t = K.donor_tree(lv, self.plan)
            for fam in fake_families():
                t, _info = C.rewrite_effect_refs(t, fam)
            probs, facts = K.revision_tree_problems(t, lv, self.plan)
            self.assertEqual(probs, [])
            self.assertEqual(K.dsl_quick_problems(t), [])
            self.assertEqual(K.cooldown_width_problems(t), [])
            self.assertEqual(facts["frames"],
                             sorted([5, 9, 20, 80] + [s[1] for s in K.STAGES]
                                    + [K.FINALE_FRAME, K.COOLDOWN_FRAME, *K.EXT_FRAMES,
                                       K.BEAM_END_FRAME]))

    def test_revision_tree_problems_catches_regressions(self):
        """把方案要点逐条拆掉，对账门禁必须变红（门禁不是恒通过）。"""
        import copy
        base = K.donor_tree("2", self.plan)
        self.assertEqual(K.revision_tree_problems(base, "2", self.plan)[0], [])

        def mutated(fn):
            t = copy.deepcopy(base)
            fn(t)
            return K.revision_tree_problems(t, "2", self.plan)[0]

        def drop_head(t):
            t[11][1].pop(0)                                     # 删 RemoveEventFromOwner

        def drop_cannon_condition(t):
            body = t[11][1]
            for i, node in enumerate(body):
                if node[0] == "Command" and node[1][0] == "CreateCondition" \
                        and node[1][2][0][0] == "ACUnique":
                    body.pop(i)
                    break

        def restore_reference_point(t):
            for node in C.walk(t):
                if isinstance(node, list) and node and node[0] == "CreateHitArea" and node[2] == K.BALL:
                    node[3] = ["AB"]                            # 判定区回到不跟随的坐标系
                    break

        def rename_event(t):
            for node in C.walk(t):
                if isinstance(node, list) and node and node[0] == "Wait" and node[2] == K.EV_CANNON:
                    node[2] = "*"
                    break

        # ---- 审查修复轮的负向对照：把每条修复拆掉，对账门禁必须变红
        def drop_engine_condition(t):                               # R-M4：删掉技能自给的「引擎启动」
            body = t[11][1]
            for i, node in enumerate(body):
                if node[0] == "Command" and node[1][0] == "CreateCondition" \
                        and node[1][2][0][0] == "ACUnique" and node[1][2][0][1] == int(K.UID_ENGINE):
                    body.pop(i)
                    return
            raise AssertionError("engine CreateCondition not found")

        def regate_finale(t):                                       # R-m6：把终幕塞回开关槽2
            find = next(n for n in t[11][1] if n[0] == "Command" and n[1][0] == "FindNearSubjects")
            body = find[1][6][1]
            for i, node in enumerate(body):
                if node[0] == "Event" and node[1][0] == "Wait" and node[1][1] == K.FINALE_FRAME:
                    body[i] = ["Command", ["ConditionalsChangeSkillFlag", 2,
                                           ["Block", [node]], ["Block", []]]]
                    return
            raise AssertionError("finale Wait not found")

        def shrink_extension_lifetime(t):                           # R-m10：延长段退回首尾相接
            for node in C.walk(t):
                if isinstance(node, list) and node and node[0] == "CreateHitArea" \
                        and node[13] == ["SpecifyHitAreaLifetimeDirectly", K.EXT_LIFETIME]:
                    node[13] = ["SpecifyHitAreaLifetimeDirectly", 60]

        for fn in (drop_head, drop_cannon_condition, restore_reference_point, rename_event,
                   drop_engine_condition, regate_finale, shrink_extension_lifetime):
            self.assertTrue(mutated(fn), fn.__name__)

    def test_extension_slots_overlap_and_fit_in_handle(self):
        """R-m10 + 第三轮 D2：延长段两两重叠；整条延长链落在「重炮展开」基础时长（720 帧 = 12 s）以内。

        第二轮判据是「首槽晚于基础时长（360）」＝没有队友续能就一次都不触发；作者第三轮把
        重炮展开提到 12 s，语义反转成「基础时长覆盖整条延长链」。
        """
        gaps = [b - a for a, b in zip(K.EXT_FRAMES, K.EXT_FRAMES[1:])]
        self.assertTrue(all(K.EXT_LIFETIME - g >= 5 for g in gaps), gaps)
        self.assertLessEqual(K.EXT_FRAMES[-1] + K.EXT_LIFETIME,
                             int(K.UNIQUE_META[K.UID_CANNON]["duration"]))
        # 终幕收尾与首个延长槽之间的空档不得超过 15 帧（上一轮是 30）
        self.assertLessEqual(min(K.EXT_FRAMES) - (K.FINALE_FRAME + K.FINALE_LIFETIME), 15)
        # 命中上限 Some(6) + 最小间隔 10 ⇒ 寿命 60→70 不改伤害
        t = tree("2")
        ext = [c for c in K._command_nodes(t, "CreateHitArea")
               if c[13] == ["SpecifyHitAreaLifetimeDirectly", K.EXT_LIFETIME]]
        self.assertEqual(len(ext), len(K.EXT_FRAMES))
        for c in ext:
            self.assertEqual(c[14], ["SpecifyMinHitIntervalDirectly", 10])
            self.assertEqual(c[15], ["Some", [{"min": 6, "max": 6}]])

    def test_big_beam_is_a_single_instance(self):
        """S14（第二轮消闪烁）：大激光整段只有一个光束实例，且任一帧没有同族光柱同屏。"""
        t = tree("2")
        census = K.laser_beam_census(t)
        lll = [e for e in census if e["fam"] == "lll"]
        self.assertEqual(len(lll), 1, census)
        self.assertEqual((lll[0]["label"], lll[0]["on_hitarea"]), (K.FX_BEAM_MAIN, False))
        self.assertEqual((lll[0]["start"], lll[0]["end"]),
                         (K.BIG_BEAM_FRAME, K.EXT_FRAMES[-1] + K.EXT_LIFETIME))
        self.assertEqual(K.beam_overlap_problems(t), [])
        # 挂球 -18 + ["GH",0] + π：与挂 LLL 判定区 CD+π 同角同位（判定区自己也是 -18/GH/td=false）
        fx = [c for c in K._command_nodes(t, "ShowEffect") if c[1] == K.FX_BEAM_MAIN]
        self.assertEqual(len(fx), 1)
        self.assertEqual([fx[0][3], fx[0][6], fx[0][9], fx[0][10], fx[0][11], fx[0][12]],
                         [K.BALL, K.GH, K.PI, True, False, ["None"]])
        self.assertEqual(fx[0][5], ["SpecifyEffectLifetimeDirectly", K.BIG_BEAM_LIFETIME])
        # 提前收炮：根块 1 + 收炮 1 + 延长槽 5
        hides = [c for c in K._command_nodes(t, "HideEffectFromOwner") if c[1] == K.FX_BEAM_MAIN]
        self.assertEqual(len(hides), 2 + len(K.EXT_FRAMES))
        # 终幕不再用激光族贴图；形态 / 寿命 / scale 一并钉死（审查 R2-m4：这是本轮顺带的观感改动，
        # 且 scale 9 > 官方同素材 27 处引用的最大值 2.0 ⇒ 不能无声漂移，改动必须过作者）
        fin = [c for c in K._command_nodes(t, "ShowEffect") if c[1] == K.FX_FINALE]
        self.assertEqual(len(fin), 1)
        self.assertEqual(fin[0][2], ["ResolveByElement", K.CHARGE, 255])
        self.assertEqual(fin[0][3], K.BALL)
        self.assertEqual(fin[0][5], ["SpecifyEffectLifetimeDirectly", K.FINALE_LIFETIME])
        self.assertEqual(fin[0][12], ["Some", [{"min": K.FINALE_FLASH_SCALE, "max": K.FINALE_FLASH_SCALE}]])
        # 第三轮 B：9 → 2.0（charge 是空心光环，parts 矩阵已铺成 750×750；scale 9 = 中心全黑的巨环）
        self.assertEqual((K.FINALE_LIFETIME, K.FINALE_FLASH_SCALE), (30, 2.0))
        self.assertLessEqual(K.FINALE_FLASH_SCALE, K.OFFICIAL_CHARGE_SCALE_MAX)
        self.assertIn(K.FINALE_FLASH_SCALE, K.OFFICIAL_CHARGE_SCALES)

    def test_previous_round_tree_is_flagged(self):
        """负向对照用的是真样本：上一轮（live 1.4.877）的定稿树必须被闪烁门禁判红。"""
        prev = ROOT / K.REVISION_DIR / f"final_{K.CODE}_2.json"
        if not prev.is_file():
            self.skipTest("上一轮定稿树不在本机")
        old = json.loads(prev.read_text(encoding="utf-8"))
        probs = K.beam_overlap_problems(old)
        self.assertTrue(probs, "上一轮形态必须报同族光柱同屏，否则门禁是恒通过的假门禁")
        self.assertTrue(all("lll" in p for p in probs), probs)
        self.assertEqual(len([e for e in K.laser_beam_census(old) if e["fam"] == "lll"]),
                         1 + 1 + len(K.EXT_FRAMES))          # LLL 段 + 终幕 + 5 延长槽

    def test_laser_end_frames_match_packaged_timelines(self):
        """``LASER_END_FRAMES`` 必须等于包内 timeline 实测的 ``end`` 序列长度（常量漂了就抓不到重叠）。"""
        import zlib
        import wf_dsl
        base = (ROOT / "work/character_packs/s7-tekuto/package/roots/common/battle/effect/skill_unique"
                / K.CODE)
        if not base.is_dir():
            self.skipTest("包未构建")
        for fam in K.LASER_FAMS:
            raw = (base / f"laser_{fam}" / f"enemy_shot_laser_{fam}_yellow.timeline.amf3.deflate").read_bytes()
            seqs = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]["sequences"]
            self.assertEqual([s["name"] for s in seqs], ["start", "loop", "end"], fam)
            end = seqs[-1]
            self.assertEqual(K.LASER_END_FRAMES[fam], int(end["end"]) - int(end["begin"]) + 1, fam)

    def test_engine_unique_is_permanent(self):
        """作者第二轮：「引擎启动无时间限制」⇒ c3 永续、c4 上限仍 99（(None) 会被读成 1 层）。"""
        self.assertEqual(K.UNIQUE_META[K.UID_ENGINE]["duration"], "99999999")
        self.assertEqual(K.UNIQUE_META[K.UID_ENGINE]["max"], "99")
        fix = K.REV2_UNIQUE_FIXES[K.UID_ENGINE]
        self.assertEqual((fix["col"], fix["fixed"]), (3, "99999999"))
        plan_row = {e["key"]: e["row"] for e in self.plan["unique_conditions"]["add"]}[K.UID_ENGINE]
        self.assertIn(plan_row[fix["col"]], (fix["plan"], fix["fixed"]))   # 覆盖锚点还在
        # 第三轮 D2：重炮展开 360 → 720（12 s）；上限仍是 1（开关型固有，不读层数）
        self.assertEqual(K.UNIQUE_META[K.UID_CANNON]["duration"], "720")
        self.assertEqual(K.UNIQUE_META[K.UID_CANNON]["max"], "1")
        cfix = K.REV3_UNIQUE_FIXES[K.UID_CANNON]
        self.assertEqual((cfix["col"], cfix["plan"], cfix["fixed"]), (3, "360", "720"))
        cannon_plan = {e["key"]: e["row"] for e in self.plan["unique_conditions"]["add"]}[K.UID_CANNON]
        self.assertIn(cannon_plan[cfix["col"]], (cfix["plan"], cfix["fixed"]))   # 覆盖锚点还在

    def test_rev2_text_rules(self):
        """第二轮文案规则：面板不出现「无上限」类措辞；技能强化条目不写数字与时长。"""
        plan_cas = {r["key"]: r["new"] for r in self.plan["texts"]["custom_ability_string"]["rows"]}
        for key, fix in K.REV2_TEXT_FIXES.items():
            self.assertIn(plan_cas[key], (fix["plan"], fix["fixed"]))      # 覆盖锚点还在
            plan_cas[key] = fix["fixed"]
        for key, text in plan_cas.items():
            for word in ("无上限", "可无限", "可累计", "秒"):
                self.assertNotIn(word, text, key)
            self.assertFalse([c for c in text if c.isdigit()], (key, text))
            self.assertTrue(text.startswith("强化『"), (key, text))
        for text in (K._DESC, *K.POWER_UP_TEXTS.values(), *K.POWER_UP_CUSTOM.values(),
                     *(m["name"] for m in K.UNIQUE_META.values())):
            self.assertNotIn("无上限", text)
        # 审查 R2-m5：潜能 2–6 的 custom_ability_power_up_string 也是「技能强化」条目的面板文案，
        # 同样受规则②约束（此前只有 custom_ability_string 被守住，潜能文案是裸的）
        for key, text in (*K.POWER_UP_TEXTS.items(), *K.POWER_UP_CUSTOM.items()):
            for word in ("无上限", "可无限", "可累计", "无限叠加", "秒"):
                self.assertNotIn(word, text, key)
            self.assertFalse([c for c in text if c.isdigit()], (key, text))

    def test_ability1_switch_row_is_main_slot_only(self):
        """R-m11：536 在能力1（整键 unisonable）⇒ 必须靠前置 202 OwnerIsMain 堵住合击位串扰。"""
        rows, _ = K.revision_ability_rows(self.plan, _design_ability_rows(self.design))
        row = rows[f"{K.CID}1"][1]
        self.assertEqual(row[47], "536")
        self.assertEqual(row[1], rows[f"{K.CID}1"][0][1])            # c1 是整键语义，必须同值
        self.assertEqual(row[6], "202")                              # 前置1 = 仅主位
        self.assertEqual([row[13], row[16], row[17], row[18]], ["2", "600000", "600000", "Yellow"])

    def test_revision_rows_and_sentinels(self):
        """plan 的 cells/edits → 行：126/124 列、块入口哨兵补齐、记录数与 plan 一致。"""
        import wf_client_legality as LG
        leader = K.revision_leader_rows(self.plan)
        self.assertEqual(len(leader), 10)       # 6 − 1(D2 移到能力3) + 4(D3/D4) + 1(第四轮 T1 攻击力行)
        for row in leader:
            self.assertEqual(len(row), 124)
            self.assertEqual(row[0], K.CODE)
            self.assertEqual(LG.client_legality_problems("leader_ability", row)
                             + LG.declared_block_field_problems("leader_ability", row)
                             + LG.ability_element_column_problems("leader_ability", row, K.ELEMENT), [])
        # 瞬发行 c37 / 持续行 c83 的官方哨兵
        for row in leader:
            self.assertEqual(row[37] if row[3] == "0" else row[83], "(None)")
        # 第四轮 T1：作者给了 500% 上限 ⇒ 触发 23 的两行都写 '10'（50% × 10 = 500%）
        limits = sorted(row[32] for row in leader if row[3] == "0" and row[25] == "23")
        self.assertEqual(limits, [K.REV4_TRIGGER_LIMIT] * 2)
        # 审查 R-m8：按层数成长的 during 行 trigger_limit 写 '(None)' = 真无上限（固有 c4 仍是 99）；
        # 第三轮 D3 的两行是 194 ConditionCountUnique 开关门 ⇒ 按官方 8 行先例写 '1'
        self.assertEqual([row[100] for row in leader if row[3] == "1" and row[95] == "134"],
                         ["(None)"] * 5)
        self.assertEqual([row[100] for row in leader if row[3] == "1" and row[95] == "194"], ["1"] * 2)
        # 审查 R-M5：剩下的瞬发触发行仍要带「自身持有重炮展开」前置（188, Myself, ≥1 层）
        gated = [row for row in leader if row[3] == "0" and row[25] == "23"]
        self.assertEqual(len(gated), 2)         # 第四轮 T1：攻击力行与技能伤害行同前置、同触发
        for row in gated:
            self.assertEqual([row[11], row[12], row[14], row[15], row[17]],
                             ["188", "0", "100000", "100000", K.UID_CANNON])

    def test_revision_ability_rows_are_idempotent(self):
        """kit 重跑：已经改过的行再跑一遍结果不变（edits 接受 old 或 new）。"""
        pre = _design_ability_rows(json.loads(DESIGN.read_text(encoding="utf-8")))
        once, _ = K.revision_ability_rows(self.plan, pre)
        twice, _ = K.revision_ability_rows(self.plan, once)
        self.assertEqual(once, twice)
        self.assertEqual(K.revision_record_counts(once, K.revision_leader_rows(self.plan)),
                         {"leader": 10, "abilities": 13})
        self.assertEqual(len(once[f"{K.CID}3"]), 5)      # 第三轮 D2：队长那条 461 搬进来
        self.assertEqual(once[f"{K.CID}1"][1][47], "536")
        self.assertEqual(once[f"{K.CID}3"][1][47], "704")
        self.assertEqual(once[f"{K.CID}2"], K.apply_rev5_ability2(pre[f"{K.CID}2"]))   # 第五轮 T3
        with self.assertRaises(K.KitError):                                # 既不是 old 也不是 new → 报错
            broken = {k: [list(r) for r in v] for k, v in pre.items()}
            broken[f"{K.CID}1"][0][52] = "123456"
            K.revision_ability_rows(self.plan, broken)

    # ------------------------------------------------------------------ 第三轮 D1-D4 / 特效 A、B

    def test_rev3_d1_engine_stack_strengths(self):
        """D1：队长「引擎启动」每层 攻击力 100% / 技能伤害 200%（独立乘区 5% 不动）。"""
        plan_rows = K.plan_leader_rows(self.plan)
        for idx, fix in K.REV3_LEADER_STRENGTH.items():
            for col in fix["cols"]:
                self.assertIn(plan_rows[idx][col], (fix["plan"], fix["fixed"]))   # 覆盖锚点还在
        leader = K.revision_leader_rows(self.plan)
        self.assertEqual([leader[0][107], leader[0][111], leader[0][112]], ["0", "100000", "100000"])
        self.assertEqual([leader[1][107], leader[1][111], leader[1][112]], ["2", "200000", "200000"])
        self.assertEqual([leader[2][107], leader[2][108], leader[2][111]], ["411", "0", "5000"])
        for row in leader[:3]:
            self.assertEqual([row[95], row[96], row[100], row[102]], ["134", "0", "(None)", K.UID_ENGINE])
        # 幂等：已经是新值再跑一遍不变；第三种值必须报错
        mixed = [list(r) for r in leader[:3]] + [list(r) for r in plan_rows[3:]]
        self.assertEqual(K.apply_rev3_leader(mixed), leader)
        broken = [list(r) for r in plan_rows]
        broken[0][111] = "77000"
        with self.assertRaises(K.KitError):
            K.apply_rev3_leader(broken)

    def test_rev3_d2_move_461_row_to_ability3(self):
        """D2：461「赋予重炮展开」整条从队长搬到能力3，列形按 ability 布局逐格重映射。"""
        import wf_client_legality as LG
        src = K.plan_leader_rows(self.plan)[K.REV3_LEADER_MOVED]
        rows, trace = K.revision_ability_rows(self.plan, _design_ability_rows(self.design))
        moved = rows[K.REV3_MOVED_ABILITY_KEY][-1]
        self.assertEqual(len(moved), 126)
        # 头部按 ability 语义；c1/c2 与同键其它记录一致（c1 是整键语义）
        self.assertEqual(moved[0], K.CODE + "_3")
        self.assertEqual([moved[1], moved[2]], [rows[K.REV3_MOVED_ABILITY_KEY][0][1],
                                                rows[K.REV3_MOVED_ABILITY_KEY][0][2]])
        self.assertEqual([moved[3], moved[5]], ["0", "0"])
        # 业务列逐格 = 队长源行（列映射）；c17→c19 前置 uid 是第四轮 T2 唯一改掉的一格
        for lcol, acol in K.REV3_MOVE_COLMAP.items():
            if acol == K.REV4_MOVED_PRE_UID_COL:
                continue
            self.assertEqual(moved[acol], src[lcol], "leader c%d -> ability c%d" % (lcol, acol))
        for lcol, acol in K.REV3_MOVE_SENTINEL_COLS.items():
            self.assertEqual(moved[acol], src[lcol], "sentinel c%d -> c%d" % (lcol, acol))
        # 语义抽查：触发 = 除自身任一·雷 技能发动；内容 = 461 给自身「重炮展开」1 层；
        # 前置2 = 自身持有「引擎启动」（第四轮 T2：从自持环的「重炮展开」换成「引擎启动」）
        self.assertEqual([moved[27], moved[28], moved[29], moved[30], moved[31]],
                         ["23", "4", "Yellow", "100000", "100000"])
        self.assertEqual([moved[47], moved[48], moved[68], moved[59], moved[74], moved[75]],
                         ["461", "0", K.UID_CANNON, "100000", "1", "0"])
        self.assertEqual([moved[13], moved[14], moved[16], moved[17], moved[19]],
                         ["188", "0", "100000", "100000", K.UID_ENGINE])
        self.assertEqual([moved[6], moved[9], moved[10], moved[11]], ["2", "600000", "600000", "Yellow"])
        self.assertEqual(LG.client_legality_problems("ability", moved)
                         + LG.declared_block_field_problems("ability", moved)
                         + LG.ability_element_column_problems("ability", moved, K.ELEMENT), [])
        self.assertEqual(sorted(LG.required_client_capabilities("ability", moved)), [])
        self.assertIn({"key": K.REV3_MOVED_ABILITY_KEY, "record": 4, "op": "add", "req": "D2",
                       "from": "leader#%d" % K.REV3_LEADER_MOVED, "colmap": "REV3_MOVE_COLMAP"}, trace)
        # 队长侧不再有任何 461 / c66
        leader = K.revision_leader_rows(self.plan)
        self.assertEqual([row for row in leader if row[45] == "461" or row[66]], [])
        # 幂等：拿「已经搬过」的包内行再跑一遍，结果仍是 5 条、不会重复 append
        again, _ = K.revision_ability_rows(self.plan, {k: [list(r) for r in v] for k, v in rows.items()})
        self.assertEqual(again, rows)
        self.assertEqual(len(again[K.REV3_MOVED_ABILITY_KEY]), 5)
        # 防线仍在：plan 若哪天自己也加了一条 461/重炮展开，重复搬运必须报错
        with self.assertRaises(K.KitError):
            K._rev3_move_guard([moved])

    def test_rev3_d3_d4_new_leader_rows(self):
        """D3：持有「重炮展开」→ 除自身外雷属性角色 充能/上限 +50%；D4：每层引擎启动 → 自身 +5%。"""
        import wf_client_legality as LG
        leader = K.revision_leader_rows(self.plan)
        want = {
            # 位置 → (during kind, uid, trigger_limit, content kind, target, target 组, 强度)
            3: ("134", K.UID_ENGINE, "(None)", "3", "0", "", "5000"),
            4: ("134", K.UID_ENGINE, "(None)", "124", "0", "", "5000"),
            5: ("194", K.UID_CANNON, "1", "3", "1", "Yellow", "50000"),
            6: ("194", K.UID_CANNON, "1", "124", "1", "Yellow", "50000"),
        }
        for pos, spec in want.items():
            row = leader[pos]
            self.assertEqual((row[95], row[102], row[100], row[107], row[108], row[109], row[111]), spec, pos)
            self.assertEqual(row[112], row[111])                 # 低级/满级拉平（固定文案口径）
            self.assertEqual([row[3], row[96], row[106], row[83]], ["1", "0", "false", "(None)"])
            self.assertEqual([row[4], row[7], row[8], row[9]], ["2", "600000", "600000", "Yellow"])
            self.assertEqual(LG.client_legality_problems("leader_ability", row)
                             + LG.declared_block_field_problems("leader_ability", row)
                             + LG.ability_element_column_problems("leader_ability", row, K.ELEMENT), [])
        # 技能槽族在持续侧只有 3 / 124（瞬发 211 无按层倍增通道）⇒ D4 的「技能槽」取 3
        self.assertEqual(sorted({leader[p][107] for p in want}), ["124", "3"])
        # 面板分组：同一触发的行必须相邻（134 五行 + 194 两行 + 三条瞬发）
        self.assertEqual([row[95] for row in leader], ["134"] * 5 + ["194"] * 2 + [""] * 3)
        self.assertLessEqual(len(leader), 10)                    # 一键最多 10 条

    # ------------------------------------------------------------------ 第四轮 T1 / T2

    def test_rev4_t1_attack_row_is_a_twin_of_the_skill_damage_row(self):
        """T1：队长瞬发多出一条「自身攻击力 +50%」，与技能伤害行逐格相同（只差 content kind）。"""
        import wf_client_legality as LG
        leader = K.revision_leader_rows(self.plan)
        self.assertEqual(len(leader), 10)
        attack, skill = leader[7], leader[8]
        self.assertEqual(attack[45], K.REV4_ATTACK_KIND)         # 32 AttackPoint
        self.assertEqual(skill[45], K.REV4_SKILL_KIND)           # 34 SkillDamage
        # 「同触发」不是口头承诺：两行逐格只差 content kind 那一列
        self.assertEqual([i for i, (a, b) in enumerate(zip(attack, skill)) if a != b], [45])
        for row in (attack, skill):
            self.assertEqual([row[3], row[25], row[26], row[27]], ["0", "23", "4", "Yellow"])
            self.assertEqual([row[46], row[49], row[50]], ["0", "50000", "50000"])
            self.assertEqual(row[32], K.REV4_TRIGGER_LIMIT)      # 触发次数上限
            self.assertEqual(int(row[32]) * int(row[49]), 500000)  # 50% × 10 = 500%（作者要的上限）
            self.assertEqual(LG.client_legality_problems("leader_ability", row)
                             + LG.declared_block_field_problems("leader_ability", row)
                             + LG.ability_element_column_problems("leader_ability", row, K.ELEMENT), [])
        # 原值断言 + 幂等：plan 里这一列是 '(None)'；已经是 '10' 再跑一遍不变；第三种值必须报错
        plan_rows = K.plan_leader_rows(self.plan)
        self.assertEqual(plan_rows[K.REV4_LEADER_SOURCE][32], K.REV4_LIMIT_PLAN)
        already = [list(r) for r in plan_rows]
        already[K.REV4_LEADER_SOURCE][32] = K.REV4_TRIGGER_LIMIT
        self.assertEqual(K.apply_rev3_leader(already), leader)
        broken = [list(r) for r in plan_rows]
        broken[K.REV4_LEADER_SOURCE][32] = "7"
        with self.assertRaises(K.KitError):
            K.apply_rev3_leader(broken)
        # 源行认错了也要报错（plan 哪天换了行序）
        wrong = [list(r) for r in plan_rows]
        wrong[K.REV4_LEADER_SOURCE][45] = "35"
        with self.assertRaises(K.KitError):
            K.apply_rev3_leader(wrong)

    def test_rev4_t1_panel_writes_out_the_cap(self):
        """面板上限 = 强度 × 触发次数：客户端对 Common 家族（攻击力/技能伤害）走
        ``stringfyCommonCharacterContent`` 末尾的 ``addMaxStrengthPercent``，
        渲染 ``ability_description_instant_max_strength``「[最大 ::max_strength::&nbsp;]」
        ⇒ 50% × 10 = 「[最大 + 500 % ]」。**不是**「（上限 N 次）」那条通道
        （``addTriggerLimitPrefix`` 在 Common 支上没被套用；取证
        ``revision4-20260917/tekuto/review/panel_cap.json``）。
        """
        import wf_describe
        leader = K.revision_leader_rows(self.plan)
        lines = wf_describe.describe_rows(leader, "leader_ability")
        capped = [line for line in lines if "限10次" in line]
        self.assertEqual(len(capped), 2, lines)
        self.assertTrue(any("攻击力 50%" in line for line in capped), capped)
        self.assertTrue(any("技能伤害 50%" in line for line in capped), capped)
        # 面板算式本身：两行都必须 强度 × 次数 = 500%（面板打印的是这个乘积，不是次数）
        for row in leader:
            if row[3] == "0" and row[25] == "23" and row[26] == "4" and row[45] in ("32", "34"):
                self.assertEqual(row[32], K.REV4_TRIGGER_LIMIT, row)
                self.assertEqual(row[49], row[50], row)      # 低级/满级拉平，面板只有一个数
                self.assertEqual(int(row[32]) * int(row[49]), 500_000, row)
        # 文案规则①：没有上限的成长写到效果为止 ⇒ 面板不许出现「无上限」类字样
        self.assertEqual([line for line in lines
                          if any(w in line for w in ("无上限", "可无限", "可累计"))], [])

    # ------------------------------------------------------------------ 第五轮 T3

    def test_rev5_t3_ability2_grows_with_engine_stacks_uncapped(self):
        """T3：能力2 = 两条 during-134 行，按「引擎启动」层数给自身攻击力/技能伤害各 50%，无上限。"""
        import wf_client_legality as LG
        import wf_describe
        pre = _design_ability_rows(json.loads(DESIGN.read_text(encoding="utf-8")))
        rows, _ = K.revision_ability_rows(self.plan, pre)
        got = rows[K.REV5_ABILITY_KEY]
        self.assertEqual(len(got), 2)
        for row in got:
            self.assertEqual(len(row), 126)
            self.assertEqual(row[0], f"{K.CODE}_2")
            self.assertEqual(row[5], "1")                       # 持续行
            self.assertEqual(row[85], "(None)")                 # 持续行的块入口哨兵在 c85
            self.assertEqual(row[39], "")                       # …不是瞬发行的 c39
            self.assertEqual(row[97], "134")                    # 按固有层数成长（194 只数实例个数）
            self.assertEqual(row[98], "0")                      # 134 的 during puller
            self.assertEqual([row[100], row[101]], ["100000", "100000"])
            self.assertEqual(row[102], K.REV5_NO_CAP)           # 不设置上限
            self.assertEqual(row[104], K.UID_ENGINE)
            self.assertEqual(row[110], "0")                     # target 0 = 自身
            self.assertEqual(row[111], "")                      # 只给自身 ⇒ 不带元素组
            self.assertEqual([row[113], row[114]], [K.REV5_STRENGTH] * 2)
            self.assertEqual(row[27], "")                       # 瞬发块整块空
            self.assertEqual(row[47], "")
            self.assertEqual(LG.client_legality_problems("ability", row)
                             + LG.declared_block_field_problems("ability", row)
                             + LG.ability_element_column_problems("ability", row, K.ELEMENT), [])
            self.assertEqual(sorted(LG.required_client_capabilities("ability", row)), [])
        self.assertEqual([row[109] for row in got], [K.REV5_ATTACK_KIND, K.REV5_SKILL_KIND])
        self.assertEqual([row[1] for row in got], [pre[K.REV5_ABILITY_KEY][0][1]] * 2)
        self.assertEqual([row[2] for row in got], [pre[K.REV5_ABILITY_KEY][0][2]] * 2)
        # 面板：按作者文案规则①，成长写到效果为止、后面什么都不跟（没有「上限」「最大」）
        lines = [wf_describe.describe_line(row, "ability") for row in got]
        self.assertEqual(lines, [spec["desc_expected"] for spec in K.REV5_ROWS])
        for line in lines:
            self.assertNotIn("上限", line)
            self.assertNotIn("最大", line)
            self.assertNotIn("无上限", line)

    def test_rev5_t3_replaces_the_capped_instant_rows(self):
        """被换掉的必须正是「技能发动限3次 → 攻击 50/100、技伤 25/50」那两条瞬发行。"""
        pre = _design_ability_rows(json.loads(DESIGN.read_text(encoding="utf-8")))
        before = pre[K.REV5_ABILITY_KEY]
        self.assertEqual(tuple((r[27], r[34], r[47], r[51], r[52]) for r in before),
                         K.REV5_REPLACED_SHAPE)
        self.assertEqual(K.apply_rev5_ability2(K.apply_rev5_ability2(before)),
                         K.apply_rev5_ability2(before))          # 幂等
        for broken, why in (
                ([before[0]], "只剩一条"),
                ([list(before[0]), [*before[1][:34], "9", *before[1][35:]]], "次数上限被动过"),
                ([[*before[0][:1], "false", *before[0][2:]], list(before[1])], "整键 c1 不自洽")):
            with self.assertRaises(K.KitError, msg=why):
                K.apply_rev5_ability2([list(r) for r in broken])

    def test_accumulation_cap_guard(self):
        """被 during-134 数层数的固有，叠层上限必须 >1；写 1 或 (None) 会让整条词条静默失效。"""
        row = K.revision_row({"0": f"{K.CODE}_2", "3": "0", "5": "1", "97": "134",
                              "104": K.UID_ENGINE, "109": "0"}, "ability")
        leader = [K.revision_row({"0": K.CODE, "3": "1", "95": "134", "102": K.UID_CANNON},
                                 "leader_ability")]
        ok = {K.UID_ENGINE: ["", "", "", "99999999", "99"], K.UID_CANNON: ["", "", "", "720", "9"]}
        self.assertEqual(K.accumulation_cap_problems({f"{K.CID}2": [row]}, leader, ok), [])
        for bad in ("1", "(None)", "", "99.5"):
            caps = {K.UID_ENGINE: ["", "", "", "99999999", bad], K.UID_CANNON: ok[K.UID_CANNON]}
            probs = K.accumulation_cap_problems({f"{K.CID}2": [row]}, leader, caps)
            self.assertEqual(len(probs), 1, bad)
            self.assertIn(K.UID_ENGINE, probs[0])
        # 只查被 134 数层数的固有：194 / 瞬发行不该被牵连
        instant = K.revision_row({"0": f"{K.CODE}_2", "3": "0", "5": "0", "27": "23", "47": "32"}, "ability")
        self.assertEqual(K.accumulation_cap_problems(
            {f"{K.CID}2": [instant]}, [], {K.UID_ENGINE: ["", "", "", "1", "1"]}), [])
        # 本 kit 不写的固有（不在 unique_rows 里）跳过，不误伤
        self.assertEqual(K.accumulation_cap_problems({f"{K.CID}2": [row]}, [], {}), [])

    def test_ability_mode_column_is_c5_not_c3(self):
        """哨兵补齐要按 ability 的 c5（c3 是 awake_kind）——第五轮之前这里读错列也看不出来。"""
        self.assertEqual(K.MODE_COL, {"leader_ability": 3, "ability": 5})
        during = K.revision_row({"0": f"{K.CODE}_2", "3": "0", "5": "1", "97": "134"}, "ability")
        self.assertEqual((during[39], during[85]), ("", "(None)"))
        instant = K.revision_row({"0": f"{K.CODE}_2", "3": "0", "5": "0", "27": "23"}, "ability")
        self.assertEqual((instant[39], instant[85], instant[34]), ("(None)", "", "(None)"))
        # 觉醒词条（c3='1'）不该被当成持续行
        awake = K.revision_row({"0": f"{K.CODE}_2", "3": "1", "5": "0", "27": "23"}, "ability")
        self.assertEqual((awake[39], awake[85]), ("(None)", ""))
        # leader 仍按 c3
        lead_during = K.revision_row({"0": K.CODE, "3": "1", "95": "134"}, "leader_ability")
        self.assertEqual((lead_during[37], lead_during[83]), ("", "(None)"))

    def test_rev4_t2_ability3_461_precondition_is_engine(self):
        """T2：能力3 的 461「赋予重炮展开」前置 = 自身持有「引擎启动」，不再是自持环的「重炮展开」。"""
        rows, _ = K.revision_ability_rows(self.plan, _design_ability_rows(self.design))
        a3 = rows[K.REV3_MOVED_ABILITY_KEY]
        moved = [r for r in a3 if r[47] == "461" and r[68] == K.UID_CANNON]
        self.assertEqual(len(moved), 1)
        row = moved[0]
        # 前置列形与官方 ability 侧 188 三行逐格相同：['188','0','','100000','100000',''] + uid
        self.assertEqual(row[13:20], ["188", "0", "", "100000", "100000", "", K.UID_ENGINE])
        # 触发仍是「除自身外任一雷属性角色发动技能」；效果仍是赋予自身「重炮展开」1 层
        self.assertEqual(row[27:32], ["23", "4", "Yellow", "100000", "100000"])
        self.assertEqual([row[47], row[48], row[68], row[74]], ["461", "0", K.UID_CANNON, "1"])
        # 自持环已断：包内不再有「要重炮展开才能给重炮展开」的记录
        self.assertEqual([r for r in a3 if r[47] == "461" and r[68] == K.UID_CANNON
                          and r[19] == K.UID_CANNON], [])
        # 「引擎启动」永续且技能自带 1 层 ⇒ 首次发动技能后这条前置恒成立
        self.assertGreaterEqual(int(K.UNIQUE_META[K.UID_ENGINE]["duration"]), 99999)
        # 原值断言：plan 的 leader c17 必须仍是「重炮展开」，否则覆盖锚点已失效
        self.assertEqual(K.plan_leader_rows(self.plan)[K.REV3_LEADER_MOVED][17], K.REV4_MOVED_PRE_UID_PLAN)

    def test_rev3_charge_scales_are_official(self):
        """特效 B：charge 系 scale 收回官方同素材档位（1.0/1.5/2.0），并与 plan 原值可追溯。

        审查 R3-m5：第三段 charge_core 由 2.0 降到 1.5，把 2.0 留给终幕独占 ——
        否则终幕与第三段同素材、同 subject/锚点、同大小、只隔 2 帧，在屏幕上读不出来。
        """
        self.assertEqual(K.charge_scale_problems(self.plan), [])
        self.assertEqual([st[5] for st in K.STAGES], [None, 1.0, 1.5, 1.5])
        self.assertEqual(K.FINALE_FLASH_SCALE, 2.0)
        # 终幕必须严格大于所有 charge_core（负向对照：把第三段调回 2.0 这条必红）
        self.assertTrue(all(st[5] < K.FINALE_FLASH_SCALE for st in K.STAGES if st[5] is not None))
        plan_ha = {h["id"]: h for h in self.plan["skill_dsl"]["hitareas"]}
        for name, fix in K.REV3_CHARGE_SCALE_FIXES.items():
            if name.startswith("charge_core:"):
                self.assertIn(plan_ha["HA_" + name.split(":", 1)[1]]["charge_core_scale"],
                              (fix["plan"], fix["fixed"]))
        t = tree("2")
        got = [c[12] for c in K._command_nodes(t, "ShowEffect")
               if c[1] == "charge_core" and c[2][0] == "ResolveByElement"]
        self.assertEqual(got, [["Some", [{"min": sc, "max": sc}]] for sc in (1.0, 1.5, 1.5)])
        # 寿命收到官方同素材区间上沿，并与终幕拉开空档（O-R3-6 一并收口）
        self.assertEqual(K.CHARGE_CORE_LIFETIME, 40)
        self.assertLessEqual(K.CHARGE_CORE_LIFETIME, K.OFFICIAL_CHARGE_LIFETIME_MAX)
        lives = [c[5] for c in K._command_nodes(t, "ShowEffect") if c[1] == "charge_core"]
        self.assertEqual(lives, [["SpecifyEffectLifetimeDirectly", 40]] * 3)
        self.assertGreaterEqual(K.FINALE_FRAME - (K.STAGES[-1][1] + K.CHARGE_CORE_LIFETIME), 15)

    def test_rev3_cooldown_glow_is_reachable(self):
        """审查 R3-M1：D2 的 720 帧让 f362 的收炮 else 分支恒不执行，余晖与 laser_200px_end 变死码。

        修法＝在大激光真正结束的 f682 补一条**条件相反**的门：
        f362 走 else（重炮展开已没了 → 提前收炮），f682 走 then（还在 → 打完才收），
        任何一次发动恰好播一次余晖。
        """
        self.assertEqual(K.BEAM_END_FRAME, K.BIG_BEAM_FRAME + K.BIG_BEAM_LIFETIME)
        self.assertEqual(K.BEAM_END_FRAME, 682)
        # f682 必须仍在「重炮展开」窗口内，否则两条门会同时关上 ⇒ 一次都不播
        self.assertLess(K.BEAM_END_FRAME, int(K.UNIQUE_META[K.UID_CANNON]["duration"]))
        t = tree("2")
        glow = K._command_nodes(t, "ShowEffect", "cannon_cooldown")
        self.assertEqual(len(glow), 2)
        self.assertEqual(glow[0][2], glow[1][2])                  # 同一素材
        self.assertEqual(glow[0][12], glow[1][12])                # 同一 scale
        self.assertTrue(str(glow[0][2][1]).endswith("laser_200px_end"))
        self.assertEqual(K.cooldown_width_problems(t), [])
        # 两条门的分支恰好互补：一条 then 空 / 一条 else 空
        gates = K._command_nodes(t, "ConditionalsConditionAccumulationNumber")
        self.assertEqual(len(gates), len(K.EXT_FRAMES) + 2)
        empty_then = [g for g in gates if not g[3][1]]
        beam_end = [g for g in gates if g[3][1] and not g[4][1]]
        self.assertEqual(len(empty_then), 1)                      # f362：then 空、else 收炮
        self.assertEqual(len(beam_end), 1)                        # f682：then 收炮、else 空
        self.assertEqual([n[1][:2] for n in beam_end[0][3][1]], [["ShowEffect", "cannon_cooldown"]])

    def test_rev3_finale_is_distinguishable(self):
        """审查 R3-m5：终幕必须是全树唯一的最大档 charge，且与第三段之间有全黑空档。"""
        t = tree("2")
        ring = K._command_nodes(t, "ShowEffect", K.FX_FINALE)
        self.assertEqual(len(ring), 1)
        self.assertEqual(ring[0][12], ["Some", [{"min": 2.0, "max": 2.0}]])
        cores = K._command_nodes(t, "ShowEffect", "charge_core")
        self.assertEqual(len(cores), 3)
        self.assertTrue(all(c[12][1][0]["max"] < 2.0 for c in cores))
        # 第三段 f270+40=310，终幕 f332 ⇒ 22 帧空档
        self.assertEqual(K.FINALE_FRAME - (K.STAGES[-1][1] + K.CHARGE_CORE_LIFETIME), 22)

    def test_rev3_damage_census_matches_plan(self):
        """审查 R3-M1：D2 的 12 s 让 5 个延长槽默认全触发 —— 段数与倍率必须由树算出来。

        自校验：census 的「无条件」那一堆逐值等于 plan 声明的总倍率（口径相同）；
        被「重炮展开」门包住的那一堆 = 5 × plan 的 extension_slot_lv2_max。
        """
        for lv, want_mult, want_stack in (("2", 65.0, 15.0), ("1", 52.0, 12.0)):
            cen = K.damage_census(tree(lv))
            self.assertEqual(cen["ungated"]["mult_max"], want_mult, lv)
            self.assertEqual(cen["ungated"]["per_stack_max"], want_stack, lv)
            self.assertEqual(cen["ungated"]["hits"], 30, lv)
            self.assertEqual(cen["gated_by_cannon"]["hits"], 30, lv)
            self.assertEqual(cen["gate_frames"], list(K.EXT_FRAMES), lv)
            # D2 的直接后果：门在 [0,720) 内恒开 ⇒ 不需要队友续能，延长链每次都全打
            self.assertTrue(cen["gate_always_open_without_ally"], lv)
            # 同一件事的另一面：f362 的收炮 else 分支恒不执行
            self.assertFalse(cen["cooldown_branch_reachable"], lv)
        cen2 = K.damage_census(tree("2"))
        self.assertEqual(cen2["gated_by_cannon"]["mult_max"], 69.0)      # 5 × 13.8
        self.assertEqual(cen2["if_gate_open"]["mult_max"], 134.0)        # 65.0 + 69.0
        self.assertEqual(cen2["if_gate_open"]["per_stack_max"], 31.5)    # 15.0 + 16.5
        self.assertEqual(cen2["if_gate_open"]["hits"], 60)

    def test_hitarea_max_hits_semantics(self):
        """段数算法本身：最小命中间隔 → floor((L-1)/iv)+1，再被 Some(cap) 钳。"""
        self.assertEqual(K.hitarea_max_hits(60, ["SpecifyMinHitIntervalDirectly", 10], 6), 6)
        self.assertEqual(K.hitarea_max_hits(70, ["SpecifyMinHitIntervalDirectly", 10], 6), 6)
        self.assertEqual(K.hitarea_max_hits(70, ["SpecifyMinHitIntervalDirectly", 10], None), 7)
        self.assertEqual(K.hitarea_max_hits(30, ["CalculatedUsingMaxNumOfHits", 1], 1), 1)
        self.assertEqual(K.hitarea_max_hits(15, ["CalculatedUsingMaxNumOfHits", 4], None), 4)
        with self.assertRaises(K.KitError):
            K.hitarea_max_hits(60, ["NoSuchInterval", 1], 1)

    def test_rev3_lll_head_patch(self):
        """特效 A：官方母本 laser_lll 的坏块被同族供体块整体替换；幂等；越段断言在。

        审查 R3-m4：修复逻辑已从未跟踪的 ``work/**/fx/lll_head_patch.py`` 内联进 kit，
        本用例只依赖 kit 本身；母本原件不在本机时 **skip**（以前是 import 就 error）。
        """
        orig = ROOT / K.REV3_FX_DIR / "out/enemy_shot_laser_lll_yellow.parts.ORIGINAL.amf3.deflate"
        if not orig.is_file():
            self.skipTest("母本原件不在本机")
        raw = C.amf_parse(orig.read_bytes())
        self.assertFalse(K.lll_is_patched(raw))                   # 负向对照：母本必须是红的
        fixed, report = K.lll_repair_tree(raw)
        self.assertEqual(report["status"], "patched")
        self.assertTrue(K.lll_is_patched(fixed))
        self.assertEqual(K._lll_block_images(fixed, K.LLL_BAD_START),
                         K._lll_block_images(fixed, K.LLL_DEFAULT_DONOR))
        again, report2 = K.lll_repair_tree(fixed)
        self.assertEqual(report2["status"], "already-patched")
        self.assertEqual(again, fixed)
        # 包内落盘的就是修好的那份
        pkg = ROOT / "work/character_packs/s7-tekuto/package/roots/common" / K.REV3_LLL_PARTS
        if pkg.is_file():
            self.assertTrue(K.lll_is_patched(C.amf_parse(pkg.read_bytes())))

    def test_rev3_lll_patch_needs_no_untracked_file(self):
        """审查 R3-m4：kit 不再 import work/ 里的取证副本；副本在本机时逐常量比对，不在也不报错。"""
        src = (ROOT / "mod-tools/wf_seasonal7_kit_tekuto.py").read_text(encoding="utf-8")
        self.assertNotIn("importlib.import_module", src)     # 不再从 work/ 动态 import
        self.assertNotIn("sys.path.insert", src)
        self.assertIn("def lll_repair_tree(", src)           # 纯函数就在 kit 里
        self.assertIn("def lll_is_patched(", src)
        drift = K.lll_patch_forensic_drift(ROOT)
        self.assertEqual(drift["drift"], [])            # 副本缺失时 drift=[] 且 present=False
        if drift["present"]:
            self.assertTrue((ROOT / K.REV3_FX_DIR / "lll_head_patch.py").is_file())

    def test_design_tree_fix_states(self):
        raw = self.design["skills"]["tree_plan_2"]["composed_tree"]
        node = K._command_nodes(raw, "ShowEffect", "cannon_cooldown")
        self.assertEqual(len(node), 1)
        # 原设计值 3.8 → applied；已同步 7.6 → already-in-design；其他值 → 报错
        fixed, rep = K.apply_design_tree_fixes(raw)
        self.assertIn(rep[0]["state"], ("applied", "already-in-design"))
        self.assertEqual(K._command_nodes(fixed, "ShowEffect", "cannon_cooldown")[0][12],
                         ["Some", [{"min": 7.6, "max": 7.6}]])
        synced = K.apply_design_tree_fixes(fixed)[1]
        self.assertEqual(synced[0]["state"], "already-in-design")
        other = K._command_nodes(fixed, "ShowEffect", "cannon_cooldown")[0]
        other[12] = ["Some", [{"min": 5, "max": 5}]]
        with self.assertRaises(K.KitError):
            K.apply_design_tree_fixes(fixed)

    def test_amf_roundtrip(self):
        t = tree("2")
        self.assertEqual(C.amf_parse(C.amf_bytes(t)), t)

    def test_unique_rows_match_plan(self):
        """两个固有状态：上限列必须是整数（(None) = 上限 1，会把 during 134 与 vlv 成长全弄死）。"""
        rows = {e["key"]: e["row"] for e in self.plan["unique_conditions"]["add"]}
        self.assertEqual(sorted(rows), [K.UID_ENGINE, K.UID_CANNON])
        self.assertEqual(rows[K.UID_ENGINE][4], "99")
        self.assertEqual(rows[K.UID_CANNON][3:5], ["360", "1"])
        for uid, row in rows.items():
            self.assertEqual(len(row), 15)
            self.assertTrue(row[4].isdigit())
            self.assertEqual(row[2] + ".png", K.UNIQUE_ICON[uid])

    def test_texts_are_revised(self):
        row = self.design["text"]["character_text_row"]
        self.assertEqual(K.TEXTS["profile"], row[2])
        self.assertEqual((K.TEXTS["skill1"], K.TEXTS["skill2"]), (row[4], row[6]))
        self.assertEqual(K.TEXTS["cv"], row[11])
        # 技能说明：设计稿仍是改版前的长文，TEXTS/常量是改版短文，plan 的 old/new 对得上
        self.assertEqual([row[5], row[7]], [K._DESIGN_DESC, K._DESIGN_DESC])
        # S18（2026-09-21 取消后摇）：落表文案 = plan 的 _DESC + 「不再进入硬直」一句；
        # 2026-09-27 平衡第二批（第一批输出 + 第二批覆盖）：技能倍率的层数贡献封顶 ENGINE_CAP=10 ⇒
        # 「威力随其层数提升」后面写出「（最多10层）」（wf_balance_20260927b_tekuto 同一句）；
        # 平衡第三批（wf_balance_20260927c_tekuto）：担任队长且雷共鸣时旗号 3 分支不封顶，但技能说明只写本体
        # （主会话 2026-09-27 口径：强化后效果只写在强化条目 CHANGE_SKILL_LEADER_TEXT）⇒ 落表文案 == 第二批。
        self.assertEqual((K.TEXTS["desc1"], K.TEXTS["desc2"]), (K._DESC_BALANCE_C, K._DESC_BALANCE_C))
        self.assertEqual(K._DESC_NO_ENDLAG, K._DESC + K.REV7_NO_ENDLAG_SUFFIX)
        self.assertEqual(K._DESC_BALANCE_B, K._DESC_NO_ENDLAG.replace(
            K.BALANCE_B_DESC_ANCHOR, K.BALANCE_B_DESC_ANCHOR + K.BALANCE_B_DESC_CAP))
        self.assertEqual(K.BALANCE_B_DESC_CAP, f"（最多{K.ENGINE_CAP}层）")
        self.assertEqual(K._DESC_BALANCE_C, K._DESC_BALANCE_B)
        self.assertFalse(hasattr(K, "BALANCE_C_DESC_CAP"))
        for mark in ("不受此限", "担任队长", "强化后"):
            self.assertNotIn(mark, K._DESC_BALANCE_C)
        self.assertTrue(K.CHANGE_SKILL_LEADER_TEXT.startswith(f"强化『{K.TEXTS['skill1']}』："))
        desc = self.plan["texts"]["action_skill_desc"]
        self.assertEqual((desc["old"], desc["r1_new"], desc["new"]), (K._DESIGN_DESC, K._R1_DESC, K._DESC))
        self.assertLess(len(K._DESC), len(K._DESIGN_DESC))
        # 审查 R-M3：不许再出现与行为不符的「刷新…持续时间」措辞
        self.assertNotIn("刷新", K._DESC)
        self.assertIn("替换", K._DESC)
        # 禁恒真/HP 文案（记忆卡 wf-no-hplow-text-discipline）
        self.assertNotIn("生命值", K._DESC)

    def test_power_up_text_matches_alv_landing(self):
        """审查 R-M1：槽2 的 alv2 只落在雷达 Sector 的半径/角度上 ⇒ 潜能文案不能写「伤害强化」。"""
        self.assertNotIn(K.CHANGE_SKILL2_KEY, K.POWER_UP_SOURCES)
        text = K.POWER_UP_CUSTOM[K.CHANGE_SKILL2_KEY]
        self.assertNotIn("伤害", text)
        self.assertIn("范围", text)
        t = tree("2")
        alv2 = [d for d in _slv_terms(t) if "alv2_min" in d]
        self.assertEqual(len(alv2), 2)                                  # 半径 + 角度，别处一律没有 alv2
        radar = [c for c in K._command_nodes(t, "CreateHitArea") if K._tag(c[9]) == "Sector"]
        self.assertEqual(len(radar), 1)
        self.assertEqual([radar[0][9][1][0], radar[0][9][2][0]], alv2)
        # 两端都非零：潜能 1 就要有加成（AbilityPowerValue.resolve 在潜能==1 时返回 alv_min）
        for term in alv2:
            self.assertGreater(term["alv2_min"], 0)
            self.assertGreater(term["alv2_max"], term["alv2_min"])
        # R-M2：基础半径必须高于 live 改版前的 400
        self.assertGreater(alv2[0]["min"], 400)

    def test_spec_merge_extra_keys(self):
        spec = S.get_spec("tekuto")
        # 平衡第三批：旗号 3 开关行（能力1 kind 705）的文案键也由本包认领；它没有潜能文案（官方 705 行同样没有）
        self.assertEqual(spec.extra_keys[K.CAS], (K.CHANGE_SKILL_KEY, K.CHANGE_SKILL2_KEY, K.CHANGE_SKILL_LEADER_KEY))
        self.assertEqual(spec.extra_keys[K.CAPS], (K.CHANGE_SKILL_KEY, K.CHANGE_SKILL2_KEY))
        self.assertEqual(spec.extra_keys[K.SWITCHED], (K.VOICE_READY_KEY,))
        self.assertEqual(spec.extra_keys[K.UNIQUE], (K.UID_ENGINE, K.UID_CANNON))
        self.assertEqual(spec.required_capabilities, ())

    def test_icons_are_48_and_use_official_frame_alpha(self):
        from PIL import Image
        frame = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        for x in range(4, 44):
            for y in range(4, 44):
                frame.putpixel((x, y), (255, 255, 255, 255))
        for uid, painter in K.ICON_PAINTERS.items():
            icon = painter(frame)
            self.assertEqual(icon.size, (48, 48))
            self.assertEqual(icon.getchannel("A").tobytes(), frame.getchannel("A").tobytes(), uid)
            self.assertNotEqual(icon.getchannel("R").tobytes(), frame.getchannel("R").tobytes(), uid)
        # 外框 donor 不是 48×48 时必须报错（图标位取图按 48×48 走）
        class _Ctx:
            png_open = staticmethod(C.png_open)

            def official_read(self, logical):
                return png_bytes((32, 32), (0, 0, 0, 255), store=False)

        with self.assertRaises(K.KitError):
            K.install_unique_icons(_Ctx())


class PureHelpersTest(unittest.TestCase):
    def test_strict_diff_types(self):
        self.assertTrue(K.strict_diff([1], [1.0]))
        self.assertTrue(K.strict_diff([True], [1]))
        self.assertEqual(K.strict_diff({"a": [1.5]}, {"a": [1.5]}), [])

    def test_cooldown_width_pairing(self):
        t = tree("2")
        self.assertEqual(K.cooldown_width_problems(t), [])
        node = K._command_nodes(t, "ShowEffect", "cannon_cooldown")[0]
        self.assertEqual(node[12], ["Some", [{"min": 7.6, "max": 7.6}]])
        node[12] = ["Some", [{"min": 3.8, "max": 3.8}]]           # 设计原值：≈380px，只有 LLL 一半
        self.assertTrue(K.cooldown_width_problems(t))

    def test_donothing_detected(self):
        t = tree("1")
        # 审查 R-m6 之后树里没有 ConditionalsChangeSkillFlag，用延长槽/收炮的条件节点做同一件事
        gate = K._command_nodes(t, "ConditionalsConditionAccumulationNumber")[0]
        gate[4] = ["DoNothing"]                                   # 空分支写枚举 → 进游戏 F1009
        self.assertTrue(K.donothing_problems(t))

    def test_fx_manifest_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            mapping, info = K.load_fx_manifest(Path(tmp))
            self.assertEqual(mapping, {})
            self.assertFalse(info["present"])

    def _write_manifest(self, tmp: Path, payload) -> Path:
        path = tmp / K.FX_MANIFEST_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_fx_manifest_forms(self):
        sheet = f"{K.CANNON_SRC}/super_robot.png"
        laser_dir = K.laser_src("l")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            path = self._write_manifest(tmp, {"sheets": {sheet: "cannon.png", laser_dir: {"png": "l.png"}}})
            (path.parent / "cannon.png").write_bytes(png_bytes((4, 4), (1, 2, 3, 255)))
            (path.parent / "l.png").write_bytes(png_bytes((4, 4), (1, 2, 3, 255), store=False))
            mapping, info = K.load_fx_manifest(tmp)
            self.assertEqual(set(mapping), {sheet, f"{laser_dir}/enemy_shot_laser_l_yellow.png"})
            path.write_text(json.dumps([{"source": sheet, "file": "cannon.png"}]), encoding="utf-8")
            mapping, _ = K.load_fx_manifest(tmp)
            self.assertEqual(set(mapping), {sheet})

    def test_fx_manifest_rejects_unknown_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._write_manifest(tmp, {"battle/effect/skill_unique/other/other.png": "x.png"})
            with self.assertRaises(K.KitError):
                K.load_fx_manifest(tmp)
            self._write_manifest(tmp, {f"{K.CANNON_SRC}/super_robot.png": "missing.png"})
            with self.assertRaises(K.KitError):
                K.load_fx_manifest(tmp)

    def test_pixel_review_verdict_reads_fix_round_only(self):
        head = "# R\n\n## 2. 初审\n\n| tekuto 特克托 | 12/12 过 | **PASS** | 无 |\n\n"
        fix = "## 5. 修复轮复核（x）\n\n| 角色 | a | b | c | 最终判定 |\n|---|---|---|---|---|\n"
        self.assertFalse(K.pixel_review_verdict(head)[0])                     # 只有初审段 → 不算
        self.assertTrue(K.pixel_review_verdict(head + fix + "| tekuto 特克托 | 未改 | 12/12 过 | 无声明 | **PASS** |\n")[0])
        self.assertFalse(K.pixel_review_verdict(head + fix + "| tekuto 特克托 | 未改 | 11/12 | 无 | **FAIL** |\n")[0])
        self.assertFalse(K.pixel_review_verdict(head + fix + "| zehr 泽赫尔 | 改 | 12/12 过 | 无 | **PASS** |\n")[0])
        # 修复轮段之后的新 ## 段里的 PASS 不算
        self.assertFalse(K.pixel_review_verdict(head + fix + "\n## 6. 其他\n| tekuto | **PASS** |\n")[0])

    def test_pixel_sheet_problems(self):
        import numpy as np
        tpl = np.zeros((4, 3, 4), dtype=np.uint8)
        tpl[1, 1] = (10, 20, 30, 255)
        tpl[0, 0] = (5, 5, 5, 0)                                                # 透明但 RGB 非零
        dyed = tpl.copy()
        dyed[1, 1, :3] = (200, 100, 0)
        self.assertEqual(K.pixel_sheet_problems(dyed, tpl), [])
        bad = dyed.copy(); bad[1, 1, 3] = 128
        self.assertTrue(K.pixel_sheet_problems(bad, tpl))                    # alpha 变了
        bad = dyed.copy(); bad[0, 0, :3] = 0
        self.assertTrue(K.pixel_sheet_problems(bad, tpl))                    # 透明像素 RGB 变了
        self.assertTrue(K.pixel_sheet_problems(dyed[:3], tpl))               # 尺寸

    def test_atlas_bounds(self):
        atlas = [{"n": "a", "x": 0, "y": 0, "w": 10, "h": 5}, {"n": "b", "x": 5, "y": 5, "w": 5, "h": 5, "r": True}]
        self.assertEqual(K.atlas_bounds_problems(atlas, (10, 10)), [])
        self.assertTrue(K.atlas_bounds_problems(atlas, (9, 10)))

    def test_png_transform_size_and_stats(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            dyed = Path(tmp) / "d.png"
            dyed.write_bytes(png_bytes((4, 4), (255, 214, 40, 255)))
            stats = {}
            fn = K.make_png_transform("x.png", dyed, stats)
            out = fn(Image.new("RGBA", (4, 4), (0, 0, 0, 255)))
            self.assertEqual(out.getpixel((0, 0)), (255, 214, 40, 255))
            self.assertIsNone(stats["x.png"]["alpha_changed_bbox"])
            with self.assertRaises(K.KitError):
                fn(Image.new("RGBA", (5, 4), (0, 0, 0, 255)))


if __name__ == "__main__":
    unittest.main()
