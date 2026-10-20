# -*- coding: utf-8 -*-
"""DSL 伤害类型「完整转换」(damage-type-rules-v1) 的检测 / 语义核验 / 叠加守门脚本。

结论先行（2026-10-15 核实）：
  这项客户端能力**已经在** v29-coop、v30-perf 和本机 com.leiting.wf 安装基线(installed_base/wf_installed.apk)里，
  由 battle-rules 补丁（canonical 源：D:/WF/out/q1056/rv4p/client-patch/battle-rules/damage.py）实现：
    * Environment/getBuffTargetAs           —— 方法头插入：101/102/104/131/132/133 原样返回（原版 default 分支会丢成 0）
    * ImpactSourceContent$/NormalAttack     —— 方法头插入：param1 = MemberImpl.wfConvertNormalAttack(param1)
    * MemberImpl$/wfConvertNormalAttack     —— battle-rules 新增的静态方法：按标记改写来源标志（独占）并把 buffTargetAs 归 0
    * AbilityTotalizer.wfResolveDamageType  —— 角色级 424 规则（与本需求无关，只在非标记值时被调用）
  官方数据只用 0/4，标记值 ≥101 官方 0 例 ⇒ 官方角色逐字节不受影响；旧 APK 读到 ≥101 走原版 default ⇒ 按 0（自动）结算，不崩。

因此本脚本**不再拼接任何方法**（重复拼接会和 battle-rules 叠层冲突、改变已锁定方法哈希），而是：
  --check  IN.apk|IN.swf ...   锁定上述 3 个方法体 sha256，并用有限指令解释器直接执行 IN 里的真实字节码，
                               核验 0/1/2/3/4 原版行为不变、101/102/104/131-133 完整转换、罗尔夫式「根 0 + 判定区 104」继承链；
                               另确认与 v29-coop(BattleDerailleur/getDeferralLevel)、v30-perf(MasterBinaryMap/getIndex) 无方法重叠。
  --apk IN --out OUT           「应用」入口：已含 → 拒绝（exit 3，already patched，不产出 APK）；
                               原版方法体 → 拒绝（exit 4），请用 battle-rules 构建器（需新增方法/trait，不是单方法拼接）；
                               其他哈希 → 拒绝（exit 5，unknown base）。
用法：
  python wf_damage_type_override.py --check ~/Downloads/世界弹射测试服-v29-coop.apk [--report out.json]
"""
from __future__ import annotations

import argparse, hashlib, json, sys, zipfile
from pathlib import Path

ABCASM = Path(r"D:/WF/startpoint-cn-kulo/client-patch/author-merge-20261001/abcasm")
VMDIR = Path(r"D:/WF/out/q1056/rv4p/client-patch/battle-rules/tests")
sys.path.insert(0, str(ABCASM))
sys.path.insert(0, str(VMDIR))
import asm, bodies  # noqa: E402
from swfabc import SwfAbc  # noqa: E402
from vm import run  # noqa: E402

SWF_MEMBER = "assets/worldflipper_android_release.swf"
CAPABILITY = "damage-type-rules-v1"
# battle-rules 打过之后的方法体（v29-coop / v30-perf / 本机 installed_base 三者逐字节相同）
PRESENT = {
    "Environment/getBuffTargetAs": "3534ccee6777",
    "ImpactSourceContent$/NormalAttack": "9377796ffd22",
    "MemberImpl$/wfConvertNormalAttack": "d75e6f800238",
}
# 其他叠层补丁改的方法 —— 本能力不得与之重叠
OTHER_PATCHES = {"v29-coop": ["BattleDerailleur/getDeferralLevel"], "v30-perf": ["MasterBinaryMap/getIndex"]}
MARKERS = {101: "skill", 102: "ability", 104: "direct", 131: "pf1", 132: "pf2", 133: "pf3"}
FLAGS = ("createdByDirectAttack", "createdByPowerFlipAction", "createdByMainSkillAction",
         "createdByUnisonSkillAction", "createdByAbility", "createdByUnisonAbility", "createdBySkillInvoker")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def load_swf(p: Path) -> tuple[bytes, str]:
    if p.suffix.lower() == ".apk":
        with zipfile.ZipFile(p) as z:
            return z.read(SWF_MEMBER), sha(p.read_bytes())
    return p.read_bytes(), None


def classify(abc) -> dict:
    out = {}
    for lab, want in PRESENT.items():
        try:
            bi = bodies.resolve(abc, lab)
        except Exception:
            out[lab] = {"state": "absent"}
            continue
        got = sha(abc.bodies[bi][5])
        out[lab] = {"body": bi, "sha256": got, "state": "present" if got.startswith(want) else "different"}
    return out


def semantic_checks(abc) -> list[str]:
    """直接执行 IN 里的真实字节码。返回失败列表（空 = 全过）。"""
    bad = []
    getter = asm.decode(abc.bodies[bodies.resolve(abc, "Environment/getBuffTargetAs")][5])
    conv = asm.decode(abc.bodies[bodies.resolve(abc, "MemberImpl$/wfConvertNormalAttack")][5])
    ctor = asm.decode(abc.bodies[bodies.resolve(abc, "ImpactSourceContent$/NormalAttack")][5])
    # NormalAttack 必须先调转换器再构造枚举
    if not (ctor[2].name == "callproperty" and abc.mn_name(ctor[2].args[0]).endswith("wfConvertNormalAttack")
            and ctor[4].name == "setlocal_1"):
        bad.append("ImpactSourceContent.NormalAttack does not route through wfConvertNormalAttack")
    member_t = [abc.mn_name(x.args[0]) for x in conv if x.name == "astype"]

    def env(v, outer=None):
        e = {"buffTargetAs": v, "outerEnvironment": outer}
        e["getBuffTargetAs"] = lambda: run(getter, abc, [e])
        return e

    def bta(e):
        r = e["getBuffTargetAs"]()
        return 0 if r is None else r   # AVM：int 方法 returnvoid → 0

    # 1) getter：原版值、标记值、未知值、继承
    for v in (1, 2, 3, 4, *MARKERS):
        if bta(env(v, env(0))) != v:
            bad.append(f"getBuffTargetAs({v}) != {v}")
    for v in (5, 11, 14, 100, 103, 134, 999):
        if bta(env(v, env(104))) != 0:
            bad.append(f"unknown {v} should read as 0")
    if bta(env(0)) != 0:
        bad.append("root 0 should be 0")
    for v in (4, *MARKERS):   # 判定区/onHit 写 0 = 继承外层，三层嵌套
        e = env(v)
        for _ in range(3):
            e = env(0, e)
        if bta(e) != v:
            bad.append(f"nested inherit {v} lost")
    if bta(env(104, env(0))) != 104:   # 罗尔夫：根 0 + 判定区 104
        bad.append("hit-area 104 over root 0 failed")
    if bta(env(4, env(104))) != 4:
        bad.append("native local 4 must override outer marker")

    # 2) 转换器：DSL 技能命中（ActionSkill/AbilitySkill ⇒ main=true；kind 7 ⇒ invoker=true）
    def attack(v, origin=0, attacker=None):
        a = dict.fromkeys(FLAGS, False)
        a.update(createdByMainSkillAction=origin != 1, createdByUnisonSkillAction=origin == 1,
                 createdBySkillInvoker=True, buffTargetAs=v, powerFlipChargeLv=0, originMemberKind=origin,
                 attacker=attacker, damage=123, multiplierOfAttackPoint=4.5)
        return a
    no_rules = {"_type": member_t[0] if member_t else "?", "abilityTotalizer": {"wfResolveDamageType": lambda k: 0}}
    for v in (0, 1, 2, 3, 4):
        for att in (None, no_rules):
            a = attack(v, attacker=att); b = dict(a)
            if run(conv, abc, [None, a]) is not a or a != b:
                bad.append(f"native buffTargetAs {v} (attacker={'member' if att else None}) was modified")
    want = {101: {"createdByMainSkillAction"}, 102: {"createdByAbility"}, 104: {"createdByDirectAttack"},
            131: {"createdByPowerFlipAction"}, 132: {"createdByPowerFlipAction"}, 133: {"createdByPowerFlipAction"}}
    for v, w in want.items():
        for origin in (0, 1):
            a = attack(v, origin)
            run(conv, abc, [None, a])
            ww = set(w)
            if origin == 1 and v == 101:
                ww = {"createdByUnisonSkillAction"}
            if origin == 1 and v == 102:
                ww = {"createdByAbility", "createdByUnisonAbility"}
            got = {f for f in FLAGS if a[f]}
            if got != ww or a["buffTargetAs"] != 0 or a["powerFlipChargeLv"] != max(0, v - 130) \
                    or a["damage"] != 123 or a["multiplierOfAttackPoint"] != 4.5:
                bad.append(f"marker {v} origin {origin}: flags {sorted(got)} bta {a['buffTargetAs']} lv {a['powerFlipChargeLv']}")
    return bad


def check(path: Path) -> dict:
    data, apk_sha = load_swf(path)
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / "in.swf"
        tmp.write_bytes(data)
        abc = SwfAbc(tmp).abc
    st = classify(abc)
    rep = {"input": str(path), "input_sha256": apk_sha, "swf_sha256": sha(data), "methods": st}
    if all(v["state"] == "present" for v in st.values()):
        rep["state"] = "present"
        rep["semantic_failures"] = semantic_checks(abc)
    elif st["MemberImpl$/wfConvertNormalAttack"]["state"] == "absent":
        rep["state"] = "native"
    else:
        rep["state"] = "unknown"
    ours = set(PRESENT)
    rep["overlap_with_other_patches"] = {k: sorted(ours & set(v)) for k, v in OTHER_PATCHES.items()}
    lm = set(bodies.label_map(abc).values())
    rep["other_patch_methods_exist"] = {m: m in lm for v in OTHER_PATCHES.values() for m in v}
    return rep


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--check", nargs="+")
    p.add_argument("--report")
    p.add_argument("--apk")
    p.add_argument("--out")
    p.add_argument("--signer", choices=("local", "debug"))
    a = p.parse_args()
    if a.check:
        reps = [check(Path(x)) for x in a.check]
        txt = json.dumps({"capability": CAPABILITY, "markers": MARKERS, "results": reps}, ensure_ascii=False, indent=2)
        print(txt)
        if a.report:
            Path(a.report).write_text(txt + "\n", "utf8")
        ok = all(r["state"] == "present" and not r["semantic_failures"] and not any(r["overlap_with_other_patches"].values())
                 for r in reps)
        raise SystemExit(0 if ok else 1)
    if not (a.apk and a.out):
        p.error("--check or --apk/--out required")
    r = check(Path(a.apk))
    if r["state"] == "present":
        print(f"refuse: {a.apk} already contains {CAPABILITY} (all 3 method bodies match); "
              "nothing to apply, no APK written", file=sys.stderr)
        raise SystemExit(3)
    if r["state"] == "native":
        print("refuse: native base. Apply the canonical battle-rules builder "
              "(D:/WF/out/q1056/rv4p/client-patch/battle-rules/patch.py); it adds methods/traits, "
              "which a single-method splice cannot do.", file=sys.stderr)
        raise SystemExit(4)
    print(f"refuse: unknown base, method states {json.dumps(r['methods'])}", file=sys.stderr)
    raise SystemExit(5)


if __name__ == "__main__":
    main()
