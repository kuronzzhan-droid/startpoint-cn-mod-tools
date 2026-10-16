# -*- coding: utf-8 -*-
"""多段直击/凯尔 PF 追加结算的「只首段出表现」客户端补丁（hitfx-silence-v1）。

只做单方法指令级插入（author-merge 的 abcasm：splice + 逐字节可逆校验），不回编 AS3、不动常量池。
两个方法体按 sha256 + header 锁定，对不上即拒绝：

1. MemberImpl/scheduleDirectAttack：每段直击的 ImpactSource.hitEffect，第 2 段起（段下标 _loc11_ != 0）
   改为 Option.None。伤害、段数、计数、触发全部照旧（schedule() 的其余参数不动）。
2. EnemyImpl/applyAttack：在 `lastAttackResult = param1` 之后、伤害数字之前插入提前返回：
   a) 本机主战斗 && createdByDirectAttack && hitEffect == None   → 不弹伤害数字、不播命中特效/受击音效/受击闪烁
   b) hitEffect == Some 且 paths[0] == "battle/common/layer0/attack_to_hostile_hit" 且 randomRotation == false
      （凯尔 PF 追加判定区专用标记；原生直击该路径 randomRotation 恒为 true，全语料 DSL 0 处使用）→ 同上
   扣血、韧性、Fever、统计、词条计数都在插入点之前完成，不受影响。

用法：
  python wf_hitfx_silence.py --apk IN.apk --out OUT.apk --signer local|debug [--work DIR]
  local = 本机 com.leiting.wf（wf_new.keystore，口令取自本机既有构建脚本默认值，只进子进程环境变量）
  debug = 测试服 com.leiting.wt（~/.android/debug.keystore / androiddebugkey）
  每次构建轮换 AndroidManifest 里的 AIR uniqueappversionid（同长 UTF-16 替换），使 AIR 重新解包 SWF。
"""
from __future__ import annotations

import argparse, ast, hashlib, json, os, re, shutil, subprocess, sys, uuid, zipfile
from pathlib import Path

ABCASM = Path(r"D:/WF/startpoint-cn-kulo/client-patch/author-merge-20261001/abcasm")
sys.path.insert(0, str(ABCASM))
import asm, bodies  # noqa: E402
from swfabc import SwfAbc  # noqa: E402

SWF_MEMBER = "assets/worldflipper_android_release.swf"
TOOLS = Path(r"D:/WF/runtimes/android-toolchain/sdk/build-tools/34.0.0")
JAVA_HOME = Path(r"D:/WF/runtimes/android-toolchain/jdk/jdk-17.0.19+10")
LOCAL_KS = Path(r"D:/WF/_archive/kept/弹国服-tools-and-decompile/instrument/wf_new.keystore")
LOCAL_KS_SRC = LOCAL_KS.with_name("build_instrumented_apk.py")
DEBUG_KS = Path(os.path.expanduser("~")) / ".android" / "debug.keystore"
MARKER = b"battle/common/layer0/attack_to_hostile_hit"
CAPABILITY = "hitfx-silence-v1"

LOCKS = {
    "MemberImpl/scheduleDirectAttack": {"sha": "fe24bf97e3da", "header": [110, 38, 1, 2], "at": 477},
    "EnemyImpl/applyAttack": {"sha": "d3bbb8fbe858", "header": [23, 25, 1, 2], "at": 597},
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


class Fail(SystemExit):
    pass


def expect(ins, i, op, name=None, abc=None, arg=None):
    x = ins[i]
    if x.op != asm.MNEMONICS[op]:
        raise Fail(f"anchor #{i}: expected {op}, got {x.name}")
    if name is not None and abc.mn_name(x.args[0]).split("::")[-1].split(":")[-1] != name:
        raise Fail(f"anchor #{i}: expected {op} {name}, got {abc.mn_name(x.args[0])}")
    if arg is not None and x.args[0] != arg:
        raise Fail(f"anchor #{i}: operand {x.args} != {arg}")
    return x.args[0] if x.args else None


def mn_from(abc, label, index, op, name):
    body = abc.bodies[bodies.resolve(abc, label)]
    ins = asm.decode(body[5])
    return expect(ins, index, op, name, abc)


def patch_swf(src: Path, dst: Path) -> dict:
    swf = SwfAbc(src)
    abc = swf.abc
    before_bodies = [bytes(b[5]) for b in abc.bodies]
    pool_before = (len(abc.strings), len(abc.multinames), len(abc.ints))
    idx = {lab: bodies.resolve(abc, lab) for lab in LOCKS}
    for lab, bi in idx.items():
        b = abc.bodies[bi]
        if b[5].find(b"") != 0:
            pass
        got = sha(b[5])
        if b[1:5] != LOCKS[lab]["header"] or not got.startswith(LOCKS[lab]["sha"]):
            # 已打过本补丁？
            raise Fail(f"unknown method baseline for {lab}: sha {got[:12]} header {b[1:5]} (locked {LOCKS[lab]})")
    # ---- 锚点与多名（全部从既有指令里取，不新建常量）
    sd = asm.decode(abc.bodies[idx["MemberImpl/scheduleDirectAttack"]][5])
    option = expect(sd, 461, "getlex", "Option", abc)
    expect(sd, 465, "pushstring", abc=abc, arg=abc.strings.index(MARKER))
    expect(sd, 475, "callproperty", "Some", abc)
    expect(sd, 476, "coerce", "Option", abc)
    expect(sd, 477, "pushstring")
    if abc.strings[sd[477].args[0]] != b"createdByCoopCommand":
        raise Fail("anchor 477 is not createdByCoopCommand")
    none_mn = expect(sd, 350, "getproperty", "None", abc)
    if sd[349].op != asm.MNEMONICS["getlex"] or sd[349].args[0] != option:
        raise Fail("anchor 349 is not getlex Option")
    coerce_option = sd[476].args[0]
    # 段下标 = local 11（循环头 #162-#165：getlocal 9; inclocal_i 9; convert_i; setlocal 11）
    expect(sd, 165, "setlocal", arg=11); expect(sd, 163, "inclocal_i", arg=9)
    ap = asm.decode(abc.bodies[idx["EnemyImpl/applyAttack"]][5])
    expect(ap, 596, "initproperty", "lastAttackResult", abc)
    expect(ap, 597, "getlocal_2"); expect(ap, 598, "getproperty", "shouldShowDamageFont", abc)
    hit_mn = expect(ap, 656, "getproperty", "hitEffect", abc)
    primary_mn = expect(ap, 662, "getproperty", "createdByPrimaryBattle", abc)
    direct_mn = [x.args[0] for x in ap if x.op == 0x66 and abc.mn_name(x.args[0]).endswith("createdByDirectAttack")]
    if len(set(direct_mn)) != 1:
        raise Fail("createdByDirectAttack multiname not unique")
    direct_mn = direct_mn[0]
    index_mn = mn_from(abc, "EnemyImpl/showHitEffect", 3, "getproperty", "index")
    params_mn = mn_from(abc, "EnemyImpl/showHitEffect", 11, "getproperty", "params")
    sh = asm.decode(abc.bodies[bodies.resolve(abc, "EnemyImpl/showHitEffect")][5])
    expect(sh, 12, "pushbyte", arg=0); expect(sh, 13, "getproperty")
    elem_mn = sh[13].args[0]
    if abc.multinames[elem_mn][0] != 0x1B:
        raise Fail("element access multiname is not MultinameL")
    paths_mn = mn_from(abc, "ImpactHitEffectManager/show", 18, "getproperty", "paths")
    rot_mn = mn_from(abc, "ImpactHitEffectManager/show", 48, "getproperty", "randomRotation")
    marker_str = abc.strings.index(MARKER)

    # ---- 插入块
    block_a = [
        ("getlocal", 11), ("pushbyte", 0), ("ifeq", "END"),
        ("pop",), ("getlex", option), ("getproperty", none_mn), ("coerce", coerce_option),
    ]
    hit = [("getlocal_1",), ("getproperty", hit_mn)]
    some0 = hit + [("getproperty", params_mn), ("pushbyte", 0), ("getproperty", elem_mn)]
    block_b = [
        ("getlocal_1",), ("getproperty", primary_mn), ("iffalse", "R2"),
        ("getlocal_2",), ("getproperty", direct_mn), ("iffalse", "R2"),
        *hit, ("getproperty", index_mn), ("pushbyte", 1), ("ifne", "R2"),
        ("returnvoid",),
        ("label", "R2"),
        *hit, ("getproperty", index_mn), ("pushbyte", 0), ("ifne", "END"),
        *some0, ("getproperty", rot_mn), ("iftrue", "END"),
        *some0, ("getproperty", paths_mn), ("pushbyte", 0), ("getproperty", elem_mn),
        ("pushstring", marker_str), ("ifne", "END"),
        ("returnvoid",),
    ]
    report = {}
    for lab, block in (("MemberImpl/scheduleDirectAttack", block_a), ("EnemyImpl/applyAttack", block_b)):
        body = abc.bodies[idx[lab]]
        before = bytes(body[5])
        code, exc, merged, placed = asm.splice_many(body, [(LOCKS[lab]["at"], asm.assemble(block), asm.FORBID)])
        if asm.unsplice_many(code, placed) != before:
            raise Fail("not reversible: " + lab)
        analysis = [asm.Instruction(0x02) if x.op in (0xEF, 0xF0, 0xF1) else x for x in merged]
        metrics = asm.simulate(analysis, body[3], abc.multinames)
        if metrics[1] != body[4]:
            raise Fail("scope depth changed: " + lab)
        if asm.block_locals(merged) > body[2]:
            raise Fail("locals exceeded: " + lab)
        body[1] = max(body[1], metrics[0])
        body[5], body[6] = code, exc
        report[lab] = {"body": idx[lab], "before": sha(before), "after": sha(code), "inserted_at": placed,
                       "header_after": body[1:5], "metrics": list(metrics)}
    # ---- 只改了这两个体、常量池零追加
    changed = [i for i, b in enumerate(abc.bodies) if bytes(b[5]) != before_bodies[i]]
    if sorted(changed) != sorted(idx.values()):
        raise Fail(f"unexpected body changes: {changed}")
    if (len(abc.strings), len(abc.multinames), len(abc.ints)) != pool_before:
        raise Fail("constant pool changed")
    data = swf.serialize()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    back = SwfAbc(dst)
    for lab, bi in idx.items():
        if sha(back.abc.bodies[bi][5]) != report[lab]["after"]:
            raise Fail("readback mismatch " + lab)
    return {"source_swf_sha256": sha(src.read_bytes()), "output_swf_sha256": sha(data),
            "source_abc_sha256": sha(SwfAbc(src).abc.serialize()), "output_abc_sha256": sha(back.abc.serialize()),
            "methods": report, "bodies_total": len(abc.bodies), "bodies_changed": len(changed),
            "constant_pool_added": 0}


def is_sig(name):
    p = name.upper().split("/")
    return len(p) == 2 and p[0] == "META-INF" and (p[1] == "MANIFEST.MF" or p[1].endswith((".RSA", ".SF", ".DSA", ".EC")))


def run(args, env=None):
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding="utf8", errors="replace", env=env)
    if r.returncode:
        raise Fail(f"{Path(str(args[0])).name} failed ({r.returncode}); output withheld (signing inputs)")
    return r.stdout


def signer_env(kind):
    env = os.environ.copy()
    env["JAVA_HOME"] = str(JAVA_HOME)
    env["PATH"] = str(JAVA_HOME / "bin") + os.pathsep + env.get("PATH", "")
    if kind == "debug":
        env["WF_HITFX_KS"] = env["WF_HITFX_KEY"] = "android"   # Android SDK 标准 debug 口令
        return env, ["--ks", DEBUG_KS, "--ks-key-alias", "androiddebugkey"]
    tree = ast.parse(LOCAL_KS_SRC.read_text(encoding="utf8"))
    vals = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"
                and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value in ("--ks-pass", "--ks-key-pass")):
            vals[node.args[0].value] = ast.literal_eval(next(k.value for k in node.keywords if k.arg == "default"))
    ks = (vals.get("--ks-pass") or "").removeprefix("pass:")
    kp = (vals.get("--ks-key-pass") or vals.get("--ks-pass") or "").removeprefix("pass:")
    if not ks:
        raise Fail("local keystore password not found")
    env["WF_HITFX_KS"], env["WF_HITFX_KEY"] = ks, kp or ks
    return env, ["--ks", LOCAL_KS]


def certs(apk, env):
    out = run([TOOLS / "apksigner.bat", "verify", "--verbose", "--print-certs", apk], env)
    d = sorted(set(re.findall(r"certificate SHA-256 digest: ([0-9a-f]{64})", out)))
    if not d:
        raise Fail("no verified certificate")
    return d, {"v1": "Verified using v1 scheme (JAR signing): true" in out,
               "v2": "Verified using v2 scheme (APK Signature Scheme v2): true" in out}


def build(a):
    work = Path(a.work)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    out = Path(a.out)
    if out.exists():
        raise Fail("output exists: " + str(out))
    base = Path(a.apk)
    base_bytes_sha = sha(base.read_bytes())
    env, ksargs = signer_env(a.signer)
    base_certs, _ = certs(base, env)
    src_swf = work / "base.swf"
    with zipfile.ZipFile(base) as z:
        names = z.namelist()
        if names.count(SWF_MEMBER) != 1 or len(set(names)) != len(names):
            raise Fail("missing/duplicate members")
        src_swf.write_bytes(z.read(SWF_MEMBER))
        manifest = z.read("AndroidManifest.xml")
    swf_report = patch_swf(src_swf, work / "patched.swf")
    swf = (work / "patched.swf").read_bytes()
    # AIR uniqueappversionid：清单里同长 UTF-16 替换
    text = manifest.decode("utf-16le", "ignore")
    olds = sorted(set(re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", text)))
    if len(olds) != 1 or manifest.count(olds[0].encode("utf-16le")) != 1:
        raise Fail(f"manifest uniqueappversionid not unique: {olds}")
    new_uid = str(uuid.uuid4())
    manifest2 = manifest.replace(olds[0].encode("utf-16le"), new_uid.encode("utf-16le"))
    unsigned, aligned = work / "unsigned.apk", work / "aligned.apk"
    kept = {}
    with zipfile.ZipFile(base) as s, zipfile.ZipFile(unsigned, "w") as d:
        d.comment = s.comment
        for m in s.infolist():
            if is_sig(m.filename):
                continue
            data = swf if m.filename == SWF_MEMBER else manifest2 if m.filename == "AndroidManifest.xml" else s.read(m)
            d.writestr(m, data)
            kept[m.filename] = (sha(data), m.compress_type)
    run([TOOLS / "zipalign.exe", "-p", "-f", "4", unsigned, aligned])
    out.parent.mkdir(parents=True, exist_ok=True)
    run([TOOLS / "apksigner.bat", "sign", "--v4-signing-enabled", "false", *ksargs,
         "--ks-pass", "env:WF_HITFX_KS", "--key-pass", "env:WF_HITFX_KEY", "--out", out, aligned], env)
    out_certs, schemes = certs(out, env)
    if out_certs != base_certs:
        raise Fail("signer certificate differs from base — would not install over it")
    run([TOOLS / "zipalign.exe", "-c", "-p", "4", out])
    with zipfile.ZipFile(out) as r:
        if {n for n in r.namelist() if not is_sig(n)} != set(kept) or r.testzip() is not None:
            raise Fail("member inventory/CRC differs")
        for n, exp in kept.items():
            if (sha(r.read(n)), r.getinfo(n).compress_type) != exp:
                raise Fail("member changed: " + n)
    if sha(base.read_bytes()) != base_bytes_sha:
        raise Fail("base APK changed during build")
    for p in (unsigned, aligned):
        p.unlink()
    rep = {"capability": CAPABILITY, "status": "signed_static_candidate", "installed": False, "runtime_verified": False,
           "base_apk": str(base), "base_apk_sha256": base_bytes_sha, "apk": str(out), "apk_sha256": sha(out.read_bytes()),
           "signer": a.signer, "certificate_sha256": out_certs, "signature_schemes": schemes,
           "uniqueappversionid": {"before": olds[0], "after": new_uid},
           "changed_members": ["AndroidManifest.xml", SWF_MEMBER, "META-INF signature"],
           "preserved_members": len(kept) - 2, **swf_report}
    out.with_suffix(".build-report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", "utf8")
    print(json.dumps({k: rep[k] for k in ("apk", "apk_sha256", "output_swf_sha256", "certificate_sha256", "uniqueappversionid")}, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apk", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--signer", choices=("local", "debug"), required=True)
    p.add_argument("--work", default=None)
    a = p.parse_args()
    a.work = a.work or str(Path(a.out).with_suffix(".work"))
    build(a)


if __name__ == "__main__":
    main()
