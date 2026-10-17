# -*- coding: utf-8 -*-
'装备列表置顶数据工具 wf_weapon_sort_pin（方案 ${WF_ROOT}/out/武器置顶-20260928/方案.md「目标顺序」与 B「数据」）。\n\nlive（store）只读；暂存只写临时目录。live 已上线这 46 行后再跑，断言按 live 状态分支，仍然成立；\n门禁另有合成 live（多一行 / 少装备 / 重复序号）用例保证有牙。\n'
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import wf_client_legality as L  # noqa: E402
import wf_share_update_codec as codec  # noqa: E402
import wf_weapon_gacha as G  # noqa: E402
import wf_weapon_sort_pin as S  # noqa: E402
from wf_weapon_gacha import core  # noqa: E402


class OverlayLive(G.Live):
    """live + 若干逻辑文件换成给定字节（已上线 / 合成状态）；equipment_drop 从装备表里拿掉这些 ID。"""

    def __init__(self, extra: dict | None = None, equipment_drop=()):
        super().__init__()
        self.extra = extra or {}
        self.equipment_drop = {str(x) for x in equipment_drop}

    def raw(self, logical, root="upload"):
        if root == "upload" and logical in self.extra:
            return self.extra[logical]
        return super().raw(logical, root)

    def flat(self, logical):
        rows = super().flat(logical)
        if logical == S.EQUIPMENT_LOGICAL and self.equipment_drop:
            return {k: v for k, v in rows.items() if k not in self.equipment_drop}
        return rows


def cas_with(raw: bytes, upsert: dict) -> bytes:
    staged, _changed, _deleted = G.repack(raw, {k: core.write_csv_lines([v]) for k, v in upsert.items()})
    return staged


def decoded(raw: bytes) -> dict:
    return {k: core.read_csv_lines(zlib.decompress(v).decode("utf-8"))[0] if v else []
            for k, v in codec.unpack(raw).items()}


class ContractTests(unittest.TestCase):
    """不需要 live 的合同常量。"""

    def test_pin_values_follow_the_plan(self):
        self.assertEqual(46, len(S.PINS))
        self.assertEqual(1000, S.PINS[5920001])
        self.assertEqual(list(range(2001, 2030)), [S.PINS[e] for e in range(5910101, 5910130)])
        self.assertEqual(list(range(3001, 3016)), [S.PINS[e] for e in range(8000101, 8000116)])
        self.assertEqual(3100, S.PINS[5900101])
        order = S.pin_order()
        self.assertEqual([5920001, *range(5910101, 5910130), *range(8000101, 8000116), 5900101], order)
        # 死亡使者的 ID 比深渊小，只按 ID 分档会排到深渊前面：必须显式序号
        self.assertLess(5900101, 8000101)
        self.assertGreater(S.PINS[5900101], max(S.PINS[e] for e in range(8000101, 8000116)))

    def test_rows_are_single_cell_canonical_and_owned_by_the_capability(self):
        rows = S.cas_rows()
        self.assertEqual(46, len(rows))
        self.assertEqual({"equipment_sort_pin_5920001": ["1000"], "equipment_sort_pin_5900101": ["3100"]},
                         {k: rows[k] for k in ("equipment_sort_pin_5920001", "equipment_sort_pin_5900101")})
        for key, row in rows.items():
            self.assertEqual(1, len(row), key)
            self.assertEqual([], L.equipment_key_problems(key, row[0]), key)
            self.assertEqual(L.EQUIPMENT_SORT_PIN, L.equipment_key_capability(key), key)
            self.assertEqual([L.EQUIPMENT_SORT_PIN],
                             L.required_client_capabilities(L.CUSTOM_ABILITY_STRING_KIND, [key]), key)
        self.assertEqual("equipment_sort_pin_", S.PREFIX)
        self.assertEqual("equipment-sort-pin-v1", S.CAPABILITY)
        self.assertEqual([], S.contract_problems())

    def test_contract_gate_has_teeth(self):
        rows = S.cas_rows()
        dup = dict(rows, **{"equipment_sort_pin_5910102": ["2001"]})
        self.assertTrue(any("重复" in p for p in S.contract_problems(dup)))
        for bad in ("02001", "+2001", " 2001", "2001.0", "0", "-1", "", "1000000000", "2e3"):
            broken = dict(rows, **{"equipment_sort_pin_5910101": [bad]})
            self.assertTrue(S.contract_problems(broken), bad)
        two_cells = dict(rows, **{"equipment_sort_pin_5910101": ["2001", "x"]})
        self.assertTrue(S.contract_problems(two_cells))
        short = {k: v for k, v in rows.items() if k != "equipment_sort_pin_5900101"}
        self.assertTrue(any("46" in p for p in S.contract_problems(short)))
        bad_key = dict(rows, **{"equipment_sort_pin_05910101": ["2100"]})
        self.assertTrue(S.contract_problems(bad_key))


class LiveTests(unittest.TestCase):
    """真实 live（只读）。"""

    @classmethod
    def setUpClass(cls):
        from external_sources import require_live_store
        require_live_store()
        cls.live = G.Live()
        cls.raw = cls.live.raw(S.CAS_LOGICAL)
        cls.raw_sha = hashlib.sha256(cls.raw).hexdigest()
        cls.live_rows = decoded(cls.raw)

    def test_build_is_clean_against_live(self):
        out = S.build(self.live)
        self.assertEqual([], out["problems"])
        missing = {k for k, row in S.cas_rows().items() if self.live_rows.get(k) != row}
        if missing:
            staged, changed, deleted = out["tables"][S.CAS_LOGICAL]
            self.assertEqual(missing, set(changed))
            self.assertEqual([], deleted)
        else:
            self.assertEqual({}, out["tables"])
        self.assertEqual(46, out["report"]["pins"])
        self.assertEqual(S.CAPABILITY, out["report"]["capability"])

    def test_stage_writes_only_the_workdir_and_the_gacha_plan_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "w"
            result = S.stage(work, self.live)
            self.assertFalse(result["refused"], result)
            plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
            self.assertEqual({"tables", "files", "server", "deleted"}, set(plan))
            self.assertEqual(({}, {}, {}), (plan["files"], plan["server"], plan["deleted"]))
            if plan["tables"]:
                self.assertEqual([S.CAS_LOGICAL], list(plan["tables"]))
                info = plan["tables"][S.CAS_LOGICAL]
                self.assertEqual({"changed", "live_sha256", "staged_sha256"}, set(info))
                self.assertEqual(self.raw_sha, info["live_sha256"])
                staged = (work / "stage/common" / S.CAS_LOGICAL).read_bytes()
                self.assertEqual(info["staged_sha256"], hashlib.sha256(staged).hexdigest())
                rows = decoded(staged)
                for key, row in S.cas_rows().items():
                    self.assertEqual(row, rows[key], key)
                # 本工具之外的键逐字节不动、顺序不变
                before, after = codec.unpack(self.raw), codec.unpack(staged)
                self.assertEqual([k for k in before], [k for k in after if k in before])
                self.assertEqual({k: v for k, v in before.items() if k not in S.cas_rows()},
                                 {k: v for k, v in after.items() if k in before and k not in S.cas_rows()})
                self.assertEqual(sorted(info["changed"]), sorted(set(after) - set(before)
                                                                 | {k for k in before if k in S.cas_rows()
                                                                    and before[k] != after[k]}))
                # 幂等：把暂存结果当作已上线再跑 → 空 plan
                again = S.build(OverlayLive({S.CAS_LOGICAL: staged}))
                self.assertEqual(([], {}), (again["problems"], again["tables"]))
                self.assertEqual(46, again["report"]["already_live"])
            self.assertEqual(self.raw_sha, hashlib.sha256(self.live.path(S.CAS_LOGICAL).read_bytes()).hexdigest())

    def test_stray_key_in_live_is_refused_and_nothing_is_written(self):
        extra = cas_with(self.raw, {"equipment_sort_pin_5100020": ["1"]})
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "w"
            result = S.stage(work, OverlayLive({S.CAS_LOGICAL: extra}))
            self.assertTrue(result["refused"])
            self.assertTrue(any("合同外" in p for p in result["problems"]))
            self.assertFalse(work.exists())

    def test_missing_equipment_is_refused(self):
        out = S.build(OverlayLive(equipment_drop=[5910129]))
        self.assertTrue(any("5910129" in p for p in out["problems"]))

    def test_changed_live_value_is_restaged_with_a_warning(self):
        extra = cas_with(self.raw, {**S.cas_rows(), "equipment_sort_pin_5920001": ["999"]})
        out = S.build(OverlayLive({S.CAS_LOGICAL: extra}))
        self.assertEqual([], out["problems"])
        self.assertEqual(["equipment_sort_pin_5920001"], out["tables"][S.CAS_LOGICAL][1])
        self.assertTrue(any("5920001" in w for w in out["warnings"]))

    def test_live_workdir_is_refused(self):
        with self.assertRaises(SystemExit):
            S.stage(self.live.store / "sort-pin-stage", self.live)


if __name__ == "__main__":
    unittest.main()
