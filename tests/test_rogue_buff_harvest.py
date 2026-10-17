# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_boss_buff_harvest as harvest  # noqa: E402
import wf_dsl  # noqa: E402
import wf_quest_lib as q  # noqa: E402


def _slv(value):
    return [{"min": value, "max": value}]


def _tree(commands):
    return ["ActionDsl", 1, ["None"], False, False, False, False, False,
            False, False, 0, ["Block", [["Command", c] for c in commands]]]


def _condition(subject, ac, *, cancelable=False, reapply=True, hit="None"):
    return ["CreateCondition", subject, [ac], _slv(1), [hit], cancelable,
            reapply, "", None, False, 3, _slv(1), False]


class BossBuffHarvestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_dsl(self, logical: str, tree) -> None:
        path = self.store / q.hashed_rel(logical)
        path.parent.mkdir(parents=True, exist_ok=True)
        co = zlib.compressobj(9, zlib.DEFLATED, -15)
        raw = wf_dsl.encode_amf3(tree)
        path.write_bytes(co.compress(raw) + co.flush())

    def fixture(self):
        prefix = "battle/action/enemy/action/test_boss/test_boss$"
        esdl = "battle/enemy/boss/test_boss.esdl.amf3.deflate"
        # ESDL 只需要像真实资源一样同时携带 action 前缀与动作名；采集器必须
        # 探测双重扩展名，而不是把 .esdl/.action 当最终文件名。
        self.write_dsl(esdl, {"program": prefix,
                              "states": ["buff_reset", "debuff_delete", "missing"]})
        damage = ["ACDirectAttackDamageResistance", _slv(9_999_999),
                  _slv(0.01), _slv(99)]
        debuff = ["ACToleranceOfDebuff", _slv(9_999_999), _slv(1), _slv(99)]
        self.write_dsl(
            prefix + "buff_reset.action.dsl.amf3.deflate",
            _tree([_condition(-17, damage), _condition(-17, damage),
                   _condition(-17, debuff)]))
        element_break = ["ACToleranceOfElement", _slv(9_999_999), 254,
                         _slv(-2), _slv(1)]
        attack_break = ["ACAttackPoint", _slv(9_999_999), _slv(-2), _slv(1)]
        self.write_dsl(
            prefix + "debuff_delete.action.dsl.amf3.deflate",
            _tree([_condition(1, element_break, reapply=False,
                              hit="GenericConditionHitEffect"),
                   _condition(1, attack_break, reapply=False,
                              hit="GenericConditionHitEffect")]))
        return esdl

    def test_harvest_discovers_double_extension_actions_and_normalizes_cards(self):
        esdl = self.fixture()
        report = harvest.harvest_boss(
            "test_boss", store_root=self.store, esdl_logical=esdl)

        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["boss_code"], "test_boss")
        self.assertEqual(report["sources"]["esdl"], [esdl])
        self.assertEqual(
            sorted(a["name"] for a in report["actions"]),
            ["buff_reset", "debuff_delete"])
        self.assertTrue(all(a["logical"].endswith(".action.dsl.amf3.deflate")
                            for a in report["actions"]))

        cards = {c["constructor"]: c for c in report["cards"]}
        direct = cards["ACDirectAttackDamageResistance"]
        self.assertEqual(direct["count"], 2)
        self.assertEqual(direct["strength"], 0.01)
        self.assertEqual(direct["max_accumulation"], 99)
        self.assertEqual(direct["subjects"], [-17])
        self.assertFalse(direct["cancelable"])
        # CreateCondition params[5]=true 是允许同帧相同命令重复落地；官方正靠它叠层。
        self.assertTrue(direct["allow_same_frame_reapply"])

        reward = cards["ACToleranceOfElement"]
        self.assertEqual(reward["element"], 254)
        self.assertEqual(reward["strength"], -2)
        self.assertEqual(reward["subjects"], [1])
        self.assertEqual(reward["actions"], {"debuff_delete": 1})

    def test_json_output_is_deterministic_and_contains_no_raw_tree(self):
        esdl = self.fixture()
        a = harvest.harvest_boss("test_boss", store_root=self.store,
                                 esdl_logical=esdl)
        b = harvest.harvest_boss("test_boss", store_root=self.store,
                                 esdl_logical=esdl)
        encoded = harvest.render_json(a)
        self.assertEqual(encoded, harvest.render_json(b))
        self.assertEqual(json.loads(encoded), a)
        self.assertNotIn('"tree"', encoded)

    def test_missing_action_prefix_fails_loudly(self):
        esdl = "battle/enemy/boss/empty.esdl.amf3.deflate"
        self.write_dsl(esdl, {"states": ["buff_reset"]})
        with self.assertRaisesRegex(ValueError, "action 前缀"):
            harvest.harvest_boss("empty", store_root=self.store,
                                 esdl_logical=esdl)

    def test_cli_stdout_is_utf8_machine_readable_json_on_windows(self):
        esdl = self.fixture()
        completed = subprocess.run(
            [sys.executable, str(Path(harvest.__file__)), "测试首领",
             "--store", str(self.store), "--esdl", esdl],
            capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0,
                         completed.stderr.decode("utf-8", errors="replace"))
        report = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(report["boss_code"], "测试首领")


if __name__ == "__main__":
    unittest.main()
