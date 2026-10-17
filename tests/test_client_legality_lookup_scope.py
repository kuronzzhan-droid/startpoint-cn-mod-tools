# -*- coding: utf-8 -*-
"""ActionDsl 全量 lookup 作用域门禁(C16103)的隔离测试。

新增于 2026-09-21,配套 `wf_client_legality.action_dsl_lookup_scope_problems`
与 `DSL_SUBJECT_LOOKUPS`。

事故:凯尔(139990 `kyle_moon`)的 629 追击树 `ability_skill_kyle_moon_thunder`
把强化分支从常态分支整块克隆后,**绑定位**平移了 +30,但
`CreateReferencePoint` node[1]、`ShowEffect` node[3]、`CreateHitArea` node[2]
这三个**引用位**留在母本的 0/1。既有的 `action_dsl_subject_binding_problems`
用的是手抄子集 `DSL_SUBJECT_CONSUMERS`,里面**没有**这三列,所以门禁全绿,
真机开打即 `[ClientError]:16103:アクション対象のlookupに失敗しました`
(崩溃栈 `Environment/lookup` ×3 = 当前环境 → ConditionalsChangeSkillFlag 环境 → 全局环境)。

三组用例:

1. **最小骨架**(不依赖 store / 官方基线):事故原型必红、修好必绿;
   旧门禁看不见、新门禁看得见(两者的差集就是事故面);内建负数主体不误伤。
2. **变异检验**:对每一个新增的引用位,把值改成未绑定号必须变红;
   改回可见绑定必须变绿 —— 保证不是"写死返回空列表"。
3. **官方正向对照**(缺 `.cdn/cn/archive-common-full` 或 `弹国服/restored` 时跳过):
   官方 1.4.0 全量归档里的全部 `.action.dsl` 必须 **0 报错**。
   有报错 = 作用域模型不对,先修模型再谈修数据。
"""
from __future__ import annotations

import glob
import sys
import unittest
import zipfile
import zlib
from pathlib import Path

MOD_TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD_TOOLS))

import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_mod_tool as core  # noqa: E402

ROOT = core.project_root()
OFFICIAL_ZIPS = ROOT / ".cdn" / "cn" / "archive-common-full"
RESTORED_PATHLIST = ROOT / "弹国服" / "restored" / "_pathlist_restored.txt"


def _cmd(node: list) -> list:
    return ["Command", node]


def _block(*commands: list) -> list:
    return ["Block", list(commands)]


def _dsl(*commands: list) -> list:
    return ["ActionDsl", 2, ["None"], False, False, False, False,
            False, False, False, 0, _block(*commands)]


def _show_effect(subject: int) -> list:
    return ["ShowEffect", "演出", ["SpecifyEffectDirectly", "battle/effect/x/y"],
            subject, ["ForesideOfCharacter"], ["PlayOnlyFirstSequence"], ["AB"],
            0, 0, 0, False, False, ["Some", [{"min": 1, "max": 1}]]]


def _normal_attack(subject: int) -> list:
    return ["CreateNormalAttack", subject, 255, [], [], 49,
            [{"min": 5.0, "max": 5.0}], [{"min": 0, "max": 0}],
            True, False, False, False, False,
            [{"min": 3.6, "max": 3.6}], [{"min": 1.8, "max": 1.8}], ["Coarse"], True]


def _hit_area(subject: int, bind_create: int, bind_area: int, bind_target: int,
              on_hit: list) -> list:
    return ["CreateHitArea", "*", subject, ["AB"], 0, 0, 0, False, True,
            ["Circle", [{"min": 200, "max": 200}]],
            ["Center"], ["Center"], ["Single"],
            ["SpecifyHitAreaLifetimeDirectly", 30],
            ["CalculatedUsingMaxNumOfHits", 5],
            ["Some", [{"min": 5, "max": 5}]],
            False, True, ["None"],
            bind_create, ["Block", []],
            bind_area, bind_target, on_hit,
            4, 0, ["None"]]


def _reference_point(origin: int, bind: int, body: list) -> list:
    return ["CreateReferencePoint", origin, ["AB"], 0, 0, 0, False, False,
            ["Single"], 150, bind, body]


def thunder_branch(near_bind: int, rp_bind: int, area_binds: tuple[int, int, int],
                   *, rp_origin: int, anchor: int) -> list:
    """凯尔强化天雷分支的骨架。

    ``rp_origin``/``anchor`` 就是事故的两个引用位:正确写法是
    ``rp_origin == near_bind``、``anchor == rp_bind``。
    """
    create, area, target = area_binds
    return _cmd(["FindNearSubjects", -18, 1, 49, ["CreateImaginaryTarget", -192],
                 near_bind,
                 _block(_cmd(_reference_point(
                     rp_origin, rp_bind,
                     _block(_cmd(_show_effect(anchor)),
                            _cmd(_hit_area(anchor, create, area, target,
                                           _block(_cmd(_normal_attack(target)))))))))])


class MinimalSkeletonTest(unittest.TestCase):
    def test_correct_branch_passes(self) -> None:
        tree = _dsl(thunder_branch(30, 31, (32, 33, 34), rp_origin=30, anchor=31))
        self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [])

    def test_accident_prototype_is_rejected(self) -> None:
        """绑定位平移了、引用位留在母本的 0/1 —— 真机 C16103 的原型。"""
        tree = _dsl(thunder_branch(30, 31, (32, 33, 34), rp_origin=0, anchor=1))
        problems = L.action_dsl_lookup_scope_problems(tree)
        self.assertEqual(len(problems), 3, problems)
        self.assertTrue(all("16103" in p for p in problems), problems)
        self.assertIn("CreateReferencePoint 主体 node[1]=0", problems[0])
        self.assertIn("ShowEffect 主体 node[3]=1", problems[1])
        self.assertIn("CreateHitArea 主体 node[2]=1", problems[2])

    def test_the_old_gate_is_blind_to_this_accident(self) -> None:
        """回归护栏:旧门禁看不见的那三列,正是本门禁存在的理由。

        旧门禁一旦"顺手"补上这三列,本断言会变红 —— 那时删掉这条用例即可,
        但不能反过来靠放宽新门禁来让它过。
        """
        tree = _dsl(thunder_branch(30, 31, (32, 33, 34), rp_origin=0, anchor=1))
        self.assertEqual(L.action_dsl_subject_binding_problems(tree), [])
        self.assertNotEqual(L.action_dsl_lookup_scope_problems(tree), [])

    def test_builtin_subjects_are_never_flagged(self) -> None:
        for builtin in (-1, -2, -17, -18, -33, 255):
            tree = _dsl(thunder_branch(30, 31, (32, 33, 34),
                                       rp_origin=builtin, anchor=builtin))
            self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [],
                             f"内建主体 {builtin} 不该被判")

    def test_coordinate_system_gh_reference_is_checked(self) -> None:
        """坐标系 ["GH", n] 同样走 Environment.lookup(ActionEvaluator.as:1037)。"""
        good = _show_effect(-18)
        good[6] = ["GH", -18]
        self.assertEqual(L.action_dsl_lookup_scope_problems(_dsl(_cmd(good))), [])
        bad = _show_effect(-18)
        bad[6] = ["GH", 7]
        problems = L.action_dsl_lookup_scope_problems(_dsl(_cmd(bad)))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("坐标系 GH 主体=7", problems[0])


class MutationTest(unittest.TestCase):
    """每个新增引用位都要能单独变红,否则等于没判。"""

    CASES = (
        ("CreateReferencePoint", 1, lambda v: thunder_branch(
            30, 31, (32, 33, 34), rp_origin=v, anchor=31)),
        ("ShowEffect/CreateHitArea", 3, lambda v: thunder_branch(
            30, 31, (32, 33, 34), rp_origin=30, anchor=v)),
    )

    def test_each_lookup_slot_flips_red_and_back(self) -> None:
        for label, _slot, build in self.CASES:
            with self.subTest(label):
                self.assertNotEqual(L.action_dsl_lookup_scope_problems(_dsl(build(99))), [],
                                    f"{label}: 未绑定号 99 必须变红")
        # 改回可见绑定 -> 全绿(证明不是无条件报错)
        self.assertEqual(
            L.action_dsl_lookup_scope_problems(
                _dsl(thunder_branch(30, 31, (32, 33, 34), rp_origin=30, anchor=31))), [])

    def test_lookup_table_covers_every_slot_the_old_table_had(self) -> None:
        """新表只能是旧表的超集 —— 收窄 = 把已经在判的东西放走。"""
        for name, slots in L.DSL_SUBJECT_CONSUMERS.items():
            for slot in slots:
                self.assertIn(slot, L._dsl_lookup_slots(name), f"{name} node[{slot}]")


def _official_available() -> bool:
    return OFFICIAL_ZIPS.is_dir() and RESTORED_PATHLIST.is_file()


@unittest.skipUnless(_official_available(), "需要官方 1.4.0 全量归档与 restored 路径表")
class OfficialCorpusControlTest(unittest.TestCase):
    """官方语料零误报 —— 模型不对就先修模型,不要去改数据。"""

    trees: dict[str, list] = {}

    @classmethod
    def setUpClass(cls) -> None:
        want: dict[str, str] = {}
        for line in RESTORED_PATHLIST.read_text(encoding="utf-8", errors="replace").splitlines():
            logical = line.strip()
            if ".action.dsl" not in logical:
                continue
            digest = core.sha1_path(logical)
            want[f"production/upload/{digest[:2]}/{digest[2:]}"] = logical
        for zip_path in sorted(glob.glob(str(OFFICIAL_ZIPS / "*.zip"))):
            with zipfile.ZipFile(zip_path) as archive:
                for name in archive.namelist():
                    logical = want.get(name)
                    if logical is None:
                        continue
                    try:
                        plain = zlib.decompress(archive.read(name), -15)
                        cls.trees[logical] = wf_dsl.parse_dsl(plain)["tree"]
                    except Exception:  # 归档里的坏块不是本门禁的判据
                        continue

    def test_corpus_is_large_enough_to_mean_something(self) -> None:
        self.assertGreater(len(self.trees), 5000, "语料太小,对照不成立")

    def test_no_official_tree_is_flagged(self) -> None:
        flagged = {path: problems for path, problems in
                   ((p, L.action_dsl_lookup_scope_problems(t)) for p, t in self.trees.items())
                   if problems}
        self.assertEqual(flagged, {}, f"官方语料误报 {len(flagged)} 棵树")

    def test_player_side_trees_are_covered(self) -> None:
        player = [p for p in self.trees if "/action/enemy/" not in p]
        self.assertGreater(len(player), 1000, "玩家侧样本不足")


if __name__ == "__main__":
    unittest.main()
