# -*- coding: utf-8 -*-
"""凯尔 139990 ``kyle_moon`` 2026-09-27 平衡第三轮（c：队长成长 4/5 + 追击段数撤封顶 U1）。

fixture = live 1.4.1053 输入快照（``fixtures/balance_20260927c_kyle.json``），驱动 ``revise()``：
每处改动的前后值与取整规则、未改行 / 未改格逐字保留、追击树只改 Bind 上限且逐字节回到第二批前、
629 调用方仍是「仅队长 + 雷共鸣」、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、合法性门禁为空、
DSL AMF3 往返与四道门禁、面板规则、第二批输出首尾相接、生成器输出 == revise() 输出（需要 .cdn/cn 与
live store 的用 skipUnless）、设计镜像（主会话 ``--write`` 前在内存里验证，写后验证落盘）。
C 节（面板合并 / 共鸣省略）：三块面板逐字、只删登记的「雷属性共鸣时，」、``wf_panel_merge_check.check`` 通过
（仓库内校验器，硬依赖）、「月牙」共鸣省略依据（输入行 fail closed；live 全表 + 凯尔全部 DSL 的全量核对需要 live store）。
D 节（本轮面板统一口径）：口径 3「雷属性共鸣时：」→「雷属性共鸣时，」（测试里显式写出规范化步骤再交给校验器）、
口径 4 两处按数据改文字（冲刺行去共鸣前缀、「追击伤害」改眩晕畏缩特攻写法）及其数据依据（fail closed）；
暂存前最后一轮：能力6「迟缓」按数据改「冻结」（1399906#0 kind 119 FrozenSlayer、技能强化档 ACFrozen 无 ACSlow）、
能力3 第 1 行按数据条件拆两行（口径 5 扩展，1399903#0/#1 触发不同）及其依据（fail closed），返回面板扫全角「／」与半角「/」。
E 节（技能强化条目，主会话 2026-09-27 口径 R1–R3）：``change_skill_kyle_moon`` 改官方格式点名技能、能力1 面板第 2 行拆成
数值行 + 同文强化条目行、能力6 面板删掉挂错面板的强化行；依据（唯一开关行 1399901#2、同条件、技能名）fail closed，
条目内容对两档技能树 / 天雷树的旗号 1 开支核对（第二批输出 = live；live store 可用时再核一次）；技能描述不含强化后描述。
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import re
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927_kyle as M1  # noqa: E402
import wf_balance_20260927b_kyle as M2  # noqa: E402
import wf_balance_20260927c_kyle as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kit_kyle as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_panel_merge_check as PMC  # noqa: E402
import wf_seasonal7_kit_philia as PH  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927c_kyle.json"
FIXTURE_B = Path(__file__).parent / "fixtures/balance_20260927b_kyle.json"
CANDIDATE = ROOT / "work/character_packs/ma-kyle"


def load_fixture(path: Path = FIXTURE) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


def reader(data: dict):
    def read(kind, key):
        return data[kind][key]
    return read


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(x) for x in text.split("."))


def candidate_written_back() -> bool:
    """主会话暂存回写（package_version 升到本模块版本）后为 True。"""
    manifest = json.loads((CANDIDATE / "package/manifest.json").read_text(encoding="utf-8"))
    return _version(manifest["package_version"]) >= _version(M.PACKAGE_VERSION["ma-kyle"])


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


def batch2_live() -> dict:
    """第二批 live 输入 + 第二批 revise() 输出 = 第三轮的 live（链尾 1.4.1053）全集（含本轮只读或不读的键）。"""
    live = load_fixture(FIXTURE_B)
    out = M2.revise(reader(deepcopy(live)))
    for kind in ("leader", "ability", "cas", "dsl"):
        live[kind].update(deepcopy(out[kind]))
    return live


def _percent(value: str) -> float:
    return int(value) / 1000          # 100000 = 100%


def _pierce_bind(tree) -> list:
    return tree[11][1][0][1]


def _condition_names(node) -> list[str]:
    """树里出现的全部 ``AC*`` 状态节点名（CreateCondition 的付与内容）。"""
    found = []
    if isinstance(node, list):
        if node and isinstance(node[0], str) and node[0].startswith("AC"):
            found.append(node[0])
        for item in node:
            found += _condition_names(item)
    elif isinstance(node, dict):
        for item in node.values():
            found += _condition_names(item)
    return found


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         set(M.BEFORE))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (str(K.CID), K.CODE))
        self.assertEqual(M.PACKAGES, ["ma-kyle"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-kyle": "1.0.4"})       # 候选现值 1.0.3（第二批），只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertGreater(_version(M.PACKAGE_VERSION["ma-kyle"]), _version(M2.PACKAGE_VERSION["ma-kyle"]))

    @unittest.skipUnless((CANDIDATE / "package/manifest.json").is_file(), "candidate ma-kyle missing")
    def test_package_version_moves_forward(self):
        manifest = json.loads((CANDIDATE / "package/manifest.json").read_text(encoding="utf-8"))
        current, new = _version(manifest["package_version"]), _version(M.PACKAGE_VERSION["ma-kyle"])
        if candidate_written_back():
            self.assertEqual(new, current)              # 已回写：候选现值 == 本模块版本
        else:
            self.assertGreater(new, current)
        self.assertTrue(set(M.CAPABILITIES) <= set(manifest["required_capabilities"]))

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["leader"]), {M.CID})
        self.assertEqual(out["ability"], {})                              # 1399902/1399903 只读核对；能力2 封顶版不动（D4）
        # C 节：能力2/3 面板省略共鸣；能力6：「迟缓」→「冻结」（暂存前最后一轮新返回）；E 节：能力1 面板与强化条目
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER, M.CAS_ABILITY1, M.CAS_ABILITY2, M.CAS_ABILITY3,
                                           M.CAS_ABILITY6, M.CAS_SWITCH})
        self.assertEqual(set(out["dsl"]), {M.PIERCE_PROGRAM})
        for kind in ("text", "table", "action", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)
        for key in out["cas"]:   # RevisionCandidate 命名空间
            self.assertTrue(key.startswith(("desc_override_" + M.CODE, "change_skill_" + M.CODE)), key)
        for kind in ("leader", "cas", "dsl"):
            for key, value in out[kind].items():
                self.assertNotEqual(value, self.live[kind][key], f"{kind}:{key} returned but unchanged")


class LeaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old, cls.new = cls.live["leader"][M.CID], cls.out["leader"][M.CID]

    def test_row_count_and_width_are_kept(self):
        self.assertEqual((len(self.old), len(self.new)), (9, 9))
        self.assertTrue(all(len(r) == 124 for r in self.new))

    def test_every_edit_before_and_after(self):
        want = {0: (111, "1250", "10000"), 1: (111, "6250", "50000"), 2: (111, "7500", "60000"),
                3: (111, "2500", "20000"), 6: (49, "2500", "20000"), 7: (49, "500", "4000")}
        for index, (col, before, after) in want.items():
            self.assertEqual(self.old[index][col:col + 2], [before, before], f"leader#{index}")
            self.assertEqual(self.new[index][col:col + 2], [after, after], f"leader#{index}")
            diff = [c for c, (a, b) in enumerate(zip(self.old[index], self.new[index])) if a != b]
            self.assertEqual(diff, [col, col + 1], f"leader#{index} touched other cells")
        for index in (4, 5, 8):
            self.assertEqual(self.new[index], self.old[index], f"leader#{index}")
        self.assertEqual([r[45] for r in self.new[4:6]], ["245", "35"])  # 槽上限 / 充能（口径 A6）

    def test_values_are_four_fifths_of_the_originals(self):
        """原值（第二批前）= 第二批值 ×10；新值 = 原值 ×4/5（合并行按两部分原值之和），都已是 5% 的倍数或 ≤10% 的 0.5% 档。"""
        for index, (_cells, cols, batch2, originals, new, _why) in M.LEADER_EDITS.items():
            original = sum(int(v) for v in originals)
            self.assertEqual(int(self.old[index][cols[0]]) * 10, original, f"leader#{index}")
            self.assertEqual(Fraction(original) * Fraction(4, 5), int(new), f"leader#{index}")
            self.assertEqual(int(self.new[index][cols[0]]), int(new))
            step = 5000 if original >= 10000 else 500
            self.assertEqual(int(new) % step, 0, f"leader#{index}")
        # 合并行：#1 = 自身 12.5% + 能力2#1 50%，#2 = 雷队直击 25% + 能力2#0 50%
        self.assertEqual(M.LEADER_EDITS[1][3], ("12500", "50000"))
        self.assertEqual(M.LEADER_EDITS[2][3], ("25000", "50000"))

    def test_rounding_rule(self):
        self.assertEqual(M.rescale(12500), 10000)
        self.assertEqual(M.rescale(5000), 4000)                            # ≤10%：0.5% 档，不强行取 5 的倍数
        self.assertEqual(M.rescale(50000, Fraction(2, 3), up=True), 35000)  # 2/3 档向上取（黑）
        self.assertEqual(M.rescale(150000, Fraction(7, 10)), 105000)
        self.assertEqual(M.rescale(45000), 35000)                          # 36 → 35（作者原话 6）
        self.assertEqual(M.rescale(48750), 40000)                          # 39 → 40

    def test_growth_rows_keep_their_trigger_and_unlimited_limit(self):
        for row in self.new[:4]:
            self.assertEqual((row[95], row[100], row[102]), ("134", "(None)", M.UID_CRESCENT))
        for row in self.new[6:8]:
            self.assertEqual((row[25], row[32], row[33]), ("51", "(None)", "0"))

    def test_row_locators_are_content_based(self):
        moved = deepcopy(self.old)
        moved[0], moved[1] = moved[1], moved[0]
        with self.assertRaises(M.KyleBalanceCError):
            M.leader_rows(moved)
        changed = deepcopy(self.old)
        changed[6][49] = changed[6][50] = "3000"
        with self.assertRaises(M.KyleBalanceCError):
            M.leader_rows(changed)
        changed = deepcopy(self.old)
        changed[4][45] = "211"
        with self.assertRaises(M.KyleBalanceCError):
            M.leader_rows(changed)


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old = cls.live["cas"][M.CAS_LEADER][0][0].split("\n")
        cls.new = cls.out["cas"][M.CAS_LEADER][0][0].split("\n")

    def test_leader_panel_text(self):
        self.assertEqual((len(self.old), len(self.new)), (7, 7))
        self.assertEqual([i for i, (a, b) in enumerate(zip(self.old, self.new)) if a != b],
                         list(M.CHANGED_PANEL_LINES))
        # D 节口径 4：第 2 行去掉无数据依据的共鸣前缀
        self.assertEqual((self.old[1], self.new[1]), ("雷属性共鸣时：强化自身冲刺", "强化自身冲刺"))
        # C 节：第 4、5 行是「月牙」提供的效果 ⇒ 省略共鸣前缀
        self.assertEqual(self.new[3], "自身“月牙”每上升1层，自身攻击力＋60%、直击伤害＋80%；"
                                      "除自身外雷属性角色攻击力＋10%、直击伤害＋60%")
        self.assertEqual(self.new[4], "自身“月牙”每上升1层，自身直击判定次数＋1")
        # D 节口径 3 + 4：冒号改逗号；「追击伤害」按数据（队长#7 kind 53）改为眩晕畏缩特攻写法
        self.assertEqual(self.new[5], "雷属性共鸣时，自身每获得一次贯穿效果，雷属性角色攻击力＋20%，"
                                      "对处于“眩晕”、“畏缩”状态的敌人造成伤害，额外乘区＋4%")
        self.assertEqual(self.new[6], "雷属性共鸣时，雷属性角色技能槽最大值＋20%、技能充能速度＋20%")
        self.assertEqual(self.old[4], "雷属性共鸣时：自身“月牙”每上升1层，自身直击判定次数＋1（最多10层）")
        self.assertEqual(self.old[5], "雷属性共鸣时：自身每获得一次贯穿效果，雷属性角色攻击力＋2.5%、追击伤害＋0.5%")

    def test_leader_panel_numbers_equal_the_rows(self):
        rows = self.out["leader"][M.CID]
        share = {(r[107], r[108]): _percent(r[111]) for r in rows if r[95] == "134"}
        self_attack = share[("0", "5")] + share[("0", "0")]
        self_direct = share[("1", "5")] + share[("1", "0")]
        self.assertEqual((self_attack, self_direct), (60, 80))
        line = self.new[3]
        self.assertIn(f"自身攻击力＋{self_attack:g}%", line)
        self.assertIn(f"直击伤害＋{self_direct:g}%", line)
        self.assertIn(f"除自身外雷属性角色攻击力＋{share[('0', '5')]:g}%", line)
        self.assertIn(f"直击伤害＋{share[('1', '5')]:g}%", line.split("；")[1])
        pierce = {r[45]: _percent(r[49]) for r in rows if r[25] == "51"}
        self.assertIn(f"攻击力＋{pierce['32']:g}%", self.new[5])
        # kind 53 = 眩晕畏缩特攻（独立乘区），面板写特攻，不写「追击伤害」
        self.assertIn(f"对处于“眩晕”、“畏缩”状态的敌人造成伤害，额外乘区＋{pierce['53']:g}%", self.new[5])
        self.assertFalse([line for line in self.new if "追击伤害" in line])
        # 段数上限已撤：面板段数行不再写上限（上限 = 月牙上限 99）
        self.assertEqual(_pierce_bind(self.out["dsl"][M.PIERCE_PROGRAM])[5], 99)
        self.assertNotIn("最多", self.new[4])

    def test_panel_texts_obey_the_project_rules(self):
        text = self.out["cas"][M.CAS_LEADER][0][0]
        self.assertNotIn("／", text)
        for line in text.split("\n"):
            self.assertEqual(KL.panel_problems(line), [], line)
            self.assertFalse(line.startswith(K.MAIN_ICON), line)            # 队长块不带主位图标
        for word in ("可无限", "无上限", "无限叠加", "不设上限", "不受此限", "自身为队长时", "觉醒后", "生命值100%以下"):
            self.assertNotIn(word, text)
        self.assertFalse(re.search(r"\d+(\.\d+)?%（觉醒", text))


_SIGNED = re.compile(r"[＋－]\d+(?:\.\d+)?%?")


class PanelMergeTests(unittest.TestCase):
    """C 节：面板同条件合并（凯尔无可并行）与「月牙」共鸣省略；D 节：本轮面板统一口径 3/4。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_final_panels_verbatim(self):
        icon = M.MAIN_ICON
        self.assertEqual(self.out["cas"][M.CAS_LEADER], [["\n".join((
            "赋予自身特殊强化弹射",
            "强化自身冲刺",
            "自身冲刺间隔无法进一步缩短",
            "自身“月牙”每上升1层，自身攻击力＋60%、直击伤害＋80%；除自身外雷属性角色攻击力＋10%、直击伤害＋60%",
            "自身“月牙”每上升1层，自身直击判定次数＋1",
            "雷属性共鸣时，自身每获得一次贯穿效果，雷属性角色攻击力＋20%，"
            "对处于“眩晕”、“畏缩”状态的敌人造成伤害，额外乘区＋4%",
            "雷属性共鸣时，雷属性角色技能槽最大值＋20%、技能充能速度＋20%",
        ))]])
        self.assertEqual(self.out["cas"][M.CAS_ABILITY2], [[
            icon + "自身“月牙”每提升1层，自身攻击力＋16%、雷属性角色直击伤害＋10%（最多10层）"]])
        self.assertEqual(self.out["cas"][M.CAS_ABILITY3], [["\n".join((
            icon + "雷属性共鸣时，雷属性角色发动技能时，自身“月牙”＋1层",
            icon + "雷属性共鸣时，雷属性角色每造成100次直击，自身“月牙”＋1层",
            icon + "雷属性共鸣时，自身每获得一次贯穿效果，2秒后自身技能槽＋10%（冷却时间：10秒）",
            icon + "自身持有“月牙”时，强化雷属性角色的直接攻击为3次，合计伤害额外乘区＋300%",
        ))]])
        self.assertEqual(self.out["cas"][M.CAS_ABILITY6], [[
            "雷属性共鸣时，雷属性角色对处于“冻结”状态的敌人造成伤害，额外乘区＋15%"]])
        enhancement = ("强化『月华·狼牙连斩』：追加赋予队伍贯穿、直接攻击伤害提升与加速效果，"
                       "消除距离最近的敌人的部分强化效果并赋予其冻结效果，同时强化自身直击召唤的天雷")
        self.assertEqual(self.out["cas"][M.CAS_ABILITY1], [["\n".join((
            icon + "战斗开始时：雷属性角色技能槽＋50%",
            icon + "雷属性共鸣时，自身技能槽＋50%",
            icon + "雷属性共鸣时，" + enhancement,
        ))]])
        self.assertEqual(self.out["cas"][M.CAS_SWITCH], [[enhancement]])

    def test_only_the_registered_prefixes_are_dropped(self):
        """D 节后（= 校验原文）→ 最终：只有 RESONANCE_DROPS 登记的行变了，且只删了行首（图标后）的「雷属性共鸣时，」；
        没有合并行（行数不变）；数值记号多重集合不变。能力6 没有省略（D 节后 == 最终）。"""
        self.assertEqual(M.PANEL_MERGES, {})
        self.assertNotIn(M.CAS_ABILITY6, M.RESONANCE_DROPS)
        for key, (old, numeric, preedit, new) in M.PANEL_TEXTS.items():
            self.assertEqual(self.live["cas"][key], [[old]], key)
            self.assertEqual(self.out["cas"][key], [[new]], key)
            before, after = preedit.split("\n"), new.split("\n")
            self.assertEqual(len(before), len(after), key)
            changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
            self.assertEqual(changed, sorted(M.RESONANCE_DROPS.get(key, {})), key)
            for i in changed:
                icon = M.MAIN_ICON if before[i].startswith(M.MAIN_ICON) else ""
                self.assertEqual(after[i].startswith(M.MAIN_ICON), bool(icon), f"{key} L{i + 1} icon")
                self.assertEqual(before[i], icon + "雷属性共鸣时，" + after[i][len(icon):], f"{key} L{i + 1}")
            self.assertEqual(Counter(_SIGNED.findall(preedit)), Counter(_SIGNED.findall(new)), key)
        # 获取「月牙」的两行（口径 5 拆出）、贯穿 / 充能行照写共鸣（逗号写法）；冲刺行按数据不写共鸣
        for index in (0, 1, 2):
            self.assertTrue(M.NEW_ABILITY3_TEXT.split("\n")[index].startswith(M.MAIN_ICON + "雷属性共鸣时，"), index)
        for line in M.NEW_ABILITY6_TEXT.split("\n"):                        # 技能开关行（口径 2）/ 冻结特攻行照写
            self.assertTrue(line.startswith("雷属性共鸣时，"), line)
        for index in (5, 6):
            self.assertTrue(M.NEW_LEADER_TEXT.split("\n")[index].startswith("雷属性共鸣时，"), index)
        self.assertEqual(M.NEW_LEADER_TEXT.split("\n")[1], "强化自身冲刺")

    @staticmethod
    def _normalized_origin(key: str, numeric: str) -> str:
        """校验原文的规范化步骤（显式写出，不借模块函数）：
        1. 口径 3：「X属性共鸣时：」→「X属性共鸣时，」（凯尔五块覆盖面板没有「共鸣时：」后换行接效果的行，无需并行）；
        2. 口径 4：队长第 2 行去掉无数据依据的共鸣前缀、第 6 行「追击伤害＋4%」按数据改为眩晕畏缩特攻写法；
           能力6 第 2 行「迟缓」按数据（kind 119 冻结特攻 / ACFrozen）改「冻结」；
        3. 口径 5：能力3 第 1 行在「；」处按数据条件拆两行，后半行补同一个图标与共鸣前缀；
        4. E 节：能力1 第 2 行在「，并」处拆开，后半句换成官方格式强化条目（同 CAS 文案），补同一个图标与共鸣前缀；
           能力6 第 1 行（能力6 无开关行的强化行）删除。"""
        text = re.sub(r"([火水雷风光暗]属性共鸣时)：", r"\1，", numeric)
        lines = text.split("\n")
        if key == M.CAS_LEADER:
            assert lines[1] == "雷属性共鸣时，强化自身冲刺", lines[1]
            lines[1] = "强化自身冲刺"
            assert lines[5].endswith("雷属性角色攻击力＋20%、追击伤害＋4%"), lines[5]
            lines[5] = lines[5].replace("、追击伤害＋4%", "，对处于“眩晕”、“畏缩”状态的敌人造成伤害，额外乘区＋4%")
        if key == M.CAS_ABILITY6:
            assert lines[1].count("“迟缓”") == 1, lines[1]
            lines[1] = lines[1].replace("“迟缓”", "“冻结”")
            assert lines[0] == "雷属性共鸣时，进一步强化技能「月华·狼牙连斩」的效果", lines[0]
            del lines[0]
        if key == M.CAS_ABILITY1:
            head, tail = lines[1].split("，并")
            prefix = M.MAIN_ICON + "雷属性共鸣时，"
            assert head == prefix + "自身技能槽＋50%" and tail == "进一步强化技能「月华·狼牙连斩」的效果", lines[1]
            lines[1:2] = [head, prefix + M.NEW_SWITCH_TEXT]
        if key == M.CAS_ABILITY3:
            head, tail = lines[0].split("；")
            prefix = M.MAIN_ICON + "雷属性共鸣时，"
            assert head.startswith(prefix) and not tail.startswith(M.MAIN_ICON), lines[0]
            lines[0:1] = [head, prefix + tail]
        return "\n".join(lines)

    def test_check_merge_passes(self):
        """仓库内校验器 ``wf_panel_merge_check.check``（硬依赖）：原文 = 本轮数值改后文案经口径 3/4 规范化，
        只授权 RESONANCE_DROPS 登记的行删前缀。"""
        for key, (_old, numeric, preedit, new) in M.PANEL_TEXTS.items():
            origin = self._normalized_origin(key, numeric)
            self.assertEqual(origin, preedit, key)                                  # 与模块的 D 节结果逐字相同
            self.assertNotIn("属性共鸣时：", origin, key)
            dropped = sorted(M.RESONANCE_DROPS.get(key, {}))
            drops = [dict(line=i + 1, resonance=M.ELEMENT_TOKEN) for i in dropped]
            result = PMC.check(origin, new, drops)
            self.assertTrue(result["ok"], (key, result["errors"]))
            self.assertEqual(result["warnings"], [], key)
            kinds = result["columns"][0]["kinds"]
            self.assertEqual(sorted(k for k, kind in kinds.items() if kind == "prefix_drop"),
                             [i + 1 for i in dropped], key)
            self.assertEqual(sorted(k for k, kind in kinds.items() if kind == "verbatim"),
                             [j + 1 for j in range(len(new.split("\n"))) if j not in dropped], key)
            # 负对照：不授权删前缀 ⇒ 校验器必须拒绝（能力6 无省略，不适用）；不做规范化 ⇒ 冒号 /「迟缓」/ 未拆行
            # 被当成未授权改写或来源不明
            if dropped:
                self.assertFalse(PMC.check(origin, new, [])["ok"], key)
            raw, normalized = numeric.split("\n"), origin.split("\n")
            # 能力6：未规范化原文的强化行不带数值，校验器会把它当成并入冻结特攻行的「merge」而放行（校验器对无数值行的
            # 已知宽松）⇒ 该负对照改由循环后的「不删强化行（逗号写法）⇒ 拒绝」覆盖
            if key != M.CAS_ABILITY6 and (len(raw) != len(normalized)
                                          or any(a != b for i, (a, b) in enumerate(zip(raw, normalized))
                                                 if i not in dropped)):
                self.assertFalse(PMC.check(numeric, new, drops)["ok"], key)
        # 口径 5：不拆行的原文交给校验器 ⇒ 拆出的第 2 行没有来源，必须拒绝
        joined = M.PREEDIT_ABILITY3_TEXT.replace(
            "\n".join(M.ABILITY3_SPLIT_LINES), M.ABILITY3_JOINED_LINE)
        self.assertEqual(M.split_panel(M.CAS_ABILITY3, joined), M.PREEDIT_ABILITY3_TEXT)
        self.assertFalse(PMC.check(joined, M.NEW_ABILITY3_TEXT,
                                   [dict(line=3, resonance=M.ELEMENT_TOKEN)])["ok"])
        # 「迟缓」不按数据改的原文 ⇒ 这一行只有一个来源却被改写，必须拒绝
        slow = M.PREEDIT_ABILITY6_TEXT.replace("“冻结”", "“迟缓”")
        self.assertFalse(PMC.check(slow, M.NEW_ABILITY6_TEXT, [])["ok"])
        # E 节：不删强化行 / 不拆强化条目的原文交给校验器 ⇒ 行来源对不上，必须拒绝
        kept = "雷属性共鸣时，进一步强化技能「月华·狼牙连斩」的效果\n" + M.PREEDIT_ABILITY6_TEXT
        self.assertFalse(PMC.check(kept, M.NEW_ABILITY6_TEXT, [])["ok"])
        joined = M.normalize_resonance(M.OLD_ABILITY1_TEXT)
        self.assertFalse(PMC.check(joined, M.NEW_ABILITY1_TEXT, [])["ok"])

    def test_resonance_punctuation_rule(self):
        """口径 3：本模块返回的面板里没有「X属性共鸣时：」；规范化函数只改标点，并把「共鸣时：」后换行接效果的并成一行。"""
        for key, rows in self.out["cas"].items():
            self.assertNotRegex(rows[0][0], r"属性共鸣时[：:]", key)
        self.assertEqual(M.normalize_resonance("雷属性共鸣时：A\nB"), "雷属性共鸣时，A\nB")
        self.assertEqual(M.normalize_resonance("雷属性共鸣时：\nA＋1%\nB"), "雷属性共鸣时，A＋1%\nB")
        icon = M.MAIN_ICON
        self.assertEqual(M.normalize_resonance(icon + "Fever中，雷属性共鸣时：\n" + icon + "A＋1%"),
                         icon + "Fever中，雷属性共鸣时，A＋1%")
        self.assertEqual(M.normalize_resonance("Fever中：A"), "Fever中：A")           # 非共鸣条件的冒号不动
        for key, (_old, numeric, preedit, _new) in M.PANEL_TEXTS.items():
            self.assertEqual(M.enhance_panel(key, M.split_panel(key, M.correct_panel(key, M.normalize_resonance(numeric)))),
                             preedit, key)
            self.assertEqual(M.normalized_panel(key, numeric), preedit, key)

    def test_data_corrections_follow_the_data(self):
        """口径 4：冲刺行（能力5 #1–#4 kind 422）只挂前置 42、无雷共鸣；队长#7 是 kind 53 眩晕畏缩特攻 4%。"""
        live = self.live
        leader = self.out["leader"][M.CID]
        basis = M.panel_correction_basis(live["ability"][M.ABILITY5], leader)
        self.assertEqual(basis["dash"]["rows"], [f"{M.ABILITY5}#{i}" for i in (1, 2, 3, 4)])
        self.assertEqual(basis["stun_wince"], {"row": f"{M.CID}#7", "kind": "53", "strength": "4000"})
        self.assertEqual(self.out["notes"]["panel_rules_20260927"]["basis"], basis)
        for row in (live["ability"][M.ABILITY5][i] for i in (1, 2, 3, 4)):
            self.assertEqual((row[6], row[13], row[20], row[109]), ("42", "0", "0", "422"))
        self.assertEqual(KL.describe("leader_ability", leader[7]), "雷·编成≥6 时: 状态贯通≥1 → 赋予全队(雷) 眩晕畏缩特攻 4%")
        self.assertEqual(sorted(M.PANEL_CORRECTIONS), sorted([M.CAS_LEADER, M.CAS_ABILITY6]))
        self.assertEqual(sorted(M.PANEL_CORRECTIONS[M.CAS_LEADER]), [1, 5])
        self.assertEqual(sorted(M.PANEL_CORRECTIONS[M.CAS_ABILITY6]), [1])
        self.assertIn("“冻结”", M.PANEL_CORRECTIONS[M.CAS_LEADER][5][2])            # 措辞来源已随能力6 改「冻结」
        # 冲刺参数行加上雷共鸣 / 多出一行冲刺参数 / #7 不再是特攻 ⇒ 依据不成立 ⇒ 拒绝
        data = deepcopy(live)
        data["ability"][M.ABILITY5][2][13], data["ability"][M.ABILITY5][2][16:19] = "2", ["600000", "600000", "Yellow"]
        with self.assertRaisesRegex(M.KyleBalanceCError, "leader precondition alone"):
            M.panel_correction_basis(data["ability"][M.ABILITY5], leader)
        data = deepcopy(live)
        data["ability"][M.ABILITY5][0][109] = "422"
        with self.assertRaisesRegex(M.KyleBalanceCError, "dash-parameter rows drift"):
            M.panel_correction_basis(data["ability"][M.ABILITY5], leader)
        moved = deepcopy(leader)
        moved[7][45] = "31"
        with self.assertRaisesRegex(M.KyleBalanceCError, "stun/wince"):
            M.panel_correction_basis(live["ability"][M.ABILITY5], moved)
        weaker = deepcopy(leader)
        weaker[7][49] = weaker[7][50] = "3000"
        with self.assertRaisesRegex(M.KyleBalanceCError, "slayer strength"):
            M.panel_correction_basis(live["ability"][M.ABILITY5], weaker)

    def test_frozen_wording_follows_the_data(self):
        """「迟缓」→「冻结」：能力6#0 = kind 119 FrozenSlayer（describe = 冻结特攻）15%、全队(雷)、带雷共鸣；
        状态本体 = 两档技能树强化档的 ACFrozen（无 ACSlow）。依据变了 ⇒ 拒绝。"""
        live = self.live
        rows = live["ability"][M.ABILITY6]
        basis = M.frozen_slayer_basis(rows)
        self.assertEqual((basis["row"], basis["strength"]), (f"{M.ABILITY6}#0", "15000"))
        self.assertEqual(self.out["notes"]["panel_rules_20260927"]["frozen_basis"], basis)
        self.assertEqual(KL.describe("ability", rows[0]), "雷·编成≥6 时: 赋予全队(雷) 冻结特攻 15%")
        self.assertEqual(K.EXPECT[f"{M.ABILITY6}#0"], KL.describe("ability", rows[0]))
        enum = json.loads((ROOT / "mod-tools/ability_enum_map.json").read_text(encoding="utf-8"))
        self.assertEqual(enum["enums"]["InstantAbilityContentMasterValue"][M.FROZEN_SLAYER_KIND], "FrozenSlayer")
        # 技能树（第二批输出 = live）两档都施加 ACFrozen，没有 ACSlow
        trees = batch2_live()["dsl"]
        for program in M2.SKILL_PROGRAMS.values():
            names = Counter(_condition_names(trees[program]))
            self.assertGreaterEqual(names["ACFrozen"], 1, program)
            self.assertEqual(names["ACSlow"], 0, program)
        for col, value in ((47, "118"), (51, "20000"), (6, "0"), (49, "Blue")):
            data = deepcopy(rows)
            data[0][col] = value
            if col == 51:
                data[0][52] = value
            with self.assertRaises(M.KyleBalanceCError, msg=f"c{col}"):
                M.frozen_slayer_basis(data)
        with self.assertRaises(M.KyleBalanceCError):
            M.frozen_slayer_basis(rows + [list(rows[0])])

    @unittest.skipUnless(_baseline_available(), "需要 live store")
    def test_frozen_state_source_in_the_live_skill_trees(self):
        import wf_midautumn_common as MC
        import wf_midautumn_specs as MS
        import wf_seasonal7_build as B
        ctx = B.KitContext(MC.MAPack(MS.get_spec("kyle"), record_sources=False))
        for program in M2.SKILL_PROGRAMS.values():
            tree = wf_dsl.parse_dsl(zlib.decompress(ctx.live_read(wf_dsl.dsl_logical(program)), -15))["tree"]
            names = Counter(_condition_names(tree))
            self.assertGreaterEqual(names["ACFrozen"], 1, program)
            self.assertEqual(names["ACSlow"], 0, program)

    def test_ability3_split_follows_the_data(self):
        """口径 5：能力3#0（触发 23）/#1（触发 20，每 100 次）前置与内容逐格相同、触发不同 ⇒ 拆两行，各自照写共鸣前缀。"""
        rows = self.live["ability"][M.ABILITY3]
        basis = M.panel_split_basis(rows)
        self.assertEqual(basis["rows"], [f"{M.ABILITY3}#0", f"{M.ABILITY3}#1"])
        self.assertEqual(self.out["notes"]["panel_rules_20260927"]["split_basis"], basis)
        self.assertEqual([KL.describe("ability", rows[i]) for i in (0, 1)],
                         ["雷·编成≥6 时: 技能发动≥1 → 自身 状态固有 100%×1次",
                          "雷·编成≥6 时: 编成直接攻击≥100 → 自身 状态固有 100%×1次"])
        new = self.out["cas"][M.CAS_ABILITY3][0][0].split("\n")
        old = self.live["cas"][M.CAS_ABILITY3][0][0].split("\n")
        self.assertEqual((len(old), len(new)), (3, 4))
        # 拆出的两行去掉后半行的图标与前缀、以「；」拼回 == 口径 3 之后的原行
        prefix = M.MAIN_ICON + "雷属性共鸣时，"
        self.assertEqual(new[0] + "；" + new[1][len(prefix):], M.normalize_resonance(old[0]))
        self.assertEqual(Counter(_SIGNED.findall(old[0])), Counter(_SIGNED.findall(new[0] + new[1])))
        self.assertTrue(all("；" not in line for line in new))
        # 两行条件相同 ⇒ 该合并不该拆；前置 / 内容不同或触发漂移 ⇒ 拒绝
        same = deepcopy(rows)
        same[1][27:37] = same[0][27:37]
        with self.assertRaisesRegex(M.KyleBalanceCError, "trigger drift|merge instead"):
            M.panel_split_basis(same)
        for col, value in ((6, "0"), (68, "13999003"), (30, "5000000"), (27, "51")):
            data = deepcopy(rows)
            data[1][col] = value
            with self.assertRaises(M.KyleBalanceCError, msg=f"c{col}"):
                M.panel_split_basis(data)
        with self.assertRaisesRegex(M.KyleBalanceCError, "pre-split"):
            M.split_panel(M.CAS_ABILITY3, M.PREEDIT_ABILITY3_TEXT)                 # 已拆过 ⇒ 不再拆

    def test_rule_scan_catches_half_width_slashes(self):
        self.assertEqual(M.panel_rule_problems(M.CAS_LEADER, M.NEW_LEADER_TEXT), [])
        for bad in ("Lv1/Lv2 攻击力＋1%/2%", "Lv1／Lv2", "雷属性共鸣时：A＋1%", "对处于“迟缓”状态的敌人"):
            self.assertTrue(M.panel_rule_problems("k", bad), bad)

    def test_panel_rules_on_every_returned_line(self):
        for key, rows in self.out["cas"].items():
            text = rows[0][0]
            self.assertNotIn("／", text)
            self.assertNotIn("/", text)                                            # 半角斜杠同样不许分项 / 分级
            self.assertNotIn("迟缓", text)
            self.assertNotIn("Ⓜ", text)
            self.assertEqual(M.panel_rule_problems(key, text), [], key)
            for line in text.split("\n"):
                self.assertEqual(KL.panel_problems(line.replace(M.MAIN_ICON, "")), [], f"{key}: {line}")
                # 主位限制槽（能力 1/2/3，c1=false）每行带图标；队长块、能力6（副位可用）与强化条目不带
                self.assertEqual(line.startswith(M.MAIN_ICON), key in (M.CAS_ABILITY1, M.CAS_ABILITY2, M.CAS_ABILITY3),
                                 f"{key}: {line}")
                self.assertFalse(re.search(r"属性共鸣时[，：].*属性共鸣时", line), line)
            for word in ("自身为队长时", "觉醒后", "生命值100%以下", "可无限", "无上限"):
                self.assertNotIn(word, text)

    def test_resonance_basis_from_the_inputs(self):
        """共鸣省略依据：「月牙」获取行只有能力3#0/#1 且都带雷共鸣；被省略的行的数据都按「月牙」生效。"""
        live = self.live
        basis = M.crescent_resonance_basis(live["ability"][M.ABILITY2], live["ability"][M.ABILITY3],
                                           live["leader"][M.CID])
        self.assertEqual(basis["sources"], [f"{M.ABILITY3}#0（461，前置 kind 2 雷≥6）",
                                            f"{M.ABILITY3}#1（461，前置 kind 2 雷≥6）"])
        self.assertEqual(basis["dependents"]["leader"], [f"{M.CID}#{i}" for i in range(4)])
        self.assertEqual(basis["dependents"]["ability2"], [f"{M.ABILITY2}#0", f"{M.ABILITY2}#1"])
        self.assertEqual(basis["dependents"]["ability3_holder"], [f"{M.ABILITY3}#3"])
        self.assertEqual(self.out["notes"]["panel_merge"]["resonance_basis"], basis)
        self.assertEqual(_pierce_bind(self.live["dsl"][M.PIERCE_PROGRAM])[3], ["DCUnique", int(M.UID_CRESCENT)])
        # 任一获取行丢了雷共鸣 / 多出一个获取行 ⇒ 省略不成立 ⇒ revise() 拒绝
        for index in (0, 1):
            data = deepcopy(live)
            row = data["ability"][M.ABILITY3][index]
            row[6], row[9], row[10], row[11] = "0", "", "", ""
            with self.assertRaisesRegex(M.KyleBalanceCError, "thunder-resonance"):
                M.crescent_resonance_basis(data["ability"][M.ABILITY2], data["ability"][M.ABILITY3],
                                           data["leader"][M.CID])
        data = deepcopy(live)
        data["ability"][M.ABILITY2][0][47], data["ability"][M.ABILITY2][0][68] = "461", M.UID_CRESCENT
        with self.assertRaisesRegex(M.KyleBalanceCError, "crescent grant rows drift"):
            M.crescent_resonance_basis(data["ability"][M.ABILITY2], data["ability"][M.ABILITY3],
                                       data["leader"][M.CID])
        data = deepcopy(live)
        data["ability"][M.ABILITY3][3][12] = "13999003"                      # 能力3#3 不再按月牙生效
        with self.assertRaisesRegex(M.KyleBalanceCError, "crescent-holder"):
            M.crescent_resonance_basis(data["ability"][M.ABILITY2], data["ability"][M.ABILITY3],
                                       data["leader"][M.CID])

    @unittest.skipUnless(_baseline_available(), "需要 live store")
    def test_resonance_basis_against_the_whole_live_store(self):
        """live 全部能力 / 队长表（所有键）里授予 13999001 的只有 1399903#0/#1；凯尔技能、换形、629、PF 程序
        （含嵌套引用）没有 ACUnique 13999001，追击树只 DCUnique 读层数。"""
        import wf_midautumn_common as MC
        import wf_midautumn_specs as MS
        import wf_seasonal7_build as B
        ctx = B.KitContext(MC.MAPack(MS.get_spec("kyle"), record_sources=False))
        grants = []
        for table, ic in ((KL.ABILITY, 47), (KL.LEADER, 45)):
            for key, text in ctx.live_flat(table).items():
                for index, row in enumerate(ctx.csv_split(text)):
                    row = row + [""] * (130 - len(row))
                    if row[ic] in ("461", "413", "436", "459") and row[ic + 21] == M.UID_CRESCENT:
                        grants.append(f"{key}#{index}")
        self.assertEqual(grants, [f"{M.ABILITY3}#0", f"{M.ABILITY3}#1"])

        import wf_share_update_codec as X
        programs = set(K.PF.PROGRAMS) | {K.PIERCE_PROGRAM, K.THUNDER_PROGRAM}
        action = X.unpack(ctx.pack.live_table_bytes(core.ACTION_SKILL_LOGICAL))       # 嵌套表
        for _level, cells in core.decode_action_skill_row(action[M.CODE]):
            programs.add(core.normalize_row_length(cells, 8)[7])
        for key, raw in X.unpack(ctx.pack.live_table_bytes(core.SWITCHED_ACTION_SKILL_LOGICAL)).items():
            if key.startswith(M.CODE):
                programs.update(cells[0] for _level, cells in core.decode_action_skill_row(raw))
        for table, ic in ((KL.ABILITY, 47), (KL.LEADER, 45)):
            for key, text in ctx.live_flat(table).items():
                if key.startswith(M.CID):
                    programs.update(r[ic + 24] for r in ctx.csv_split(text) if len(r) > ic + 24 and r[ic] == "629")

        def walk(node, uniques, refs):
            if isinstance(node, list):
                if node and node[0] in ("ACUnique", "DCUnique") and len(node) > 1:
                    uniques.append((node[0], str(node[1])))
                for item in node:
                    walk(item, uniques, refs)
            elif isinstance(node, dict):
                for item in node.values():
                    walk(item, uniques, refs)
            elif isinstance(node, str) and node.startswith("battle/action/"):
                refs.append(node)

        seen, todo, readers = set(), sorted(programs), []
        while todo:
            program = todo.pop()
            if program in seen:
                continue
            seen.add(program)
            tree = wf_dsl.parse_dsl(zlib.decompress(ctx.live_read(wf_dsl.dsl_logical(program)), -15))["tree"]
            uniques, refs = [], []
            walk(tree, uniques, refs)
            self.assertNotIn(("ACUnique", M.UID_CRESCENT), uniques, program)
            if ("DCUnique", M.UID_CRESCENT) in uniques:
                readers.append(program)
            todo.extend(refs)
        self.assertGreaterEqual(len(seen), 7)
        self.assertEqual(readers, [K.PIERCE_PROGRAM])


class SkillEnhancementTests(unittest.TestCase):
    """E 节（主会话 2026-09-27 口径 R1–R3）：强化条目只写在能力面板 / CAS（官方格式点名技能、定性无数字），技能描述不写。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def _abilities(self, data=None):
        data = data or self.live
        return {f"{M.CID}{slot}": data["ability"][f"{M.CID}{slot}"] for slot in range(1, 7)}

    def test_entry_uses_the_official_format(self):
        text = self.out["cas"][M.CAS_SWITCH][0][0]
        self.assertEqual(self.live["cas"][M.CAS_SWITCH], [[M.OLD_SWITCH_TEXT]])
        self.assertTrue(text.startswith("强化『月华·狼牙连斩』："))
        self.assertEqual(KL.panel_problems(text, skill_flag=True), [])            # 无数字、无秒数
        self.assertEqual(M.panel_rule_problems(M.CAS_SWITCH, text), [])
        for word in ("强化自身技能", "强化技能", "进一步强化", "雷属性共鸣"):          # 共鸣前缀只在面板行（开关行前置）
            self.assertNotIn(word, text)
        with self.assertRaisesRegex(M.KyleBalanceCError, "unexpected skill-enhancement text"):
            M.switch_text(M.CAS_SWITCH, [["进一步强化技能的效果"]])

    def test_panel_entry_line_equals_the_cas_text(self):
        """能力1 面板的强化条目行 = 图标 + 「雷属性共鸣时，」 + CAS 同文；数值行只剩自身技能槽；能力6 不再有强化行。"""
        lines = self.out["cas"][M.CAS_ABILITY1][0][0].split("\n")
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[2], M.MAIN_ICON + "雷属性共鸣时，" + self.out["cas"][M.CAS_SWITCH][0][0])
        self.assertEqual(lines[1], M.MAIN_ICON + "雷属性共鸣时，自身技能槽＋50%")
        self.assertEqual(lines[0], self.live["cas"][M.CAS_ABILITY1][0][0].split("\n")[0])     # 第 1 行逐字
        self.assertEqual(Counter(_SIGNED.findall(M.OLD_ABILITY1_TEXT)),
                         Counter(_SIGNED.findall(self.out["cas"][M.CAS_ABILITY1][0][0])))    # 数值记号不变
        panels = "\n".join(rows[0][0] for key, rows in self.out["cas"].items() if key != M.CAS_SWITCH)
        self.assertEqual(panels.count("强化『月华·狼牙连斩』"), 1)                          # 只在能力1 面板出现一次
        self.assertNotIn("进一步强化", panels)
        self.assertNotIn("强化『", self.out["cas"][M.CAS_ABILITY6][0][0])

    def test_switch_basis_from_the_inputs(self):
        basis = M.switch_basis(self._abilities(), self.live["leader"][M.CID], self.live["action"][M.CODE])
        self.assertEqual(basis["switch"], "1399901#2（kind 536 → 旗号 1，前置 kind 2 雷≥6，c70 change_skill_kyle_moon）")
        self.assertEqual(self.out["notes"]["skill_enhancement"]["basis"], basis)
        rows = self.live["ability"][f"{M.CID}1"]
        self.assertEqual([KL.describe("ability", r) for r in rows[1:]],
                         ["雷·编成≥6 时: 自身 技能槽 50%", "雷·编成≥6 时: 自身 切换技能形态[change_skill_kyle_moon]"])
        self.assertEqual(KL.describe("ability", self.live["ability"][M.ABILITY6][0]), "雷·编成≥6 时: 赋予全队(雷) 冻结特攻 15%")
        # 能力6 多出开关行（强化行就不算挂错）/ 开关行丢共鸣 / 开关行换文案键 / 技能名漂移 ⇒ 拒绝
        data = deepcopy(self.live)
        data["ability"][M.ABILITY6].append(list(data["ability"][f"{M.CID}1"][2]))
        with self.assertRaisesRegex(M.KyleBalanceCError, "switch rows drift"):
            M.switch_basis(self._abilities(data), data["leader"][M.CID], data["action"][M.CODE])
        for col, value in ((6, "0"), (70, "change_skill_2_kyle_moon"), (47, "704")):
            data = deepcopy(self.live)
            data["ability"][f"{M.CID}1"][2][col] = value
            with self.assertRaises(M.KyleBalanceCError, msg=f"c{col}"):
                M.switch_basis(self._abilities(data), data["leader"][M.CID], data["action"][M.CODE])
        data = deepcopy(self.live)
        data["ability"][f"{M.CID}1"][1][51] = data["ability"][f"{M.CID}1"][1][52] = "40000"
        with self.assertRaisesRegex(M.KyleBalanceCError, "strength"):
            M.switch_basis(self._abilities(data), data["leader"][M.CID], data["action"][M.CODE])
        data = deepcopy(self.live)
        data["action"][M.CODE][0][1][0] = "月华连斩"
        with self.assertRaisesRegex(M.KyleBalanceCError, "skill name"):
            M.switch_basis(self._abilities(data), data["leader"][M.CID], data["action"][M.CODE])

    def test_entry_content_matches_the_flag_branches(self):
        """条目内容 = 旗号 1 开支：两档技能树（队伍贯穿 / 直接攻击伤害提升 / 加速；最近敌人消除强化 + 冻结）与天雷树强化档。"""
        live = batch2_live()
        trees = [live["dsl"][program] for program in M2.SKILL_PROGRAMS.values()]
        self.assertEqual(M.switch_tree_problems(trees, live["dsl"][M2.THUNDER_PROGRAM]), [])
        for phrase in M.SWITCH_TREE_FACTS:
            self.assertIn(phrase, M.NEW_SWITCH_TEXT)
        broken = deepcopy(trees)
        flag, = M._flag_nodes(broken[0])
        flag[2][1].pop()                                                         # 去掉最近敌人那块
        self.assertTrue(M.switch_tree_problems(broken, live["dsl"][M2.THUNDER_PROGRAM]))
        self.assertTrue(M.switch_tree_problems(trees, trees[0]))                 # 天雷树换成技能树 ⇒ 没有两档攻击

    @unittest.skipUnless(_baseline_available(), "需要 live store")
    def test_entry_content_matches_the_live_trees(self):
        import wf_midautumn_common as MC
        import wf_midautumn_specs as MS
        import wf_seasonal7_build as B
        ctx = B.KitContext(MC.MAPack(MS.get_spec("kyle"), record_sources=False))
        read = lambda program: wf_dsl.parse_dsl(zlib.decompress(ctx.live_read(wf_dsl.dsl_logical(program)), -15))["tree"]  # noqa: E731
        trees = [read(program) for program in M2.SKILL_PROGRAMS.values()]
        self.assertEqual(M.switch_tree_problems(trees, read(M2.THUNDER_PROGRAM)), [])

    def test_skill_description_carries_no_enhanced_effect(self):
        """R3：技能描述只写技能本体（强化状态 = 技能自带的「月狼·觉」，不是旗号）；本轮不改、不返回。"""
        for _inner, fields in self.live["action"][M.CODE]:
            for word in ("冻结", "贯穿", "加速", "共鸣", "不受此限", "担任队长", "强化后"):
                self.assertNotIn(word, fields[1])
        for kind in ("text", "action", "server_text"):
            self.assertEqual(self.out[kind], {}, kind)


class DslTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old, cls.new = cls.live["dsl"][M.PIERCE_PROGRAM], cls.out["dsl"][M.PIERCE_PROGRAM]

    def test_pierce_growth_is_uncapped_back_to_99(self):
        self.assertEqual(_pierce_bind(self.old), ["BindConditionAccumulationVariable", -17, 1,
                                                  ["DCUnique", int(M.UID_CRESCENT)], 1, 10])
        self.assertEqual(_pierce_bind(self.new), ["BindConditionAccumulationVariable", -17, 1,
                                                  ["DCUnique", int(M.UID_CRESCENT)], 1, 99])
        self.assertIs(type(_pierce_bind(self.new)[5]), int)                # int 99，与第二批前同类型
        self.assertEqual(self.new[11][1][1][1][2][0][2], M.PIERCE_TIMES)    # 段数 = 1 + vlv（每层 +1）不变
        reverted = deepcopy(self.new)
        _pierce_bind(reverted)[5] = 10
        self.assertEqual(reverted, self.old)

    def test_pierce_tree_is_byte_identical_to_the_pre_batch2_live(self):
        before_b = load_fixture(FIXTURE_B)["dsl"][M.PIERCE_PROGRAM]
        self.assertEqual(self.new, before_b)
        self.assertEqual(encode_tree(self.new), encode_tree(before_b))

    def test_ceiling_equals_the_crescent_unique_cap(self):
        self.assertEqual(_pierce_bind(self.new)[5], int(K.NO_CAP))
        crescent = next(entry for entry in K.UNIQUES if entry[0] == M.UID_CRESCENT)
        self.assertEqual(int(crescent[3]), M.CRESCENT_UNIQUE_CAP)

    def test_tree_passes_the_dsl_gates_and_roundtrip(self):
        tree = self.new
        self.assertEqual(M.dsl_problems(tree), [])
        self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [])
        self.assertEqual(L.action_dsl_subject_binding_problems(tree), [])
        self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [])
        self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [])
        self.assertEqual(PH.signature_problems(tree), [])
        self.assertEqual(PH.expr_tag_problems(tree), [])
        raw = encode_tree(tree)
        self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], tree)
        self.assertEqual(K._dsl_problems(tree), [])

    def test_structure_guard_rejects_its_own_output(self):
        with self.assertRaises(M.KyleBalanceCError):
            M.pierce_tree(self.new)
        tree = deepcopy(self.old)
        tree[11][1][1][1][2][0][2] = [{"min": 1, "max": 1}]               # 段数不再随层数成长
        with self.assertRaises(M.KyleBalanceCError):
            M.pierce_tree(tree)


class Ability3Tests(unittest.TestCase):
    """U1 不加旗号的前提：追击 629 只由「仅队长（前置 42）+ 雷共鸣」的能力3 两行调用。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()

    def test_pierce_callers_are_leader_only_and_resonance_gated(self):
        checks = M.ability3_checks(self.live["ability"][M.ABILITY3])
        self.assertEqual(checks["pierce_callers"], [f"{M.ABILITY3}#4", f"{M.ABILITY3}#5"])
        self.assertEqual(checks["triggers"], ["23", "20"])

    def test_gate_drift_is_rejected(self):
        for col, value in ((6, "0"), (13, "0"), (18, "Red"), (17, "300000")):
            rows = deepcopy(self.live["ability"][M.ABILITY3])
            next(r for r in rows if r[70] == M.CAS_PIERCE)[col] = value
            with self.assertRaises(M.KyleBalanceCError, msg=f"c{col}"):
                M.ability3_checks(rows)
        rows = deepcopy(self.live["ability"][M.ABILITY3])
        rows.append(list(next(r for r in rows if r[70] == M.CAS_PIERCE)))   # 多一个调用方
        with self.assertRaises(M.KyleBalanceCError):
            M.ability3_checks(rows)

    @unittest.skipUnless(_baseline_available(), "需要 live store")
    def test_no_other_live_ability_or_leader_row_invokes_the_pierce_tree(self):
        import wf_midautumn_common as MC
        import wf_midautumn_specs as MS
        import wf_seasonal7_build as B
        ctx = B.KitContext(MC.MAPack(MS.get_spec("kyle"), record_sources=False))
        hits = []
        for table in (KL.ABILITY, KL.LEADER):
            for key, text in ctx.live_flat(table).items():
                if M.CAS_PIERCE in text or M.PIERCE_PROGRAM in text:
                    hits.append((table, key, sum(1 for r in ctx.csv_split(text)
                                                 if M.CAS_PIERCE in r or M.PIERCE_PROGRAM in r)))
        self.assertEqual(hits, [(KL.ABILITY, M.ABILITY3, 2)])


class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_native_legality_gates_are_empty(self):
        cas_keys = set(K.CAS_TEXTS)
        for index, row in enumerate(self.out["leader"][M.CID]):
            label = f"leader#{index}"
            self.assertEqual(L.client_legality_problems("leader_ability", row), [], label)
            self.assertEqual(L.declared_block_field_problems("leader_ability", row), [], label)
            self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, kind="leader_ability"), [], label)
            self.assertEqual(L.required_client_capabilities("leader_ability", row),
                             L.required_client_capabilities("leader_ability", self.live["leader"][M.CID][index]),
                             label)
            self.assertEqual(KL.row_problems("leader_ability", row, K.ELEMENT), {}, label)
            self.assertEqual(M.row_problems("leader_ability", row), [], label)

    def test_changed_rows_render_the_baked_describe(self):
        leader = self.out["leader"][M.CID]
        for index in M.LEADER_EDITS:
            self.assertEqual(KL.describe("leader_ability", leader[index]), K.EXPECT[f"leader#{index}"])

    def test_leader_table_keeps_to_vetted_kinds(self):
        """队长表不新增行、不引入新 kind（C7050）：kind 集合与输入相同。"""
        kinds = lambda rows: sorted((r[25], r[45], r[95], r[107]) for r in rows)  # noqa: E731
        self.assertEqual(kinds(self.out["leader"][M.CID]), kinds(self.live["leader"][M.CID]))
        K._ban_kinds("leader_ability", self.out["leader"][M.CID], "leader")


class SafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["leader"][M.CID][0][0] = "mutated"
        out["cas"][M.CAS_LEADER][0][0] = "mutated"
        _pierce_bind(out["dsl"][M.PIERCE_PROGRAM])[5] = 0
        self.assertEqual(data, self.live)

    def test_revise_is_deterministic(self):
        self.assertEqual(M.revise(reader(deepcopy(self.live))), self.out)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.live)
            if kind == "cas":
                data[kind][key][0][0] += "。"
            elif kind == "dsl":
                data[kind][key][1] = 1
            else:
                data[kind][key][-1][1] = "drift"
            with self.assertRaisesRegex(M.KyleBalanceCError, "unreviewed live baseline"):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        for kind in ("leader", "cas", "dsl"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaises(M.KyleBalanceCError):
            M.revise(reader(data))
        with self.assertRaises(M.KyleBalanceCError):
            M.leader_rows(self.out["leader"][M.CID])
        with self.assertRaises(M.KyleBalanceCError):
            M.leader_text(self.out["cas"][M.CAS_LEADER])
        for key in (M.CAS_ABILITY1, M.CAS_ABILITY2, M.CAS_ABILITY3, M.CAS_ABILITY6):
            with self.assertRaises(M.KyleBalanceCError):
                M.panel_text(key, self.out["cas"][key])
        with self.assertRaises(M.KyleBalanceCError):
            M.switch_text(M.CAS_SWITCH, self.out["cas"][M.CAS_SWITCH])


class ChainTests(unittest.TestCase):
    """第三轮排在第二批之后：第二批 revise() 的输出 == 第三轮的 live 输入。"""

    def test_batch2_output_is_the_batch3_input(self):
        live_b = load_fixture(FIXTURE_B)
        out_b = M2.revise(reader(deepcopy(live_b)))
        live = load_fixture()
        self.assertEqual(out_b["leader"][M.CID], live["leader"][M.CID])
        self.assertEqual(out_b["cas"][M.CAS_LEADER], live["cas"][M.CAS_LEADER])
        self.assertEqual(out_b["dsl"][M.PIERCE_PROGRAM], live["dsl"][M.PIERCE_PROGRAM])
        self.assertEqual(live_b["ability"][M.ABILITY3], live["ability"][M.ABILITY3])   # 第二批只读，未改
        # C 节补读的能力2 行与能力2 面板 = 第二批输出（能力3 面板第二批不涉及，fixture 取自 live）
        self.assertEqual(out_b["ability"][M.ABILITY2], live["ability"][M.ABILITY2])
        self.assertEqual(out_b["cas"][M.CAS_ABILITY2], live["cas"][M.CAS_ABILITY2])
        self.assertNotIn(M.CAS_ABILITY3, out_b["cas"])

    def test_ability5_input_is_the_first_batch_output(self):
        """D 节补读的能力5（只读依据）= 第一批 revise() 输出（第二批不涉及能力5）。"""
        path = Path(__file__).parent / "fixtures/balance_20260927_kyle.json"
        live1 = load_fixture(path)
        out1 = M1.revise(reader(deepcopy(live1)))
        self.assertEqual(M1.ABILITY_KEY, M.ABILITY5)
        self.assertEqual(out1["ability"][M.ABILITY5], load_fixture()["ability"][M.ABILITY5])

    def test_batch2_keys_outside_this_round_stay_as_batch2_left_them(self):
        """能力2 封顶版（D4）、天雷 / 技能树（第二批 Down）本轮都不返回。"""
        out = M.revise(reader(load_fixture()))
        live = batch2_live()
        for program in (M2.THUNDER_PROGRAM, *M2.SKILL_PROGRAMS.values()):
            self.assertNotIn(program, out["dsl"])
        self.assertNotIn(M2.ABILITY2, out["ability"])
        self.assertEqual([r[102] for r in live["ability"][M2.ABILITY2]], ["10", "10"])

    @unittest.skipUnless((CANDIDATE / "package/manifest.json").is_file(), "candidate ma-kyle missing")
    def test_candidate_equals_the_live_inputs(self):
        """回写前：候选 == 本轮 live 输入；回写后：候选 == live 输入 + 本轮 revise() 输出。"""
        import wf_share_update_codec as X
        root = CANDIDATE / "package/roots/common"
        live = load_fixture()
        if candidate_written_back():
            out = M.revise(reader(deepcopy(live)))
            for kind in ("leader", "cas", "dsl"):
                self.assertLessEqual(set(out[kind]), set(live[kind]), kind)
                live[kind].update(deepcopy(out[kind]))
        tables = {"leader": "master/ability/leader_ability.orderedmap",
                  "ability": "master/ability/ability.orderedmap",
                  "cas": "master/string/custom_ability_string.orderedmap"}
        for kind, logical in tables.items():
            rows = X.unpack((root / logical).read_bytes())
            for key, value in live[kind].items():
                self.assertEqual(X.csv_read(rows[key]), value, f"{kind}:{key}")
        for program, tree in live["dsl"].items():
            raw = (root / wf_dsl.dsl_logical(program)).read_bytes()
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], tree, program)


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_kyle 重跑不能回退本轮改动（也不能回退第二批其余改动）。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_panel_constants_equal_revise_output(self):
        self.assertEqual([[K.PANEL_LEADER]], self.out["cas"][M.CAS_LEADER])
        self.assertEqual(K.CAS_TEXTS[M.CAS_LEADER], K.PANEL_LEADER)
        # C 节：能力2/3 面板省略「雷属性共鸣时：」（数值不动）；能力3 拆行、能力6「冻结」；E 节：能力1 拆出强化条目、
        # 能力6 删强化行、强化条目改官方格式；其余能力面板 == live
        for slot, key in ((1, M.CAS_ABILITY1), (2, M.CAS_ABILITY2), (3, M.CAS_ABILITY3), (6, M.CAS_ABILITY6)):
            self.assertEqual([[K.PANEL_ABILITY[slot]]], self.out["cas"][key], key)
            self.assertEqual(K.CAS_TEXTS[key], K.PANEL_ABILITY[slot])
        self.assertEqual([[K.CAS_TEXTS[K.CAS_SWITCH]]], self.out["cas"][M.CAS_SWITCH])
        self.assertEqual((K.CAS_SWITCH, K.CAS_SWITCH_TEXT, K.SKILL_NAME), (M.CAS_SWITCH, M.NEW_SWITCH_TEXT, M.SKILL_NAME))
        for slot, key in ((4, f"desc_override_{M.CODE}_4"), (5, f"desc_override_{M.CODE}_5")):
            self.assertIn(key, M.PANELS_REVIEWED_UNCHANGED)
        self.assertEqual(set(K.CAS_TEXTS) & set(self.out["cas"]), set(self.out["cas"]))

    def test_plan_constants_equal_revise_output(self):
        leader = self.out["leader"][M.CID]
        for index, (_addr, _src, cells, _e) in enumerate(K.LEADER[:4]):
            self.assertEqual([cells[111], cells[112]], leader[index][111:113], f"leader#{index}")
        self.assertEqual(dict(K.PIERCING_GROWTH), {r[45]: r[49] for r in leader if r[25] == "51"})
        self.assertEqual(K.PIERCE_VAR_CEIL, _pierce_bind(self.out["dsl"][M.PIERCE_PROGRAM])[5])
        self.assertEqual(K.CRESCENT_ABILITY_LIMIT, "10")                   # D4
        for index in M.LEADER_EDITS:
            self.assertEqual(KL.describe("leader_ability", leader[index]), K.EXPECT[f"leader#{index}"])

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_rows_and_trees_equal_revise_output(self):
        import wf_midautumn_common as MC
        import wf_midautumn_specs as MS
        import wf_seasonal7_build as B
        pass  # Imports resolve from this checkout/package, not external source copies.
        import test_midautumn_kit_kyle as T   # 只借用 fake_family 三件（与 kit 测试同一口径）
        live = batch2_live()
        ctx = B.KitContext(MC.MAPack(MS.get_spec("kyle"), record_sources=False))
        built = K.build_rows(ctx)
        self.assertEqual(built["leader"], self.out["leader"][M.CID])
        self.assertEqual(built["ability"][M2.ABILITY2], live["ability"][M2.ABILITY2])
        self.assertEqual(built["ability"][M.ABILITY3], self.live["ability"][M.ABILITY3])
        blade, bolt, trail = T.blade_family(), T.bolt_family(), T.trail_family()
        donor = ctx.template_dsl(f"battle/action/skill/action/rare5/{K.TEMPLATE_CODE}${K.TEMPLATE_CODE}_1")
        pierce, note = K.build_pierce_tree(ctx, donor)
        self.assertEqual(pierce, self.out["dsl"][M.PIERCE_PROGRAM])
        self.assertEqual(note["ceiling"], 99)
        thunder, _ = K.build_thunder_tree(ctx, donor, bolt)
        self.assertEqual(thunder, live["dsl"][M2.THUNDER_PROGRAM])
        for level, program in M2.SKILL_PROGRAMS.items():
            raw = ctx.template_dsl(f"battle/action/skill/action/rare5/{K.TEMPLATE_CODE}${K.TEMPLATE_CODE}_{level}")
            tree, _ = K.mutate_tree(ctx, raw, level)
            tree, _ = ctx.rewrite_effect_refs(tree, blade)
            tree, _ = ctx.rewrite_effect_refs(tree, trail)
            self.assertEqual(tree, live["dsl"][program], level)


class MirrorTests(unittest.TestCase):
    """设计镜像由主会话 ``python mod-tools/wf_balance_20260927c_kyle.py --write`` 落盘（本轮施工不写
    work/character_packs）。落盘前：在内存里同步后验证；落盘后：验证磁盘已同步。"""

    PATHS = (ROOT / M.DESIGN_REL, ROOT / M.PANEL_REL)

    def setUp(self):
        if not all(path.is_file() for path in self.PATHS):
            self.skipTest("midautumn design mirrors missing")
        self.disk = [json.loads(path.read_text(encoding="utf-8")) for path in self.PATHS]
        self.synced = list(M.mirror_updates(*self.disk))

    def test_disk_is_synced_or_pending_exactly_this_round(self):
        pending = M.sync_mirrors(ROOT, write=False)
        written = M.MIRROR_KEY in self.disk[0]["plan"]["rework1"] and M.MIRROR_KEY in self.disk[1]
        if written:
            self.assertEqual(pending, [])
        else:
            self.assertEqual(pending, [str(M.DESIGN_REL), str(M.PANEL_REL)])

    def test_synced_mirrors_match_the_generator(self):
        design, panel = self.synced
        self.assertEqual(K._design_problems(design), [])
        self.assertEqual([line["text"] for line in panel["leader"]["lines"]], K.PANEL_LEADER.split("\n"))
        for entry in panel["abilities"]:
            want = K.PANEL_ABILITY[int(entry["index"])].split("\n")
            self.assertEqual([line["text"] for line in entry["lines"]], [line.replace(K.MAIN_ICON, "") for line in want])
        block = design["plan"]["rework1"][M.MIRROR_KEY]
        self.assertEqual(block["panel_resonance_drops"],
                         {M.CAS_LEADER: ["L4", "L5"], M.CAS_ABILITY2: ["L1"], M.CAS_ABILITY3: ["L4"]})
        self.assertEqual(block["panel_data_corrections"],
                         {M.CAS_LEADER: {"L2": "强化自身冲刺",
                                         "L6": "雷属性共鸣时，自身每获得一次贯穿效果，雷属性角色攻击力＋20%，"
                                               "对处于“眩晕”、“畏缩”状态的敌人造成伤害，额外乘区＋4%"},
                          M.CAS_ABILITY6: {"L2": "雷属性共鸣时，雷属性角色对处于“冻结”状态的敌人造成伤害，额外乘区＋15%"}})
        self.assertEqual(block["panel_splits"],
                         {M.CAS_ABILITY3: {"L1": ["雷属性共鸣时，雷属性角色发动技能时，自身“月牙”＋1层",
                                                  "雷属性共鸣时，雷属性角色每造成100次直击，自身“月牙”＋1层"]}})
        self.assertEqual(block["skill_enhancement"], {
            "cas": {M.CAS_SWITCH: M.NEW_SWITCH_TEXT},
            "panels": {M.CAS_ABILITY1: {"L2": ["雷属性共鸣时，自身技能槽＋50%", "雷属性共鸣时，" + M.NEW_SWITCH_TEXT]},
                       M.CAS_ABILITY6: {"L1": []}}})
        self.assertEqual(block["direct_hit_count"], "1 + min(月牙层数, 99)（第二批封顶 10，本轮恢复）")
        self.assertEqual(block["leader_values"]["piercing"], {"32": "20000", "53": "4000"})
        self.assertEqual(panel[M.MIRROR_KEY]["note"], M.MIRROR_NOTE)

    def test_earlier_batch_blocks_are_kept_and_their_syncs_stay_identity(self):
        design, panel = self.synced
        for rel, old, new in zip(("design", "panel"), self.disk, self.synced):
            for key in set(old) - {"plan", "leader", "abilities", M.MIRROR_KEY}:
                self.assertEqual(new[key], old[key], f"{rel}:{key}")
        # 能力面板：本轮只改能力1（E 节强化条目）/ 能力2 / 能力3（口径 3、共鸣省略、口径 5 拆行）/ 能力6（「冻结」、E 节删行）；
        # 其余槽与磁盘逐字相同
        old_abilities = {int(e["index"]): e for e in self.disk[1]["abilities"]}
        for entry in panel["abilities"]:
            slot = int(entry["index"])
            if slot not in (1, 2, 3, 6):
                self.assertEqual(entry, old_abilities[slot], f"ability {slot}")
        self.assertEqual(design["plan"]["rework1"][M2.MIRROR_KEY],
                         self.disk[0]["plan"]["rework1"][M2.MIRROR_KEY])
        self.assertEqual(design["plan"]["rework1"][M2.MIRROR_KEY]["direct_hit_count"],
                         "1 + min(月牙层数, 10)（DSL 封顶，原 99）")
        # 第二批 / 第一批的镜像同步在本轮同步之后仍是恒等（它们按生成器常量重算，不会把本轮回退）
        self.assertEqual(M2.mirror_updates(design, panel), (design, panel))
        deviations = json.loads((ROOT / M1.DEVIATIONS_REL).read_text(encoding="utf-8"))
        self.assertEqual(M1.mirror_updates(design, panel, deviations), (design, panel, deviations))

    def test_mirror_update_is_idempotent_and_pure(self):
        before = deepcopy(self.disk)
        once = M.mirror_updates(*self.disk)
        self.assertEqual(self.disk, before)
        self.assertEqual(M.mirror_updates(*once), once)


if __name__ == "__main__":
    unittest.main()
