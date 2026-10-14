# -*- coding: utf-8 -*-
"""推送前数据自检(wf_prepush_check)回归:每项检查先证明干净链不报,再埋雷证明能抓到。"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_prepush_check as pc  # noqa: E402
import wf_quest_lib as q  # noqa: E402

CHAR_TEXT = ["英雄", "HERO", "简介", "称号", "斩击", "造成伤害。", "斩击＋", "造成大伤害。",
             "(None)", "(None)", "队长技", "声优"]


def zone_row(boss: str) -> str:
    cells = ["z", "0"] + ["(None)", "0"] * 10 + ["0"] * 1
    cells += ["0"] * (23 - len(cells))
    cells += ["1", boss] + ["(None)", ""] * 5
    return ",".join(cells)


def quest_row(level: int) -> str:
    cells = ["q"] * 107
    cells[5] = "fd1"
    cells[106] = str(level)
    return ",".join(cells)


def base_tables() -> dict[str, dict]:
    return {
        pc.CHARACTER: {"900001": "hero,1,5,0,Human,,1,Male,hero_sk,(None)"},
        pc.ACTION_SKILL: {"hero_sk": {"1": "斩击,造成伤害。,x", "2": "斩击＋,造成大伤害。,x"}},
        pc.CHARACTER_TEXT: {"900001": ",".join(CHAR_TEXT)},
        pc.ITEM: {"1": "mat,1,素材,icon"},
        pc.ITEM_QUEST_SEARCH: {"1": "7,2,,6,2006,1"},
        pc.EII: {"heal_s": "x,1"},
        pc.EII_LEVEL: {"heal_s": {"1": "x"}},
        "master/battle/field_data.orderedmap": {"fd1": "a,b,zone1"},
        "master/battle/zone.orderedmap": {"zone1": {"1": zone_row("boss_a")}},
        "master/battle/boss/general_boss.orderedmap": {"boss_a": {"40": "r,1", "80": "r,1"}},
        "master/battle/boss/general_boss_variable.orderedmap": {"boss_a": {"80": "v,1"}},
        "master/quest/boss_battle_quest.orderedmap": {"1": quest_row(80)},
    }


def member(logical: str) -> str:
    return pc.member("upload", logical)


class Fixture:
    """假服务端仓:assets/item_ids.json + cdndata + asset-patch(manifest + active)。"""

    def __init__(self, root: Path):
        self.root = root
        self.active = root / "assets" / "asset-patch" / "active"
        self.active.mkdir(parents=True)
        (root / "assets" / "cdndata").mkdir(parents=True)
        (root / "assets" / "item_ids.json").write_text("[1]", "utf-8")
        (root / "assets" / "cdndata" / "character_text.json").write_text(
            json.dumps({"900001": [CHAR_TEXT]}, ensure_ascii=False), "utf-8")
        self.manifest = {"cdn_version": "1.4.2", "patches": []}
        self.add_patch("1.4.1", "1.4.2", base_tables(), "base")

    def add_patch(self, frm: str, to: str, tables: dict, tag: str, seq: int = 1) -> Path:
        name = f"pinball-{frm}-{to}-{seq}-{tag}.zip"
        path = self.active / name
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for logical, node in tables.items():
                zf.writestr(member(logical), q.build_node(node))
        with zipfile.ZipFile(path) as zf:
            files = sorted(zf.namelist())
        blob = path.read_bytes()
        self.manifest["patches"].append({
            "id": tag, "type": "patch", "version": to, "depends_on": frm, "enabled": True,
            "chain": [name], "archive_integrity": [{
                "name": name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(),
                "members": len(files), "files": files}]})
        self.manifest["cdn_version"] = to
        self.save()
        return path

    def save(self):
        (self.root / "assets" / "asset-patch" / "manifest.json").write_text(
            json.dumps(self.manifest, ensure_ascii=False, indent=1), "utf-8")


class PrepushCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.fx = Fixture(Path(tmp.name) / "server")
        self.out = Path(tmp.name) / "report.json"

    def run_check(self, *extra) -> tuple[int, list[dict]]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = pc.main(["--server-dir", str(self.fx.root), "--json", str(self.out), *extra])
        self.stdout = buf.getvalue()
        return code, json.loads(self.out.read_text("utf-8"))["findings"]

    @staticmethod
    def ids(findings, level=None):
        return {f["fid"] for f in findings if level is None or f["level"] == level}


class CleanChainTest(PrepushCase):
    def test_clean_chain_has_no_errors(self):
        code, findings = self.run_check()
        self.assertEqual(code, 0, self.stdout)
        self.assertEqual(self.ids(findings, "ERROR"), set())
        self.assertIn("等级检查: 1 张 quest 表, 1 个关卡", self.stdout)


class TextTest(PrepushCase):
    def test_server_only_text_edit_is_error(self):
        root = self.fx.root
        git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(git[:3] + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "base"], check=True)
        edited = list(CHAR_TEXT)
        edited[5] = "造成伤害并降低全属性抗性。"           # 只改了服务端文本
        (root / "assets" / "cdndata" / "character_text.json").write_text(
            json.dumps({"900001": [edited]}, ensure_ascii=False), "utf-8")
        code, findings = self.run_check("--git-since", "HEAD", "--only", "text")
        self.assertEqual(code, 1, self.stdout)
        errs = [f for f in findings if f["level"] == "ERROR"]
        self.assertEqual(len(errs), 1, errs)
        self.assertIn("text.drift:服务端 assets/cdndata/character_text.json:900001:1:技能描述", errs[0]["fid"])
        self.assertIn("游戏里看不到", errs[0]["msg"])

    def test_client_character_text_only_edit_is_error(self):
        edited = list(CHAR_TEXT)
        edited[7] = "造成超大伤害。"
        self.fx.add_patch("1.4.2", "1.4.3", {pc.CHARACTER_TEXT: {"900001": ",".join(edited)}}, "text")
        code, findings = self.run_check("--since", "1.4.2", "--only", "text")
        self.assertEqual(code, 1, self.stdout)
        self.assertIn("text.drift:客户端 character_text 表:900001:2:技能描述", self.ids(findings, "ERROR"))

    def test_action_skill_partial_tier_warns(self):
        skills = {"hero_sk": {"1": "斩击,造成伤害并眩晕。,x", "2": "斩击＋,造成大伤害。,x"}}
        self.fx.add_patch("1.4.2", "1.4.3", {pc.ACTION_SKILL: skills}, "skill")
        code, findings = self.run_check("--since", "1.4.2", "--only", "text")
        self.assertIn("text.partial_tier:hero_sk", self.ids(findings, "WARN"))
        # 改的是真正生效的表,不该当成改错表
        self.assertEqual(self.ids(findings, "ERROR"), set())
        self.assertEqual(code, 0)


class CompanionTest(PrepushCase):
    def test_new_item_without_companion_rows(self):
        items = {"1": "mat,1,素材,icon", "10000400": "mod_boss_coin,10000400,自制领主币,icon"}
        self.fx.add_patch("1.4.2", "1.4.3", {pc.ITEM: items}, "coin")
        code, findings = self.run_check("--since", "1.4.2", "--only", "companion")
        self.assertEqual(code, 1, self.stdout)
        self.assertIn("companion.item_ids:10000400", self.ids(findings, "ERROR"))
        self.assertIn("companion.item_quest_search:10000400", self.ids(findings, "WARN"))

    def test_item_quest_search_exempt_by_allowlist(self):
        items = {"1": "mat,1,素材,icon", "10000400": "mod_boss_coin,10000400,自制领主币,icon"}
        self.fx.add_patch("1.4.2", "1.4.3", {pc.ITEM: items}, "coin")
        allow = self.fx.root / "allow.json"
        allow.write_text(json.dumps({"ids": ["companion.item_ids:10000400"],
                                     "item_quest_search_exempt": [10000400]}), "utf-8")
        code, findings = self.run_check("--since", "1.4.2", "--only", "companion", "--allowlist", str(allow))
        self.assertEqual(code, 0, self.stdout)
        self.assertNotIn("companion.item_quest_search:10000400", self.ids(findings))

    def test_instant_item_without_level_row_is_c8601(self):
        self.fx.add_patch("1.4.2", "1.4.3", {pc.EII: {"heal_s": "x,1", "wf_dummy_charge": "x,2"}}, "eii")
        code, findings = self.run_check("--only", "companion")
        self.assertEqual(code, 1)
        self.assertIn("companion.eii_level:wf_dummy_charge", self.ids(findings, "ERROR"))


class LevelTest(PrepushCase):
    def test_quest_level_above_boss_table_is_gap(self):
        self.fx.add_patch("1.4.2", "1.4.3",
                          {"master/quest/boss_battle_quest.orderedmap": {"1": quest_row(100)}}, "lv100")
        code, findings = self.run_check("--since", "1.4.2", "--only", "level")
        self.assertEqual(code, 1, self.stdout)
        errs = self.ids(findings, "ERROR")
        self.assertIn("level.gap:general_boss:boss_a", errs)
        self.assertIn("level.var_gap:general_boss_variable:boss_a", errs)
        gap = next(f for f in findings if f["fid"] == "level.gap:general_boss:boss_a")
        self.assertIn("最高 80 < 关卡等级 100", gap["msg"])
        self.assertIn("boss_battle_quest:1", gap["detail"][0])

    def test_gap_already_present_before_since_is_warn(self):
        self.fx.add_patch("1.4.2", "1.4.3",
                          {"master/quest/boss_battle_quest.orderedmap": {"1": quest_row(100)}}, "lv100")
        self.fx.add_patch("1.4.3", "1.4.4", {pc.ITEM: {"1": "mat,1,素材,icon"}}, "noop")
        code, findings = self.run_check("--since", "1.4.3", "--only", "level")
        self.assertEqual(code, 0, self.stdout)
        self.assertIn("level.gap:general_boss:boss_a", self.ids(findings, "WARN"))

    def test_candidate_extra_zip_fixes_gap(self):
        self.fx.add_patch("1.4.2", "1.4.3",
                          {"master/quest/boss_battle_quest.orderedmap": {"1": quest_row(100)}}, "lv100")
        fix = self.fx.root / "candidate.zip"
        with zipfile.ZipFile(fix, "w") as zf:
            zf.writestr(member("master/battle/boss/general_boss.orderedmap"), q.build_node(
                {"boss_a": {"40": "r,1", "80": "r,1", "100": "r,1"}}))
            zf.writestr(member("master/battle/boss/general_boss_variable.orderedmap"), q.build_node(
                {"boss_a": {"80": "v,1", "100": "v,1"}}))
        code, findings = self.run_check("--only", "level", "--extra-zip", str(fix))
        self.assertEqual(code, 0, self.stdout)
        self.assertFalse(any(f["fid"].startswith("level.") and "gap" in f["fid"] for f in findings))


class ChainTest(PrepushCase):
    def test_manifest_mismatch_is_error(self):
        self.fx.add_patch("1.4.2", "1.4.3", {pc.ITEM: {"1": "mat,1,素材,icon"}}, "x")
        ent = self.fx.manifest["patches"][-1]
        ent["version"] = "1.4.4"
        ent["archive_integrity"][0]["sha256"] = "0" * 64
        self.fx.manifest["cdn_version"] = "1.4.9"
        self.fx.save()
        (self.fx.active / "pinball-1.4.3-1.4.4-1-stray.zip").write_bytes(
            (self.fx.active / ent["chain"][0]).read_bytes())
        code, findings = self.run_check("--only", "chain")
        self.assertEqual(code, 1)
        errs = self.ids(findings, "ERROR")
        name = ent["chain"][0]
        self.assertIn(f"chain.entry_version:{name}", errs)
        self.assertIn(f"chain.sha256:{name}", errs)
        self.assertIn("chain.cdn_version", errs)
        self.assertIn("chain.unlisted:pinball-1.4.3-1.4.4-1-stray.zip", self.ids(findings, "WARN"))

    def test_undecodable_master_table_is_error(self):
        name = "pinball-1.4.2-1.4.3-1-broken.zip"
        with zipfile.ZipFile(self.fx.active / name, "w") as zf:
            zf.writestr(member(pc.ITEM), b"\x10\x00\x00\x00not-an-orderedmap")
        code, findings = self.run_check("--only", "chain")
        self.assertIn(f"chain.decode:{name}:{pc.ITEM}", self.ids(findings, "ERROR"))

    @unittest.skipIf(shutil.which("node") is None, "node 不可用")
    def test_delegates_order_checks_to_kulo35(self):
        js = self.fx.root / "out" / "routes" / "cn" / "asset.js"
        js.parent.mkdir(parents=True)
        js.write_text(
            "console.log('[TIME] noise from module load');\n"
            "exports.checkPatchChainIntegrity = (pub, disk) =>"
            " pub.filter(n => !disk.includes(n)).map(n => 'listed archive missing from active directory: ' + n);\n",
            "utf-8")
        self.fx.manifest["patches"][0]["chain"].append("pinball-1.4.1-1.4.2-2-gone.zip")
        self.fx.save()
        code, findings = self.run_check("--only", "chain")
        self.assertEqual(code, 1)
        self.assertIn("chain.kulo35:listed archive missing from active directory: pinball-1.4.1-1.4.2-2-gone.zip",
                      self.ids(findings, "ERROR"))

    def test_missing_kulo35_build_is_reported_not_silent(self):
        code, findings = self.run_check("--only", "chain")
        self.assertIn("chain.kulo35.skipped", self.ids(findings, "WARN"))


if __name__ == "__main__":
    unittest.main()
