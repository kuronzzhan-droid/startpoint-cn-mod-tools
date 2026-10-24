"""Balance row-edit framework migrated from the 1017 production builder."""
import copy, hashlib, json, os, sys, zlib
from pathlib import Path
from wf.paths import root_path
from .live149 import *
from . import base149
from .stage_all import csv_text
from .dsltools import commands, get, dsl_signature_problems
from .layout import col, name_of
import wf_dsl
import wf_mod_tool as M
from wf_character_revision import encode_tree
import wf_client_legality as L
import wf_describe as D

NL = chr(10)
AB = "master/ability/ability.orderedmap"
LE = "master/ability/leader_ability.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
AS = "master/skill/action_skill.orderedmap"
TX = "master/character/character_text.orderedmap"
UQ = "master/character/unique_condition.orderedmap"
CH = "master/character/character.orderedmap"
SRV_SRC = root_path("out/万圣新角色-20261016/localsrv/assets/cdndata/character_text.json")   # 1.4.221 本地服镜像（只读）


class Framework:
    def __init__(self):
        self.T = {}
        self.ROWS = {}      # (lp,key) -> list[list[str]]（多行叶）
        self.STR = {}       # (lp,key) -> new raw leaf string
        self.DSL = {}
        self.LOG = []
        self.owner = None
        self.SRV = json.loads(SRV_SRC.read_text("utf-8"))
        self.SRV0 = json.loads(SRV_SRC.read_text("utf-8"))

    # ---------- 读
    def table(self, lp):
        if lp not in self.T:
            self.T[lp] = load(lp)
        return self.T[lp]

    def rows(self, lp, key):
        """可变行列表（空行已去掉）。改完不用手动保存。"""
        k = (lp, str(key))
        if k not in self.ROWS:
            v = self.table(lp)[str(key)]
            self.ROWS[k] = [r for r in rows(v) if r]
        return self.ROWS[k]

    def ab(self, key):
        return self.rows(AB, key)

    def le(self, key):
        return self.rows(LE, key)

    def describe(self, lp, key):
        t = "leader_ability" if lp == LE else "ability"
        return [D.describe_line(r, t) for r in self.rows(lp, key)]

    def char(self, cid):
        return row(self.table(CH)[str(cid)])

    def dsl(self, program):
        if program not in self.DSL:
            self.DSL[program] = copy.deepcopy(dsl_tree(program))
        return self.DSL[program]

    def string(self, lp, key):
        k = (lp, str(key))
        if k in self.STR:
            return self.STR[k]
        return self.table(lp)[str(key)]

    # ---------- 写
    def set_string(self, lp, key, new_leaf):
        self.STR[(lp, str(key))] = new_leaf

    def cas_replace(self, key, pairs):
        """custom_ability_string 单格文本的逐段替换；每个 old 必须恰好出现一次。"""
        v = self.string(CAS, key)
        s = rows(v)
        assert len(s) == 1 and len(s[0]) == 1, key
        t = s[0][0]
        for old, new in pairs:
            assert t.count(old) == 1, (key, old, t.count(old))
            t = t.replace(old, new)
        nv = leaf(v, [[t]])
        assert rows(nv)[0] == [t]
        self.set_string(CAS, key, nv)
        return t

    def cas_text(self, key):
        return rows(self.string(CAS, key))[0][0]

    def skill_text(self, cid, code, pairs, levels=("1", "2")):
        """技能描述：action_skill[code][lv] c1 + character_text[cid] c5/c7 + 服务端 cdndata [5]/[7] 同步替换。"""
        g = copy.deepcopy(self.table(AS)[code]) if (AS, code) not in self.STR else json.loads(self.STR[(AS, code)])
        for lv in levels:
            r = row(g[lv])
            t = r[1]
            for old, new in pairs:
                assert t.count(old) == 1, (code, lv, old)
                t = t.replace(old, new)
            r2 = list(r); r2[1] = t
            g[lv] = join(r2) + (NL if g[lv].endswith(NL) else "")
        self.STR[(AS, code)] = json.dumps(g, ensure_ascii=False)
        v = self.string(TX, cid)
        tx = rows(v)[0]
        for c in (5, 7):
            t = tx[c]
            for old, new in pairs:
                if old in t:
                    t = t.replace(old, new)
            tx[c] = t
        self.set_string(TX, cid, join(tx) + (NL if v.endswith(NL) else ""))
        if cid in self.SRV:
            srv = self.SRV[cid][0]
            for c in (5, 7):
                t = srv[c]
                for old, new in pairs:
                    if old in t:
                        t = t.replace(old, new)
                srv[c] = t

    def log(self, msg):
        self.LOG.append(f"[{self.owner}] {msg}" if self.owner else msg)

    # ---------- 汇总
    def touched(self):
        out = {}
        for (lp, k), rs in self.ROWS.items():
            v = self.table(lp)[k]
            nv = leaf(v, rs)
            if nv != v:
                out.setdefault(lp, {})[k] = nv
        for (lp, k), nv in self.STR.items():
            if lp == AS:
                g = json.loads(nv)
                if g != self.table(AS)[k]:
                    out.setdefault(lp, {})[k] = g
            elif nv != self.table(lp)[k]:
                out.setdefault(lp, {})[k] = nv
        return out


def leaf(v, rs):
    s = csv_text(rs)
    return s if v.endswith(NL) else s.rstrip(NL)


def V(x):
    return [{"min": x, "max": x}]


def raw_replace(lp, edits):
    raw, _ = read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    for k, node in edits.items():
        assert q.build_node(load(lp)[k]) == rows0[keys0.index(k)], (lp, k, "原 chunk 不能逐字节重建")
        om.rows[om.keys.index(k)] = q.build_node(node)
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys == keys0
    assert [i for i in range(len(rows0)) if back.rows[i] != rows0[i]] == sorted(keys0.index(k) for k in edits)
    return out
