"""觉醒专属素材(awakening_material_*)与装备列表置顶(equipment_sort_pin_*)两类键的门禁:

- 通用包核验器(wf_midautumn_verify.check_capabilities)必须 BLOCK 形状错误的行
  (键尾不是装备 ID 的规范十进制串、值不是规范正整数、不是一行一格),并按各自的 capability 报需求;
- WFX 能力闸门:觉醒键是 semantic(接收端缺补丁 = 拒绝发布),置顶键是 cosmetic(只警告),
  两者互不覆盖(只装觉醒补丁的客户端仍要为置顶键警告,反之拒绝)。"""
from __future__ import annotations

import csv
import io
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_midautumn_verify as V  # noqa: E402
import wfx_gate as G  # noqa: E402

AWAKEN = "awakening_material_5920001"
PIN = "equipment_sort_pin_5920001"
GOOD = {AWAKEN: "10000311", PIN: "1000"}
NAME = "cas/equipment-behaviour-key-shape"
BOTH = (L.EQUIPMENT_AWAKENING_MATERIAL, L.EQUIPMENT_SORT_PIN)


def quoted(value: str) -> str:
    """wf_mod_tool.write_csv_lines 的写法:csv.writer,含逗号的格自动加引号。"""
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow([value])
    return buf.getvalue()


class _Pack:
    """check_capabilities reads manifest / owned_keys / rows only."""

    def __init__(self, texts, declared):
        self.manifest = {"required_capabilities": list(declared)}
        self._texts = dict(texts)

    def owned_keys(self, logical, root="common"):
        return list(self._texts) if logical == V.CAS else []

    def rows(self, logical, key):
        return V.split_rows(self._texts.get(key, "")) if logical == V.CAS else []


class BehaviourKeyPackGateTest(unittest.TestCase):
    def _run(self, texts, declared=BOTH):
        rep = V.Report()
        V.check_capabilities(_Pack(texts, declared), rep)
        return rep, {c["name"]: c for c in rep.checks}

    def test_well_formed_rows_pass_and_need_both_capabilities(self):
        rep, checks = self._run({key: quoted(value) for key, value in GOOD.items()})
        self.assertTrue(checks[NAME]["pass"], checks[NAME])
        self.assertEqual(sorted(GOOD), checks[NAME]["evidence"]["equipment_behaviour_keys"])
        self.assertEqual(sorted(BOTH), checks["manifest/capability-covers-rows"]["evidence"]["needed"])
        self.assertEqual([], rep.blocking)
        # 外观族检查不认领这两类键
        self.assertEqual([], checks["cas/equipment-enhanced-look-shape"]["evidence"]["enhanced_look_keys"])

    def test_undeclared_capability_blocks(self):
        rep, checks = self._run({key: quoted(value) for key, value in GOOD.items()},
                                declared=(L.EQUIPMENT_SORT_PIN,))
        self.assertFalse(checks["manifest/capability-covers-rows"]["pass"])
        self.assertIn(L.EQUIPMENT_AWAKENING_MATERIAL,
                      "\n".join(checks["manifest/capability-covers-rows"]["evidence"].get("problems", [])))

    def test_malformed_values_and_keys_block(self):
        for texts in ({AWAKEN: quoted("")}, {AWAKEN: quoted("010000311")}, {AWAKEN: quoted("+10000311")},
                      {PIN: quoted("0")}, {PIN: quoted("-1")}, {PIN: quoted("1000.0")}, {PIN: quoted("1,000")},
                      {PIN: quoted("1000") + "\n" + quoted("2000")}, {PIN + " ": quoted("1000")},
                      {"equipment_sort_pin_05920001": quoted("1000")}, {"awakening_material_x": quoted("1")}):
            with self.subTest(texts=texts):
                rep, checks = self._run(texts)
                self.assertFalse(checks[NAME]["pass"])
                self.assertIn(NAME, [c["name"] for c in rep.blocking])


class BehaviourKeyWfxGateTest(unittest.TestCase):
    def setUp(self):
        base = G.load_profiles()["local-mumu"].capabilities - set(BOTH)
        self.none = G.ClientProfile("neither", base)
        self.awaken_only = G.ClientProfile("awaken-only", base | {L.EQUIPMENT_AWAKENING_MATERIAL})
        self.pin_only = G.ClientProfile("pin-only", base | {L.EQUIPMENT_SORT_PIN})
        self.both = G.ClientProfile("both", base | set(BOTH))

    def test_awakening_key_is_refused_without_its_patch(self):
        for profile in (self.none, self.pin_only, "gray-1047", "official"):
            with self.subTest(profile=getattr(profile, "name", profile)):
                report = G.check({}, {}, [AWAKEN], profile)
                self.assertFalse(report.ok)
                self.assertEqual([L.EQUIPMENT_AWAKENING_MATERIAL], report.required_capabilities())
        self.assertTrue(G.check({}, {}, [AWAKEN], self.awaken_only).ok)

    def test_sort_pin_key_only_warns(self):
        for profile in (self.none, self.awaken_only, "gray-1047", "official"):
            with self.subTest(profile=getattr(profile, "name", profile)):
                report = G.check({}, {}, [PIN], profile)
                self.assertTrue(report.ok, report.problems)
                self.assertEqual(1, len(report.warnings))
                self.assertIn(L.EQUIPMENT_SORT_PIN, report.warnings[0])
        self.assertEqual([], G.check({}, {}, [PIN], self.pin_only).warnings)

    def test_candidate_client_is_quiet(self):
        report = G.check({}, {}, list(GOOD), self.both)
        self.assertEqual(([], []), (report.problems, report.warnings))


if __name__ == "__main__":
    unittest.main()
