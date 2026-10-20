# -*- coding: utf-8 -*-
"""只读审计本地 APK 文本档案；输出只写本 audit 目录。"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
SRC = Path(r"D:\WF\apkp1016\apk-patches")
KULO = Path(r"D:\WF\startpoint-cn-kulo")


def source(rel: str, needle: str = "") -> dict:
    p = SRC / rel
    b = p.read_bytes()
    lines = b.decode("utf-8-sig").splitlines()
    return {"path": str(p), "sha256": hashlib.sha256(b).hexdigest(),
            "line": next((n for n, s in enumerate(lines, 1) if needle in s), 1)}


FEATURES = [
    {
        "feature": "五星角色超限 Lv120（瓦格纳 111183；护花使龙/休尔特 141099）",
        "data": ["character_status 的120级行", "超限结晶10000320", "悖论之核10000302", "character_overlimit.json", "等级觉醒任务"],
        "patches": ["O1", "O2", "O3", "O4", "O5", "O6", "O7", "bundle-level-cap", "bundle-experience", "bundle-pedestal-atlas"],
        "without": "缺 O1/内置上限表则仍受官方4次突破限制；缺 O2/O3/O4/O5 则结晶筛选、重复角色限制与双道具可突破次数显示不一致。缺101–120经验表时，同房客户端读取120级角色存在缺行报错风险；准确错误码未核实。不能把内置表同键放 CDN：设计说明记录主键冲突7051。",
        "codes": ["7051（错误地以CDN覆盖内置表同键时）", "120级经验表缺行的准确错误码未核实"],
        "server_source": "需要。灰 origin/main 不存在 src/lib/character-overlimit.ts；必须移植每角色突破/经验上限、零重复角色超限、一次请求不跨官方边界、等级觉醒任务与 extra_costs 校验后原子双扣等源码。只应用 assets JSON 行不够。",
        "references": ["README.md", "78-overlimit-crystal-buttons/README.md", "79-overlimit-experience/README.md", "82-overlimit-level-cap/README.md", "83-overlimit-max-step/README.md", "101-overlimit-paradox-core-item/README.md"],
    },
    {
        "feature": "超限台座全身/半身 _6、_7",
        "data": ["第5次突破起_6", "第8次突破且Lv120且首盘全觉醒时_7"],
        "patches": ["O6", "O7", "bundle-pedestal-atlas"],
        "without": "缺 O6/O7 则仍显示旧台座；只改方法而缺APK内置24帧图集会请求不存在资源，具体错误码未核实。CDN包不能替代该APK内置图集依赖。",
        "codes": ["未核实"], "server_source": "台座显示本身不需要新服务端源码；超限资格仍依赖上项服务端规则。",
        "references": ["80-overlimit-full-pedestal/README.md", "81-overlimit-half-pedestal/README.md", "86-overlimit-pedestal-atlas/README.md"],
    },
    {
        "feature": "赛瑞斯 129999 PF Lv4 override 与红色充能提示",
        "data": ["forLevels含4的override", "override_seris_dragon_lv4", "底层PF档位保持3"],
        "patches": ["P1", "P2", "P3", "九尾拍板前连击快照"],
        "without": "缺P1不能在100连击拍板时优先选Lv4 override；缺P2/P3没有相应八档渐变、红光与就绪提示。当前实现底层仍为Lv3，不能据此断言旧APK必崩。若错误地让真实档位流到4，已知取DSL空引用F1009、攻击计算2702。早期P2懒加载提示音曾报8022，最终v32f已修复。",
        "codes": ["F1009（仅真实档位误设4）", "2702（仅真实档位误设4）", "8022（早期提示音懒加载实现，最终已修）"],
        "server_source": "该PF选择/演出不需要新服务端源码；同房须使用一致客户端，否则队友副本可能呈现不同PF。",
        "references": ["87-pf-lv4-color/README.md", "88-pf-lv4-dsl/README.md", "89-pf-lv4-ready/README.md"],
    },
    {
        "feature": "Fever 箭头换随机道具（赛瑞斯及挂同类标记的队长）",
        "data": ["unique_condition 1299901..1299909", "string_id fever:items:<候选键>", "direct_instant_item及配套level/program/动画"],
        "patches": ["B1", "B2", "B3", "B5"],
        "without": "完全未装B系时该约定只是普通Unique标记，旧客户端继续开Fever箭头，箭头换道具不生效；这点来自源码规则推断，未在灰APK运行。只装部分/旧版B系曾报8013（主表未加载）、8601（空标记槽）、14502（rotationPanelAnimation=None）、8037（候选DSL未leading预载），最终v32l采用安全取表及Some(backgroundAnimation)。不能把这些中间错误冒称完全无补丁必崩。B4已撤销。",
        "codes": ["8013（早期/不完整取表）", "8601（早期空槽）", "14502（早期None动画）", "8037（缺B5 leading DSL预载）"],
        "server_source": "候选随机与资源预载在客户端执行，无新服务端源码要求；各端须同数据/同补丁以维持副本一致。",
        "references": ["90-fever-arrow-close/README.md", "91-fever-arrow-items/README.md", "92-fever-items-preload/README.md", "93-fever-items-leading-dsl/README.md"],
    },
    {
        "feature": "通用技能准备 alt 语音轮换",
        "data": ["正常/变身skill_ready连续_alt_N文件，最多5条，缺号停止"],
        "patches": ["V1", "V2", "V3"],
        "without": "未装V1不会按通用规则轮换，未装V2战斗不预载新增alt，未装V3图鉴不列出新增alt。全部未装时通常只播放原有准备音，未发现专用必崩码；部分混装的具体错误码未核实。V1保留5个既有专用轮换角色逻辑。",
        "codes": ["未发现专用错误码"], "server_source": "不需要新服务端源码。",
        "references": ["94-generic-ready-gallery/README.md", "95-generic-ready-preload/README.md", "96-generic-ready-rotation/README.md"],
    },
    {
        "feature": "杰拉德149999及5个既有专用角色的准备音轮换",
        "data": ["white_wolf_gerald原句与skill_ready_alt_1..3", "149990/129992/139993/159998既有专用准备音"],
        "patches": ["65-gerald-149999-ready-voice", "06-summer-bai-voice", "07-gerald-129992-ready-voice", "15-author-ready-voices"],
        "without": "149999在最终v33已有专用四拍轮换、预载与图鉴；缺专用补丁则不能仅靠V1–V3假定已解决，因为V1明确跳过white_wolf_gerald等5个已有专用角色。最终HudMemberStatus P-code含149999 alt_1/2/3分支。早期voice193_build.py的限制不代表219+v33终态。缺文件时专用分支保留原生音，未发现专用必崩码。",
        "codes": ["未发现专用错误码"], "server_source": "不需要新服务端源码。",
        "references": ["65-gerald-149999-ready-voice/README.md", "06-summer-bai-voice/README.md", "07-gerald-129992-ready-voice/README.md", "15-author-ready-voices/README.md", "96-generic-ready-rotation/pcode/boot_ffc6--HudMemberStatus_update.pcode.txt"],
    },
    {
        "feature": "凯尔 kyle_moon 终态直击、充能与PF表现",
        "data": ["Unique13999010充能上限", "Unique13999011/13999012直击倍率", "PF追加命中attack_to_hostile_hit且randomRotation=false"],
        "patches": ["53-charge-cap-unique", "54-kyle-direct-multiplier", "55-kyle-pf-marker-silence", "56-kyle-direct-merge"],
        "without": "缺53仍受官方充能上限；缺54不会执行数据层数约定的凯尔队长直击公式；缺55追加PF有重复数字/音效/闪烁；缺56多段逐次调度，性能收益不生效。以上未发现专用必崩码。",
        "codes": ["未发现专用错误码"], "server_source": "以上战斗行为不需要新服务端源码。",
        "references": ["53-charge-cap-unique/README.md", "54-kyle-direct-multiplier/README.md", "55-kyle-pf-marker-silence/README.md", "56-kyle-direct-merge/README.md"],
    },
    {
        "feature": "含新能力枚举422/423/424/724的角色平衡与重做",
        "data": ["422冲刺参数", "423回槽来源限制", "424伤害类型转换", "724按满槽比例增减Fever"],
        "patches": ["03-dash-parameter-422", "04-fever-ratio-724", "20-damage-type-conversion", "31-gauge-gain-rules"],
        "without": "未支持的能力枚举解析可能报C7050。即使仅靠DSL标记而未走新枚举，缺完整伤害类型转换仍可能把101/102/104/131–133按旧类别结算，统计/耐性/计数/乘区错误。早期423循环VerifyError #1021为已修中间实现，不能当作最终数据固有缺陷。",
        "codes": ["C7050（未支持枚举）", "VerifyError #1021（早期补丁缺label，已修）"],
        "server_source": "词条战斗解释不需要新服务端源码；按结算统计再判断是否有配套服务端校验，灰部署状态未核实。",
        "references": ["03-dash-parameter-422/README.md", "04-fever-ratio-724/README.md", "20-damage-type-conversion/README.md", "31-gauge-gain-rules/README.md"],
    },
    {
        "feature": "角色/队长技作者自定义文案",
        "data": ["CustomAbilityStringTable desc_override_<string_id>"],
        "patches": ["02-panel-description-override"],
        "without": "无补丁时按旧模板描述，作者覆盖文案不生效；旧不安全取表版在CustomAbilityStringTable未加载时报8013。最终实现缺表回退原文。",
        "codes": ["8013（旧不安全取表实现）"], "server_source": "不需要新服务端源码；技能正文仍须正确action_skill各档文本。",
        "references": ["02-panel-description-override/README.md"],
    },
    {
        "feature": "双形态角色、重设计像素与hidden_机制状态",
        "data": ["ModDualForm标签/Unique22", "frame.scale", "UniqueConditionTable string_id以hidden_开头"],
        "patches": ["21-dual-form-animation", "45-render-frame-scale", "58-hidden-unique-icons"],
        "without": "缺21不切special形态/不按约定预载；缺45自制像素占屏与设计不一致；缺58机制状态会显示并占图标页数。未发现专用错误码；灰APK现状未核实。",
        "codes": ["未发现专用错误码"], "server_source": "不需要新服务端源码。",
        "references": ["21-dual-form-animation/README.md", "45-render-frame-scale/README.md", "58-hidden-unique-icons/README.md"],
    },
    {
        "feature": "诅咒/深渊装备与能力魂门控（如最终包保留8000101–8000115）",
        "data": ["8000101..8000115", "精确Single/Multi副本白名单", "直接装备强化Lv120例外"],
        "patches": ["11-abyss-equipment-mode-gate"],
        "without": "缺门控时强力装备/魂珠的适用范围可能失守，且直接装备与魂珠例外不一致。不是已知必崩问题。PARADOX r4若只使用普通表/DSL无独立补丁编号；是否另需专用客户端逻辑未核实。",
        "codes": ["未发现专用错误码"], "server_source": "须另核对服务端装备/编队准入规则；本审计未把客户端门控等同服务端保护。",
        "references": ["11-abyss-equipment-mode-gate/README.md"],
    },
    {
        "feature": "新增高等级领主战/共同决战与属性耐性配置",
        "data": ["quest->field_data->zone->general_*等级行", "关卡sub_name属性伤害配置（若采用）"],
        "patches": ["44-quest-element-resistance（有该数据约定时）"],
        "without": "普通新副本表和官方DSL本身不必然需要新增APK补丁；若用sub_name耐性约定而缺44，属性耐性不生效。若general_*最高等级不足，则是数据配套缺口，可报U_3be147，须靠prepush level检查，不能用APK依赖说明掩盖。",
        "codes": ["U_3be147（数据等级缺口）"], "server_source": "开放、次数、掉落、联机准入等须有对应服务端JSON行；是否另含专用机制源码需按实际副本逐项核对，未核实。",
        "references": ["44-quest-element-resistance/README.md"],
    },
]

PATCH_MAP = {
    "O1": "GeneralCharacterLogic/get_maxOverLimitStep", "O2": "OwnedOverLimitLogic/getOwnAwakingCrystalToOverLimit",
    "O3": "OwnedOverLimitLogic/getAwakingCrystalToOverLimit", "O4": "OwnedOverLimitLogic/getOverLimitState",
    "O5": "OwnedCharacterLogic/getPossibleOverLimitCountByItem（已构建双道具版）",
    "O6": "GeneralCharacterLogic/getPedestalImagePath", "O7": "GeneralCharacterLogic/getHalfPedestalImagePath",
    "P1": "MemberImpl/startPowerFlip", "P2": "BattleFlipperImpl/update", "P3": "BattleFlipperView/draw",
    "B1": "YakumonoManagerImpl/activate", "B2": "YakumonoManagerImpl/deactivate",
    "B3": "BattleQuestBaseImpl/resolvePathCollectionForDashPanel", "B5": "BattleQuestBaseImpl/leadingResolvePathCollection",
    "V1": "HudMemberStatus/update", "V2": "BattleCharacterLogic/resolveFollowingPathCollection",
    "V3": "CharacterVoiceLogic/createVoicePathMap",
}


def main() -> None:
    paths = sorted({r for f in FEATURES for r in f["references"]})
    refs = {r: source(r) for r in paths}
    git_result = subprocess.run(["git", "-C", str(KULO), "ls-tree", "-r", "--name-only", "origin/main", "docs/client-apk-patches-v33"], capture_output=True, check=True)
    over = subprocess.run(["git", "-C", str(KULO), "show", "origin/main:src/lib/character-overlimit.ts"], capture_output=True)
    report = {"scope": "本地文本静态依赖审计；未读/收APK或.so，未构建/安装/运行客户端，未联网。", "origin_main_pr43_docs_present": bool(git_result.stdout.strip()),
              "origin_main_overlimit_source_present": over.returncode == 0, "gray_installed_apk_patches": "未核实", "patch_method_map": PATCH_MAP,
              "features": FEATURES, "sources": refs, "additional_local_sources": [r"D:\WF\out\角色超限-120\设计说明.md", r"D:\WF\out\角色超限-120\server-patch\0001-feat-server-character-over-limit-to-level-120-for-li.patch", r"D:\WF\out\赛瑞斯重做-20261015\pf_lv4_client.md"]}
    (OUT / "apk-dependencies.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = ["# APK 数据依赖静态审计", "", "此文供主说明引用。证据为本机最终v33文本档案及生成源码；没有运行灰APK，灰现有APK是否已含这些能力均为**未核实**。未收APK、签名、keystore、.so。", "", "用户提到的PR #43路径 `docs/client-apk-patches-v33/` 在当前本地 `kulo origin/main` 树中未找到；PR当前状态未联网核实。以下采用 `D:\\WF\\apkp1016\\apk-patches\\` 本地档案，不把PR存在等同灰已部署。", "", "## 功能与依赖", "", "| 功能/数据 | 必须保留的补丁 | 缺失后的行为/已知错误 | 服务端源码要求 |", "|---|---|---|---|"]
    for f in FEATURES:
        md.append("| " + " | ".join([f["feature"] + "；" + "、".join(f["data"]), "、".join(f["patches"]), f["without"], f["server_source"]]).replace("<候选键>", "候选键") + " |")
    md += ["", "## 编号与方法对照", "", "P/B等字母编号在perf补丁里有重名；此处P1–P3特指v32f PF，B1/B2/B3/B5特指v32l Fever，不是perf2的同名字母。", "", "| 补丁 | 方法/资源 |", "|---|---|"]
    md += [f"| {k} | `{v}` |" for k, v in PATCH_MAP.items()]
    md += ["", "O1–O7之外仍须保留APK内置两张表与台座图集；不允许用CDN同键去覆盖APK内置行。O5是已构建的双道具版，后续零核调整未构建，不应写成终态。B4已撤销。", "", "## 证据边界", "", "- F1009/2702指真实PF档位误传4，不是本次安全Lv3+override数据在旧APK的必然结果。", "- Fever的8013/8601/14502/8037有特定不完整/中间实现前提，完整缺B系通常是功能不生效；灰实包行为未核实。", "- 通用语音轮换无已证实的专用必崩码；不要编造。", "- Lv120联机伙伴也须有101–120经验表；档案记录缺行风险，准确码未核实。", "- 服务端JSON更新不等于服务端已具备超限源码；灰origin/main缺该模块为本次git show直接核实。", "", "## 本地来源", ""]
    md += [f"- `{v['path']}`；SHA-256 `{v['sha256']}`。" for v in refs.values()]
    md += ["", "补充：`D:\\WF\\out\\角色超限-120\\设计说明.md` 第79–100行附近列内置表7051与同房经验表限制；`server-patch/0001-*.patch` 明列7个源文件/配置及单测；`D:\\WF\\out\\赛瑞斯重做-20261015\\pf_lv4_client.md` 记录真实档位4的崩溃根因。", ""]
    (OUT / "apk-dependencies.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"features": len(FEATURES), "sources": len(refs), "outputs": ["apk-dependencies.json", "apk-dependencies.md"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
