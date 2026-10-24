# -*- coding: utf-8 -*-
"""灰服三角色导入：墨斯伊克 149997 / 希耶提 149995 / 希尔媞「千刃共振」泳装 149996（2026-09-27 平衡批次）。

作者原话（2026-09-27，聊天）：「对方灰服调整过的角色，把这版替换我本地的，然后一并纳入调整」。

来源：灰服 CDN 增量包 ``pinball-1.4.121-1.4.131-1-author-three-characters-data.zip``（灰链 1.4.121→1.4.131，
161 个成员，``ARCHIVE_SHA256``；成员名 ``production/<root>/<xx>/<sha1(逻辑路径+盐) 余 38 位>``，
root：upload=common、medium_upload=medium、android_upload=android、ios_upload=ios）。成员逐个钉 sha256
（``GRAY_FILES``），读到的字节不符即拒绝。读取顺序：``GRAY_ROOT``（默认仓库 ``work/gray3/production``，
``/work/`` 已 gitignore、不随会话清理；``extract`` 子命令从钉哈希的原压缩包解出）里有就读它，没有就直接从
``ARCHIVE`` 读成员；``files`` 输出要落地路径，只认 ``GRAY_ROOT``。151 个成员由哈希反查表认出；其余 4 个未识别成员 = 泳装希尔媞新特效族
``battle/effect/skill_unique/wind_spgirl_swim/wind_spgirl_swim.{parts,timeline,atlas}.amf3.deflate`` 与
``….png``——由灰版技能 DSL 的 ShowEffect 路径 + 预载器 ``<目录>/<目录名>.png/.atlas`` 规则算 sha1 反查命中；
与灰方 1.4.88 审计记录（patch-audit.json ``x_effect.members``）的 sha256 逐一相同。

## 键级替换，绝不整表
压缩包里 11 张表是灰链整表：其他角色的行与我方不同（例如 ability 142 键、leader 27 键、action_skill 20 键，
另有灰方独有 159991 等、我方独有 129986/129987 等，见夹具 ``other_character_diff``）。本模块只取三名角色
自己的外层键（``startswith(cid)``、``== code``、``startswith(code + "_")``；与 live 同名键集合逐表一致，见
``EXPECTED_KEYS``），灰值 ≠ live 值的键才返回。

## 返回（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md，多角色 ``UNITS``）
标准键 ability/leader/cas/text/action/dsl/server_text/new_programs/notes，另有新键（主会话扩展暂存脚本）：
- ``files``：``{"<tier>:<logical>": "<GRAY_ROOT 下解出文件的绝对路径>"}``，tier ∈ common/medium/android，
  只列与 live 字节不同或 live 缺的文件。ios 层 6 个 cut-in ATF 我方没有该根，忽略。技能 DSL 走 ``dsl``（树），
  其 AMF3 负载与压缩包逐字节相同（``GRAY_DSL_AMF3_SHA256``）。
- ``presentation_table``：``{(logical, outer): rows | {inner: rows}}``——立绘定位三表：character_image、
  full_shot_image_attribute 为嵌套（候选 codec raw_outer，字节用 ``encode_presentation``），trimmed_image 为平表。
- ``nested_table``：非立绘的嵌套表键（本次为空；character_status 三人与灰版相同）。
- ``server_character``：恒为空（灰版 character 行与我方相同，assets/cdndata/character.json 无需同步）。
读取另需两个 read 种类（暂存脚本扩展）：``nested_table``：(logical, outer) → {inner: csv rows}；
``file_sha256``：(tier, logical) → live 文件 sha256（缺失为 None）。

## 美术分两步：希耶提灰版美术单独拍板（``ART_DECISION``；作者 2026-09-27 已接受）
美术 = medium/android 层与 ``character/<code>/`` 下的文件 + 立绘定位三表（``is_art``）；``battle/effect`` 特效是
DSL 依赖，不算美术。希耶提灰版觉醒立绘脸锚 y=874（官方 p10-p90 418-646）、两槽脸锚不同高、cut-in 上/左边不透明——
正是作者 1.4.447 实机否决过的构图（``ART_REVIEW``，对比图在 ``work/gray3/review/``），而且会让希耶提包内 4 条
构图/边缘/生成器一致性测试变红。所以 ``UNITS`` 里的希耶提只导入表/DSL/文案（与美术无依赖），美术和定位行放进
``notes.art``（status = deferred，列出延后的文件与定位行）；作者看图接受后，暂存单独的 ``ART_UNITS``
（只查美术输入基线，核心导入之后仍可跑），并在同一单元按作者签字改/退役那 4 条包测试。泳装希尔媞的灰版美术
沿用我方定位行、脸锚落在脸上，cut-in 边缘与我方同样不透明（非回退），随核心一起导入；墨斯伊克美术与我方逐字节相同。

**作者 2026-09-27 已拍板接受希耶提灰版美术**（``ART_DECISION["149995"]`` = accepted，原话见该处注释）。核心导入
已在 1.4.1054 发布，本模块的 ``UNITS`` 因此不能再跑（BEFORE fail closed）；美术由第三轮 extra5 批次的
``wf_balance_20260927c_seofonart``（包装 ``ART_UNITS``）单独暂存，包内 4 条测试按作者决定对灰版 27 个文件的 sha256 豁免。

## 压缩包之外、被压缩包内容引用的依赖（从灰链归档补齐）
压缩包只带表、技能 DSL、UI/像素/特效资产；不带 ability_skill DSL、custom_ability_string、立绘定位三表、
PF 覆盖树、语音。其中两处是压缩包内容的硬依赖，从本地灰链归档
``work/codex_out/gray-audit-20260830/gray/assets/asset-patch/active``（灰链 ≤1.4.93 快照）取回并核对：
- 灰版 ``1499966#3`` 是 kind 629，调用 ``ability_skill_wind_spgirl_swim_whirlwind``：程序（西微「风怒龙卷＋」
  满强化本体移植）与文案「额外发动「旋风」」live 都没有。取灰链 1.4.87→1.4.88 边的原字节，
  sha256 = 灰方 1.4.88 审计 ``output_sha256``（``WHIRLWIND_DEFLATE_SHA256``）；文案取 1.4.92 的 custom_ability_string。
  灰版 149996 的表行自 1.4.93 起未变（与压缩包逐格相同），CT 60 帧 = 灰方审计 ``invoke_cooldown_frames``。
- 希耶提立绘换成灰版后 PNG 尺寸变了（_0 1774×1769→1659×1535，_1 1741×1772→1632×1681）：character_image
  的 pngW/pngH 必须等于 PNG 实际尺寸。灰链 1.4.91→1.4.92 的定位行 W/H 与压缩包 PNG 逐一相等（同一批美术），
  连同 trimmed_image（含 skill_cutin_0 显示偏移）与 full_shot_image_attribute 脸锚一起取回（只随希耶提美术导入；作者 09-27 接受后由 seofonart 暂存）。泳装/墨斯伊克的定位行灰版与我方相同。
其余压缩包外差异不导入，只报告（notes.not_in_archive）：墨斯伊克 PF 覆盖树（灰链 1.4.85 把倍率 12.5/8.28/6.44
降到 7.5/6.0/4.5，p13 仍为 5；我方 live 还叠了第二批 p13 5/4/2.5）、泳装希尔媞 19 条语音（灰链 1.4.88 重编码）、
希耶提「剑界回响」629 树（灰链 = 我方第二批之前的 p13 2.0）。

## 与第二批（1.4.1051）的关系
只有泳装希尔媞 A4（``1499964``）被覆盖：第二批 B4 把「每 77 连击自身眩晕蓄积 +25%（限 101）」改成「自身直击 +20%（限 5）」，
灰版就是改前那一行。导入后 live 1499964 的摘要 == ``wf_balance_20260927b_swimceltie.BEFORE``：第二批泳装模块
因此重新「可应用」——gray3 之后禁止重跑它（会把 B4 静默叠回灰版行）；A4 归任务 B。
墨斯伊克 PF 削韧（B2）与希耶提回响 p13（B3）不在压缩包里，第二批结果保留。
三方比对（我方最后一次发给灰的分享包 mosiyike0820 / lion0823 / trio0825 = 灰方起点）：除 1499964 外，所有差异格
都是「灰方改、我方未改」，导入不会回退我方其他改动。

纯函数：``revise`` 只读 ``read()`` 与钉住哈希的灰方来源，不写任何文件；不写 live/assets/.cdn/候选，不发布，不 git。
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable
import zipfile
import zlib

import wf_client_legality as L
import wf_describe
import wf_dsl
import wf_mod_tool as core
import wf_share_update_codec as X
from wf_balance_20260927b_mosiyike import REVIEWED_DRIFT as _MOSIYIKE_REVIEWED_DRIFT

REPO = Path(__file__).resolve().parents[1]
ARCHIVE_NAME = "pinball-1.4.121-1.4.131-1-author-three-characters-data.zip"
#: 原始压缩包（作者下载目录）；环境变量 WF_GRAY3_ARCHIVE 可覆盖。整包钉 ARCHIVE_SHA256，成员逐个钉 GRAY_FILES。
ARCHIVE = Path(os.environ.get("WF_GRAY3_ARCHIVE", Path.home() / "Downloads" / ARCHIVE_NAME))
ARCHIVE_SHA256 = "33ecd89034ef38ca43fb68e739b976bb3af0a303d6265e60905b5205fc8cdfb0"
ARCHIVE_EDGE = ("1.4.121", "1.4.131")
#: 压缩包解出目录：默认仓库内 work/gray3/production（/work/ 已 gitignore，不随会话清理）；环境变量
#: WF_GRAY3_ROOT 可覆盖。缺失时 ``python mod-tools/wf_balance_20260927b_gray3.py extract`` 从 ARCHIVE 重新解出。
GRAY_ROOT = Path(os.environ.get("WF_GRAY3_ROOT", REPO / "work" / "gray3" / "production"))
#: 给作者看的美术对比图（``python mod-tools/wf_balance_20260927b_gray3.py review`` 从 live store + 压缩包只读生成，
#: 路径相对仓库根）。
REVIEW_DIR = "work/gray3/review"
GRAY_CHAIN = "work/codex_out/gray-audit-20260830/gray/assets/asset-patch/active"
TIER_DIRS = {"common": "upload", "medium": "medium_upload", "android": "android_upload", "ios": "ios_upload"}
IMPORT_TIERS = ("common", "medium", "android")
DSL_SUFFIX = ".action.dsl.amf3.deflate"
ELEMENT = 3                                   # 三人都是风（0 基内部元素）

ABIL = "master/ability/ability.orderedmap"
LEAD = "master/ability/leader_ability.orderedmap"
CHAR = "master/character/character.orderedmap"
SPEECH = "master/character/character_speech.orderedmap"
STATUS = "master/character/character_status.orderedmap"
TXT = "master/character/character_text.orderedmap"
UQ = "master/character/unique_condition.orderedmap"
UPSKILL = "master/mana_board/upskill.orderedmap"
ACT = "master/skill/action_skill.orderedmap"
SWITCHED = "master/skill/switched_action_skill.orderedmap"
PREVIEW = "master/skill_preview/skill_preview_character.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
CIMG = "master/generated/character_image.orderedmap"
TRIM = "master/generated/trimmed_image.orderedmap"
FSA = "master/character/full_shot_image_attribute.orderedmap"
#: 压缩包里的 11 张整表。
GRAY_TABLES = (ABIL, LEAD, CHAR, SPEECH, STATUS, TXT, UQ, UPSKILL, ACT, SWITCHED, PREVIEW)
NESTED_TABLES = frozenset({STATUS, CIMG, FSA})
PRESENTATION_TABLES = (CIMG, TRIM, FSA)
_STD_KIND = {ABIL: "ability", LEAD: "leader", TXT: "text", ACT: "action"}

WHIRLWIND_KEY = "ability_skill_wind_spgirl_swim_whirlwind"
WHIRLWIND_PROGRAM = f"battle/action/skill/action/ability_skill/{WHIRLWIND_KEY}${WHIRLWIND_KEY}"

SPECS = {
    "149997": dict(code="mosiyike", name="墨斯伊克「自由之羽」", packages=["mosiyike"],
                   version={"mosiyike": "0.1.2"},          # 候选现值 0.1.1（第二批）→ 递增
                   drift=_MOSIYIKE_REVIEWED_DRIFT),        # 第二批已审的 29 条既有漂移，至今未变
    "149995": dict(code="seofon_wind", name="希耶提「剑光统御」", packages=["seofon_wind"],
                   version={"seofon_wind": "1.0.3"},       # 候选现值 1.0.2（第二批）→ 递增
                   drift={}),
    "149996": dict(code="wind_spgirl_swim", name="希尔媞「千刃共振」泳装", packages=[],
                   version={}, drift={}),                  # 无 flow 包（BarePlan）
}

# ---------------------------------------------------------------- 钉住的灰方来源（生成，勿手改）

#: 压缩包全部 161 个成员："<tier>:<logical>" → sha256（tier 按根目录：upload=common … ios_upload=ios）。
GRAY_FILES = {
    "android:character/mosiyike/ui/skill_cutin_0.atf.deflate":
        "094447da72e1963c46873db48716e0f2b9c893c2299dae5dd587c55a95a374cf",
    "android:character/mosiyike/ui/skill_cutin_1.atf.deflate":
        "094447da72e1963c46873db48716e0f2b9c893c2299dae5dd587c55a95a374cf",
    "android:character/seofon_wind/ui/skill_cutin_0.atf.deflate":
        "81089f684690a513ee8d696d6fd07b22c28e00a322022c4e47a6dbf5c342a658",
    "android:character/seofon_wind/ui/skill_cutin_1.atf.deflate":
        "27b6855dc22f68b95f273d2e1ef7f87217a5cd2b78ba0bcfb6f160710f2c6abd",
    "android:character/wind_spgirl_swim/ui/skill_cutin_0.atf.deflate":
        "c97263930d0bd5e1085e4812c4891911cd5505c8e378245bb1dda1fa2e232fed",
    "android:character/wind_spgirl_swim/ui/skill_cutin_1.atf.deflate":
        "4afa4e385cdbbb59b6d40263a5278553c11475b5f2a2dfbd637b05b3a2ef37e3",
    "common:battle/action/skill/action/rare5/mosiyike$mosiyike_1.action.dsl.amf3.deflate":
        "07e3c40f8bdb1985511be967205bb30f64ae52f6eaae029d9d8146339520cf50",
    "common:battle/action/skill/action/rare5/mosiyike$mosiyike_2.action.dsl.amf3.deflate":
        "7739a4f9458633ec09b234c39a86b13f253c8eef22a0ca406ecb3c299d04ca6b",
    "common:battle/action/skill/action/rare5/seofon_wind$seofon_wind_1.action.dsl.amf3.deflate":
        "0f1c854a6b568d21b7200f31cebcffe5612c7b3c2c66ebe18f5c1a7192d54bcd",
    "common:battle/action/skill/action/rare5/seofon_wind$seofon_wind_2.action.dsl.amf3.deflate":
        "dc9dc0b40964cbade8ecffaa69ea14b26710cba2e62676733c79efda335f6737",
    "common:battle/action/skill/action/rare5/wind_spgirl_swim$wind_spgirl_swim_1.action.dsl.amf3.deflate":
        "d399bb08d119b0d31fa521a6c9f8faa594463872686903d3119bbdd99fb48a48",
    "common:battle/action/skill/action/rare5/wind_spgirl_swim$wind_spgirl_swim_2.action.dsl.amf3.deflate":
        "6570602a270966ec678f766a98f65d62594674cc21b197f236d36ef2402ff2af",
    "common:battle/action/skill/action/rare5/wind_spgirl_swim$wind_spgirl_swim_3.action.dsl.amf3.deflate":
        "f1e398c4544670a714cb16c685ce21ce6ccab17138b559c37dc400e1eeb9a23c",
    "common:battle/effect/skill_unique/mosiyike/mosiyike_shield/mosiyike_shield.atlas.amf3.deflate":
        "bc5831d426d10505f02d93d52ed66ed47de6a62c608f66ed7f0ee6509e0372f6",
    "common:battle/effect/skill_unique/mosiyike/mosiyike_shield/mosiyike_shield.png":
        "23e77547506ebc095873b6c0307f02b0f9595775d817d86968c3eef834fc2a5d",
    "common:battle/effect/skill_unique/mosiyike/mosiyike_shield/mosiyike_shield_gather.parts.amf3.deflate":
        "1a9522d65f162656bcbc3b35f24a800e5f07929160a744f35880b3fc9b8d748c",
    "common:battle/effect/skill_unique/mosiyike/mosiyike_shield/mosiyike_shield_gather.timeline.amf3.deflate":
        "8dd61177f636c99b5eedc6b2f94cb3704729d3378895b95d96a82ec80f9fb9c6",
    "common:battle/effect/skill_unique/mosiyike/mosiyike_shield/mosiyike_shield_loop.parts.amf3.deflate":
        "0fb5b83a7b4142912cbf482cb39099c4e32c384f074d69397903680fa01f7ba0",
    "common:battle/effect/skill_unique/mosiyike/mosiyike_shield/mosiyike_shield_loop.timeline.amf3.deflate":
        "917b0285691097c841a4f1b8084805d107e9436a2bcc0af9f661a6ae80c63342",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada.atlas.amf3.deflate":
        "2c60df73cd58725cdd1f671fe0b1028ec55b8303a5a32b925491344b78cc7966",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada.parts.amf3.deflate":
        "984f1896c047fab63c9b41fce9b7a3a1854fe218a4c7b04d34d1579835c0ed91",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada.png":
        "baf955463368ff4b6127abbb7dbcd8ce2fe110db7ad502b1cab02472517b4b42",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada.timeline.amf3.deflate":
        "b9e692897b5adb800b0839107be6b6c98344af62330f6ee5787ba55c1e32bf94",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_avatar.parts.amf3.deflate":
        "e6187aca1813608029c2fa09aeba1c24cf9cf3ffbade73868f287d1638cc428a",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_avatar.timeline.amf3.deflate":
        "80ca136d394fb5ac50e15231e32bd18e903b5efd447dd97a680db8ff0a2828ef",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_avatar_summon.parts.amf3.deflate":
        "31a932315c3514db876a050dfbc246c04141fd52f895b440a7fdfe13988480af",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_avatar_summon.timeline.amf3.deflate":
        "da3cc62ec298ee2ad057db8a23912ea20a73959a4e9b335656f198d1f3f010a2",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_charge.parts.amf3.deflate":
        "3d2b4d2a50bdc7d04ed861f46228b43b9a91ce7ed5b77abc5f7e17d120a4f589",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_charge.timeline.amf3.deflate":
        "8098c296a5bb8e96ff67300b1f1771468eda27cfa49c7240603c4468e4ebaa3a",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_hit_burst.parts.amf3.deflate":
        "6c884d99e3c82422ba581f545d2b34a6ea7396d74e2d7b81303c4bc78ca6d160",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_hit_burst.timeline.amf3.deflate":
        "131ed7b3eaf7c72677ecf63f921bcad5fc5ca9b5c347c068bedee1f89d3be24d",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_volley_sword1_own.parts.amf3.deflate":
        "3363018bd1a69d8aae13c4eb81ebdaffdd8e2cca6768faad74be44a0a9ea4d88",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_volley_sword1_own.timeline.amf3.deflate":
        "0bf079cbf18df375eb8f1e561748d0b09c1b1242b0a46be66a2f6614e33bc0ff",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_volley_sword2_own.parts.amf3.deflate":
        "54db50dbded96545603c91539e3452b72c3d0c3bc625fde6661c8f44d6b6a430",
    "common:battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_volley_sword2_own.timeline.amf3.deflate":
        "0bf079cbf18df375eb8f1e561748d0b09c1b1242b0a46be66a2f6614e33bc0ff",
    "common:battle/effect/skill_unique/wind_spgirl_swim/wind_spgirl_swim.atlas.amf3.deflate":
        "a39c96195ddfc28abd68ab88d353b8460a946e6159fed2306c1cfa219ff47cf7",
    "common:battle/effect/skill_unique/wind_spgirl_swim/wind_spgirl_swim.parts.amf3.deflate":
        "f0e8ffd851487fddba1900d0ce6cf0f133440f96f737260b4e957132a10661b4",
    "common:battle/effect/skill_unique/wind_spgirl_swim/wind_spgirl_swim.png":
        "924c2061c7272bd28d990fc5231318ec3d93b174ec7962d6e1b62f3d3f2f7192",
    "common:battle/effect/skill_unique/wind_spgirl_swim/wind_spgirl_swim.timeline.amf3.deflate":
        "101918b8cf6f1b3eba0e446393634c3fe664cbaf483a32c23878ddd994f09a2c",
    "common:character/mosiyike/battle/character_detail_skill_preview.battle.amf3.deflate":
        "936515841f11ee2a7c9bf976817a9ba59d008ca40612c4b9dfe7ff86fd7ab7b5",
    "common:character/mosiyike/pixelart/pixelart.frame.amf3.deflate":
        "d5a09d2cc2567a0ad56b31dd3ee22fb903f236718b32422ca775ca07c1120933",
    "common:character/mosiyike/pixelart/pixelart.timeline.amf3.deflate":
        "23bee417315db0b49fa4bd87d62af39682a3ce9dd07b1409e01bf1c813232d8b",
    "common:character/mosiyike/pixelart/special.frame.amf3.deflate":
        "b21c73be99e03192dfc575974e342438abf4be334c7f4a75d3f87f82cb4c1639",
    "common:character/mosiyike/pixelart/special.timeline.amf3.deflate":
        "b68f439cbff34846aa607dd195b3f1fc3f30c6e62486cc989a2cd34b027e3305",
    "common:character/mosiyike/pixelart/special_sprite_sheet.atlas.amf3.deflate":
        "dcd0bb6afb3f06b8341158e74decb8c179913cbfc55e16b657a14703d16da7a4",
    "common:character/mosiyike/pixelart/special_sprite_sheet.png":
        "fd70da8cb98f4961f3a286638c479eb2de88c92a6bbf8041af2d4fd004f5c477",
    "common:character/mosiyike/pixelart/sprite_sheet.atlas.amf3.deflate":
        "d6c6a27d668fdd5c996106d50ed1630a49d29cbb74e4fbfe58a3735115a75660",
    "common:character/mosiyike/pixelart/sprite_sheet.png":
        "a2848fb14625f0423e4be8d0cc0f10209006088b491e950163c1a47ee5160538",
    "common:character/mosiyike/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate":
        "f1b77a6a6ec9b3f2546b45b891a8792cbbf55debcac8aa7a8a387b4311093008",
    "common:character/seofon_wind/battle/character_detail_skill_preview.battle.amf3.deflate":
        "809e55d2c7e141c1a835992cd7ceae02009e24d57d01e4557523b48bf4369125",
    "common:character/seofon_wind/pixelart/pixelart.frame.amf3.deflate":
        "cb070d1e5efc6f232b9cb014431bbb2a4073508401d70aeb7d9b22c5ea7b388d",
    "common:character/seofon_wind/pixelart/pixelart.timeline.amf3.deflate":
        "23bee417315db0b49fa4bd87d62af39682a3ce9dd07b1409e01bf1c813232d8b",
    "common:character/seofon_wind/pixelart/special.frame.amf3.deflate":
        "e37ba24697b859b5baa5723c7b89d987538401a8834ebd5e3c5c738f20e6bcf6",
    "common:character/seofon_wind/pixelart/special.timeline.amf3.deflate":
        "50a131416916a6b2705fd59220f7548cc0a289d5e9dfadba39817bcec8b3dfb7",
    "common:character/seofon_wind/pixelart/special_sprite_sheet.atlas.amf3.deflate":
        "efad97f7335ea0ec094bbcc603740c11f7690e5f853f7f6110baddd3b9f52c12",
    "common:character/seofon_wind/pixelart/special_sprite_sheet.png":
        "57bb64b9922ac55daef1bfaa649b816acfb17c08f8d4572714e475469f709d42",
    "common:character/seofon_wind/pixelart/sprite_sheet.atlas.amf3.deflate":
        "76a39999f6819585c3b0be192b229d5f6c1007c500a941c0b030187d4cfd5b23",
    "common:character/seofon_wind/pixelart/sprite_sheet.png":
        "0ad4ef530b0d4e61243d1643eb6077f5d33854447213769a8412af3a5dd893ea",
    "common:character/seofon_wind/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate":
        "6ff35345898d3a7d0ce0c4ecfa4a6d2b1393aada7af4aabe8409aacd92f94cbe",
    "common:character/wind_spgirl_swim/battle/character_detail_skill_preview.battle.amf3.deflate":
        "1815174862202ab6e8878ee1590dc2bc0e2cd2bf91cc242f887cf6f835a2b23b",
    "common:character/wind_spgirl_swim/pixelart/pixelart.frame.amf3.deflate":
        "74a9c5ccc8f73d56a3a7dcba8df58c08b0ffcd6c6f4629feb500578c35d50ba3",
    "common:character/wind_spgirl_swim/pixelart/pixelart.timeline.amf3.deflate":
        "23bee417315db0b49fa4bd87d62af39682a3ce9dd07b1409e01bf1c813232d8b",
    "common:character/wind_spgirl_swim/pixelart/special.frame.amf3.deflate":
        "1d19f67a505481a948d12303087c518a501460668f143cf1908539b30feb3815",
    "common:character/wind_spgirl_swim/pixelart/special.timeline.amf3.deflate":
        "6e7987222b9f0587bab6ddf5ca2d567cd6908df95fd2ffc3781c78abf70f17a5",
    "common:character/wind_spgirl_swim/pixelart/special_sprite_sheet.atlas.amf3.deflate":
        "645cc71cc4b92723020c4dbfcc6726474a940b8893b0945a01e3dcde716f25d6",
    "common:character/wind_spgirl_swim/pixelart/special_sprite_sheet.png":
        "897c41806b229a01e5106a075dc4eb108bb8935e2c47b3f3c45f62936ba6b2b6",
    "common:character/wind_spgirl_swim/pixelart/sprite_sheet.atlas.amf3.deflate":
        "ae40a287fa9436a3313d662319a44dbc82f13f45c34a4ea0048846ab9d5e473f",
    "common:character/wind_spgirl_swim/pixelart/sprite_sheet.png":
        "ffd0ee36d60a4935d6fcf66fd8ec9ec407237ce3a97c2680136e94ba5c581086",
    "common:character/wind_spgirl_swim/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate":
        "0207b60c0ae5d09a8dbeda645b225ac47b1d2595880cb3c7bb7fcdb233957bb0",
    "common:master/ability/ability.orderedmap":
        "5aec15e73f4b49104af6318f8a8e128c645e7f1e5e9b5174f726c6a545d7be0f",
    "common:master/ability/leader_ability.orderedmap":
        "9576ca420dbbcf95a7ce1825bd12e340637406ab775ab87f3beb5c948acfa269",
    "common:master/character/character.orderedmap":
        "aea20f39fb866ec8fecdb784f877907665798eefd77768acbe5cf932165079c9",
    "common:master/character/character_speech.orderedmap":
        "8c3303e325d18643f409d568a1f0d037fdb64700caffbcd86dd24ad36bc8ccec",
    "common:master/character/character_status.orderedmap":
        "8657844b33fff6c5b478e70663aacea8332c751cca1faa37abe5f21501271c23",
    "common:master/character/character_text.orderedmap":
        "c0dd454cd3c351690aaeb3fbcc08766eda26ad740eab875d4f9a6b1d2c0457c9",
    "common:master/character/unique_condition.orderedmap":
        "4a2621fdea353e8eaf7bf80d020a2238136ad0dbd4d2da851f753df9ff210ba0",
    "common:master/mana_board/upskill.orderedmap":
        "eaab86981e0b82781ddfebc5d63ddfd63292b501fbb2623a174a747d4a581ccd",
    "common:master/skill/action_skill.orderedmap":
        "a37f1becd60d07c20d521f874bc12e8a4e9b1ed9ec3c897c018625300abaa3ff",
    "common:master/skill/switched_action_skill.orderedmap":
        "f8002b4882192569091249d37cfa5a8b662117e3020e0984f8974e0d789b4538",
    "common:master/skill_preview/skill_preview_character.orderedmap":
        "a5d33126d8297e829f7c23b83e0213959e3d03d76905b5c28fae04c1fc7e3a8e",
    "ios:character/mosiyike/ui/skill_cutin_0.atf.deflate":
        "aa3ccd2820f5738987fd76d2b654a5757a097e8b3667ad344e06a5367fc0d462",
    "ios:character/mosiyike/ui/skill_cutin_1.atf.deflate":
        "aa3ccd2820f5738987fd76d2b654a5757a097e8b3667ad344e06a5367fc0d462",
    "ios:character/seofon_wind/ui/skill_cutin_0.atf.deflate":
        "2d46ac303b9342a744db10c9ee0fde2a68fc55de70dde5a6a9dac3cfc5735d37",
    "ios:character/seofon_wind/ui/skill_cutin_1.atf.deflate":
        "636b74c8fc3ffaa32b92eea796502cc46ee5a32cbddacc922385385c5e9af703",
    "ios:character/wind_spgirl_swim/ui/skill_cutin_0.atf.deflate":
        "38f293c8aeac4c853be266dde7d0ca01876b9afb6db21f7618e1f8c62556b552",
    "ios:character/wind_spgirl_swim/ui/skill_cutin_1.atf.deflate":
        "7552325dc718a7d26d2f2b828698d155bee71e356a4ccb3f8d00078656c54d5a",
    "medium:character/mosiyike/ui/battle_control_board_0.png":
        "1e28401689422b9c0537ab6a647c4d865fe44df13564cf3fe76a812015b8daa8",
    "medium:character/mosiyike/ui/battle_control_board_1.png":
        "1e28401689422b9c0537ab6a647c4d865fe44df13564cf3fe76a812015b8daa8",
    "medium:character/mosiyike/ui/battle_member_status_0.png":
        "b2ab86ecd6e4d77e2244a9b77d7917f307c9beefc9c232ccd65be21b0279a438",
    "medium:character/mosiyike/ui/battle_member_status_1.png":
        "f969d8cfc4a1ae48c078f90ad86ee4241d6eae91f229635e517304ec72e8e6f6",
    "medium:character/mosiyike/ui/cutin_skill_chain_0.png":
        "883dbe5c6b05865567087ec06fc1ce8360f085d3a3611ef1802727f875fa762e",
    "medium:character/mosiyike/ui/cutin_skill_chain_1.png":
        "883dbe5c6b05865567087ec06fc1ce8360f085d3a3611ef1802727f875fa762e",
    "medium:character/mosiyike/ui/full_shot_1440_1920_0.png":
        "3db7c3cb929c9666d332c3fffc34fb8c717e869218828321d56ebc75112f064f",
    "medium:character/mosiyike/ui/full_shot_1440_1920_1.png":
        "469ce4934555822e6a237cb30df759b39ff418071c4f2cd04dd8e011094668e7",
    "medium:character/mosiyike/ui/illustration_setting_sprite_sheet.png":
        "52441f6002f0191472d918f41ebf6b6c8f0a5b7aa0253750e887bbf28ab0440e",
    "medium:character/mosiyike/ui/skill_cutin_0.png":
        "a9ea83da7971507dcc577592891904c4350cbd96545142d0b1fb010dcda68a00",
    "medium:character/mosiyike/ui/skill_cutin_1.png":
        "a9ea83da7971507dcc577592891904c4350cbd96545142d0b1fb010dcda68a00",
    "medium:character/mosiyike/ui/square_0.png":
        "f7190d8a20c0102e11828c12a7bc8ab98ca92228ec42b7c8953fde2715b50057",
    "medium:character/mosiyike/ui/square_1.png":
        "f7190d8a20c0102e11828c12a7bc8ab98ca92228ec42b7c8953fde2715b50057",
    "medium:character/mosiyike/ui/square_132_132_0.png":
        "d81f61355487beb8153665a4bcc6c61917f32a3439f32de2793a269af6d1104d",
    "medium:character/mosiyike/ui/square_132_132_1.png":
        "d81f61355487beb8153665a4bcc6c61917f32a3439f32de2793a269af6d1104d",
    "medium:character/mosiyike/ui/square_round_136_136_0.png":
        "53a750be13151378116ebfd8061df60a16894745c88211c3cb1bb0ce87efc605",
    "medium:character/mosiyike/ui/square_round_136_136_1.png":
        "53a750be13151378116ebfd8061df60a16894745c88211c3cb1bb0ce87efc605",
    "medium:character/mosiyike/ui/square_round_95_95_0.png":
        "3c783f08cc9739cd974d106408aa8bb5db71b1d04325715452be21d095bafd28",
    "medium:character/mosiyike/ui/square_round_95_95_1.png":
        "3c783f08cc9739cd974d106408aa8bb5db71b1d04325715452be21d095bafd28",
    "medium:character/mosiyike/ui/thumb_level_up_0.png":
        "fbdf7cc3feee9b5b0a2c9540f767045c0ec069716d95b7629854348bf93f1352",
    "medium:character/mosiyike/ui/thumb_level_up_1.png":
        "fbdf7cc3feee9b5b0a2c9540f767045c0ec069716d95b7629854348bf93f1352",
    "medium:character/mosiyike/ui/thumb_party_main_0.png":
        "20f50735d528b1c8c2ff4324d133ee2d471e2059783888a0402a525176a75977",
    "medium:character/mosiyike/ui/thumb_party_main_1.png":
        "20f50735d528b1c8c2ff4324d133ee2d471e2059783888a0402a525176a75977",
    "medium:character/mosiyike/ui/thumb_party_unison_0.png":
        "201025e2bd53c349034395f36a946945626c6e232c7927e66b873cce9d35ae2a",
    "medium:character/mosiyike/ui/thumb_party_unison_1.png":
        "201025e2bd53c349034395f36a946945626c6e232c7927e66b873cce9d35ae2a",
    "medium:character/seofon_wind/ui/battle_control_board_0.png":
        "09f87c3b0443270bcd741badd4ecd9ed7c161750a6891ea8b2e82b6f24b0bbed",
    "medium:character/seofon_wind/ui/battle_control_board_1.png":
        "29c30a1f3926c667f95041a18f6a5c67d665bd2eff2b84125ffef02f234f84c5",
    "medium:character/seofon_wind/ui/battle_member_status_0.png":
        "c7071bf3aa2f89301a8c178c195dfa26c9bfdd62f2ee8960aa011ac3f78fddf0",
    "medium:character/seofon_wind/ui/battle_member_status_1.png":
        "ba4b910ac6b1884483c9f5111f11430e728b350c1f3615d30cf9b36ff65c2abe",
    "medium:character/seofon_wind/ui/cutin_skill_chain_0.png":
        "261103dd084b2f03350ec6d00af9a0e461b2def0797add06158115be92d8b176",
    "medium:character/seofon_wind/ui/cutin_skill_chain_1.png":
        "2222ea82a99a7b8f7593424f94792ad08dcc547b067c3e33617225ddc7e580be",
    "medium:character/seofon_wind/ui/full_shot_1440_1920_0.png":
        "7ef9d54f2afbef0a67bc2edd8726265239057f0c9acad1b8e64ad5d59020af20",
    "medium:character/seofon_wind/ui/full_shot_1440_1920_1.png":
        "a38807324c7134b08e7b1147167202d472a55f11da91882051c72fe7b2918419",
    "medium:character/seofon_wind/ui/illustration_setting_sprite_sheet.png":
        "b09b5c6614cbc3ea353ae1e66ed278a4e465bc496d09ce7fa637360cbd494c61",
    "medium:character/seofon_wind/ui/skill_cutin_0.png":
        "5dcff3fa0bd1c2fde29c96037b4e6d6281d99edb9fdc0bb27c4783fa3ca99281",
    "medium:character/seofon_wind/ui/skill_cutin_1.png":
        "00a4773b99864f464a0fb0ec02a538739fce8028dd64434369a3a41422ecce0e",
    "medium:character/seofon_wind/ui/square_0.png":
        "e85595ac3c660f91dded01d5c2b5cff4360d6d11fcd8a63ba3a42f05dc169e48",
    "medium:character/seofon_wind/ui/square_1.png":
        "4b6a5dc397c5c710620c4876f13f2a1f8ba7e9accb37c021d3d476abeacf0b01",
    "medium:character/seofon_wind/ui/square_132_132_0.png":
        "671aeb204867a2f99b8be0b1b98edadc143e0bc71c9af897d8497dbfdb89fc0a",
    "medium:character/seofon_wind/ui/square_132_132_1.png":
        "f032914dfa40e7adb246aa79cccd783d3ea426e5e5aeda878ab0f78e741f6fdd",
    "medium:character/seofon_wind/ui/square_round_136_136_0.png":
        "a7ac467f8192f00d1984e21335a06f21329f860e6585c20702c9ef497e1e6c44",
    "medium:character/seofon_wind/ui/square_round_136_136_1.png":
        "da958a7a99f552ed3ebb993d744b71173c89f87aee720cfbf6ba788b06249ac4",
    "medium:character/seofon_wind/ui/square_round_95_95_0.png":
        "d1b8deb4e6c31c345626a4c134fd8c323c3cda8959920b1344ea8e4f7eed8977",
    "medium:character/seofon_wind/ui/square_round_95_95_1.png":
        "d585a97ac66f716367bfb364b2f5c7c75e6d6d3542b179bfa633765e0d210028",
    "medium:character/seofon_wind/ui/thumb_level_up_0.png":
        "ca5928aaf674d62b7e5656f444d795d6e507396183bcbee3661272e87aa6ffb8",
    "medium:character/seofon_wind/ui/thumb_level_up_1.png":
        "e7deab4427b4a9ab779d2d295715f1ac83d9b4b156db51bb75a02706713d5989",
    "medium:character/seofon_wind/ui/thumb_party_main_0.png":
        "b5db05787347e106059250252b78498920f990435894a2efd3f4bbeb98c24687",
    "medium:character/seofon_wind/ui/thumb_party_main_1.png":
        "aab07393f31b49a9c70b5fa15cf07e24cd6e2cc9d3a2f7aac899ef7115dd266a",
    "medium:character/seofon_wind/ui/thumb_party_unison_0.png":
        "afbf0bd5cbe6c4254b8c2f6b20571fbe805d33507dcf888384c6b392fb097f47",
    "medium:character/seofon_wind/ui/thumb_party_unison_1.png":
        "4ff801b5e5edd03fd932002387be4875f0676a8b1acc8b40ec5517de4743a71e",
    "medium:character/wind_spgirl_swim/ui/battle_control_board_0.png":
        "97f925b7aa0d8530f9878d2e9aba7fb742f53f84f375f1120596ee9dd4718442",
    "medium:character/wind_spgirl_swim/ui/battle_control_board_1.png":
        "9c4e1798002e52ab5c7740d501cc7af33f98ac5738cb3e4bf5e183ac57c9df11",
    "medium:character/wind_spgirl_swim/ui/battle_member_status_0.png":
        "b8a89e9d19e26006adb8663ef3080c6203a32ee78dd228213826bfb4aa0228af",
    "medium:character/wind_spgirl_swim/ui/battle_member_status_1.png":
        "9dc6987569c49771ca1c0c65fba63f5b5c44d278d67f1f6246db70823a21b459",
    "medium:character/wind_spgirl_swim/ui/cutin_skill_chain_0.png":
        "61a82c6d1d83f93aab45d5d9ca73ece041efce747804ddd01c8a8fabc24c77fc",
    "medium:character/wind_spgirl_swim/ui/cutin_skill_chain_1.png":
        "c8edd4e538c15ab56d8df31cc7f83762066eb0f1f272bed6009769bf98850cca",
    "medium:character/wind_spgirl_swim/ui/full_shot_1440_1920_0.png":
        "ef5a09c3fe39f822b264f3a945c47504c4d71f1d6236436b7c82fd1c79ccfd1f",
    "medium:character/wind_spgirl_swim/ui/full_shot_1440_1920_1.png":
        "4154bd6b2fff7415a22dc968a3011dde7aba6cc4d81793172ca80c949e15d9f1",
    "medium:character/wind_spgirl_swim/ui/illustration_setting_sprite_sheet.png":
        "8d9132c6c5c75766fd3643620a0e76bc3f01d19637425f913d81fa24793a6636",
    "medium:character/wind_spgirl_swim/ui/skill_cutin_0.png":
        "e3d6e1f6db9dcfa00b900adeb21bf8dee3c19c3ec0601aa37dda2ff3da9b4021",
    "medium:character/wind_spgirl_swim/ui/skill_cutin_1.png":
        "823b2c8c54d6347d9fdff2564d90727eed1996218b8154cf3cccc078104ad0a3",
    "medium:character/wind_spgirl_swim/ui/square_0.png":
        "a9677a2ced5a5259c3a56f870ca1fd0c096769a50fe31b78aa4ce92dc6af6761",
    "medium:character/wind_spgirl_swim/ui/square_1.png":
        "c357425f98e3543175deb6b5ee6eac48b4d24cf9f8bd32a1275249297eefe891",
    "medium:character/wind_spgirl_swim/ui/square_132_132_0.png":
        "7f5abc1311a2afb0d99f08e5e9213b0b4f12161a0a325c5d33e5f52d62d2792a",
    "medium:character/wind_spgirl_swim/ui/square_132_132_1.png":
        "b62aef721a8d3b38895dffd5d6c4eb2a2778d3550da6064f31a42edfbf6acdef",
    "medium:character/wind_spgirl_swim/ui/square_round_136_136_0.png":
        "42da9c4e69e42f918250db351723ea9a08ea58685042af84ef5e1e118a1ee660",
    "medium:character/wind_spgirl_swim/ui/square_round_136_136_1.png":
        "90ff38d9bf6e21deefc199306f5349d9fe544f78736224c0b1376ba7c16e7cab",
    "medium:character/wind_spgirl_swim/ui/square_round_95_95_0.png":
        "f1964156acd162eae6a1fdac2396fb0b435b7087fe690195c113fcc0d9f1d855",
    "medium:character/wind_spgirl_swim/ui/square_round_95_95_1.png":
        "ee7548b83eeb90d3b825d571f2915f235698e30fa53b59a7c9722e2c866ad313",
    "medium:character/wind_spgirl_swim/ui/thumb_level_up_0.png":
        "c0a84128ee5bd7a28db89257febdb0e4c87515afb2ee568a4ec4496d581753c4",
    "medium:character/wind_spgirl_swim/ui/thumb_level_up_1.png":
        "0a6f394937461c8daeaee99d5c384824a76a4dd68deb2c28787990c9cbf7a5cf",
    "medium:character/wind_spgirl_swim/ui/thumb_party_main_0.png":
        "dba5d8f0ea6ff5a9179f75bccf5f0e6fff07759ea2ca3da97217d25575f671e6",
    "medium:character/wind_spgirl_swim/ui/thumb_party_main_1.png":
        "93cec67dc83b30dd35673f6e24ad3d44fab102270b7a1b91bf617c8b1dd3659c",
    "medium:character/wind_spgirl_swim/ui/thumb_party_unison_0.png":
        "eaee7df2292a40c2e48a27af410e02d775514d88e92390c4e1dd172d60423844",
    "medium:character/wind_spgirl_swim/ui/thumb_party_unison_1.png":
        "915420f4795c15147b707ee825bcdae1713c64981aa2bf24eb13f984f1b25803",
}

#: 压缩包技能 DSL 的 AMF3 负载 sha256（解 deflate 后；暂存脚本重压缩不影响负载）。
GRAY_DSL_AMF3_SHA256 = {
    "battle/action/skill/action/rare5/mosiyike$mosiyike_1":
        "fe0b4b5abce7be890788ef456b90ef666d9c3bc4bbc0c4c97b9bc31ed23807ac",
    "battle/action/skill/action/rare5/mosiyike$mosiyike_2":
        "22cb49fead481d4d5512fa2cb3d1f9636da0bf7154f07146c0b4c17171cfbd82",
    "battle/action/skill/action/rare5/seofon_wind$seofon_wind_1":
        "65f277f8e581d706c0465480415726da75eadadd2d31ddc235d7b2340d338656",
    "battle/action/skill/action/rare5/seofon_wind$seofon_wind_2":
        "0110f68b659a455c4e3b136ca67e65ad910f47486791c692531724a09d522272",
    "battle/action/skill/action/rare5/wind_spgirl_swim$wind_spgirl_swim_1":
        "ef33146ec5cb1ab076040ed27ea3ffb2084bc3a08cb61e1734fe7e1b2501447d",
    "battle/action/skill/action/rare5/wind_spgirl_swim$wind_spgirl_swim_2":
        "240b5f36e16ac6d8b3c1ba97ec246f9d1b3bb5c73a3d33334c865f8cc0967bf3",
    "battle/action/skill/action/rare5/wind_spgirl_swim$wind_spgirl_swim_3":
        "71f181de7c675c162c1596c7f4dd101d2d8f3508258009e1892fc12b516842cd",
}

#: 三名角色在 11 张整表里的外层键（灰版 == live 键集合，逐表核对过）。
EXPECTED_KEYS = {
    "149995": {
        ABIL: ["1499951", "1499952", "1499953", "1499954", "1499955", "1499956"],
        LEAD: ["149995"],
        CHAR: ["149995"],
        SPEECH: ["149995"],
        STATUS: ["149995"],
        TXT: ["149995"],
        UQ: ["149995"],
        ACT: ["seofon_wind"],
        PREVIEW: ["149995"],
    },
    "149996": {
        ABIL: ["1499961", "1499962", "1499963", "1499964", "1499965", "1499966"],
        LEAD: ["149996"],
        CHAR: ["149996"],
        SPEECH: ["149996"],
        STATUS: ["149996"],
        TXT: ["149996"],
        UPSKILL: ["149996"],
        ACT: ["wind_spgirl_swim"],
        PREVIEW: ["149996"],
    },
    "149997": {
        ABIL: ["1499971", "1499972", "1499973", "1499974", "1499975", "1499976"],
        LEAD: ["149997"],
        CHAR: ["149997"],
        SPEECH: ["149997"],
        STATUS: ["149997"],
        TXT: ["149997"],
        UQ: ["149997", "1499970"],
        UPSKILL: ["149997"],
        ACT: ["mosiyike"],
        PREVIEW: ["149997"],
    },
}

#: live 输入基线（本地链尾 1.4.1053 只读取数）：{(kind, key): digest}；任何一项漂移即拒绝。
BEFORE_BY_CID = {
    "149995": {
        ("ability", "1499951"):
            "cdb078e7a857911901af2a0d241fa4588b434b9f84a2e43afe8b0d88e1f942ad",
        ("ability", "1499952"):
            "86275444eb178f47962b2ce0e6ad3b0cb4411586fa9bdfc3e722f40bd6525d86",
        ("ability", "1499953"):
            "ddcbae9b212316b1cb96432f6aa701b9249e58f7418e06244d0417f82f2776f3",
        ("ability", "1499954"):
            "fd47ab5cc96e690e107ba2f90cd5b89b15a8d5d645d575c991942fc936308c46",
        ("ability", "1499955"):
            "f2d6ced6ee58c6e7352ba228f1d79ef603e015b9cc4c3cf4ba666107947f9c7c",
        ("ability", "1499956"):
            "6a6da6f0cbeabae530036919bedf5f9869ba21b0dd42baa62a741feab6224c6a",
        ("leader", "149995"):
            "f0612ef8eacb6149b5ee1293c7cdee9cb1984976a9cf72a9e29fe1cddc533c77",
        ("table", (CHAR, "149995")):
            "b168bd383af3c257b8dbb95aa9ba9cb7a5313a8752bb0ef03370d7a2ea3872d6",
        ("table", (SPEECH, "149995")):
            "792a40e0169c8e27db09088bbb81c69c6017714ea3587fb2c84bc659e82ed2b2",
        ("nested_table", (STATUS, "149995")):
            "8c997940e83c5e09cecdaae8ad19c3da5f3e0889e071dbfe44ee82727b34ccc0",
        ("text", "149995"):
            "e7f8d4cc9de27ad4526c6c16f01344456ba330621a325b019276868deddd89b7",
        ("table", (UQ, "149995")):
            "e97f0d1b94af534e35655d4fc9983ec86ab9467f55aa10a1cee3c6bf6dc35bef",
        ("action", "seofon_wind"):
            "1f18c87921b7ad7e42e0e06b29eae416b3d364f94d2a0963bd01f8fc90179910",
        ("table", (PREVIEW, "149995")):
            "1ae5348a0c0062e3d19b734d1485636c2ec8789cfedc8eebe24c5e6b15bb5df3",
        ("dsl", "battle/action/skill/action/rare5/seofon_wind$seofon_wind_1"):
            "076c13bce7937be269f7a08d8eaa3ebcf0075752c6eea49bed4a5ad1efb41e12",
        ("dsl", "battle/action/skill/action/rare5/seofon_wind$seofon_wind_2"):
            "35827244e4c83b44f07ae2caf148337605f7ff392e3476525747ace81abd6772",
        ("server_text", "149995"):
            "e7f8d4cc9de27ad4526c6c16f01344456ba330621a325b019276868deddd89b7",
        ("nested_table", (CIMG, "149995")):
            "b0e180663d5e005c58ffb3d3729590de494a98bc8427a82cd566ac264113f3d1",
        ("nested_table", (FSA, "149995")):
            "f57a23add894114c7873c01a4de2988a4244d3f5a564bd645522bf395200a724",
        ("table", (TRIM, "character/seofon_wind/ui/full_shot_1440_1920_0")):
            "07d38f5ff47f56fdd2965a842430cb42a925c12767ed6d62734b4ae8270caab7",
        ("table", (TRIM, "character/seofon_wind/ui/skill_cutin_0")):
            "2721917d3ccd0ea9833144d08bb4d2f2ca1fa9bf7d5419d00e348fa50db4f7b8",
        ("table", (TRIM, "character/seofon_wind/ui/full_shot_1440_1920_1")):
            "b9455dc2fbb735769e519f9ab66f5d6156b65db0ad83c1765e117a8ea9f8b6d5",
        ("table", (TRIM, "character/seofon_wind/ui/skill_cutin_1")):
            "4e8007a7d87a59b2f9917eaff214fbf14d02f0162904f25367d6aeafebcb39c4",
        ("file_sha256", ("android", "character/seofon_wind/ui/skill_cutin_0.atf.deflate")):
            "58fec7efced534ab5b41d022df1e2c1f2024d6514139a493ac994e50a217510b",
        ("file_sha256", ("android", "character/seofon_wind/ui/skill_cutin_1.atf.deflate")):
            "6247680a95904163bcf5bc389c5903875e3cdd529d616c36673d62d5e4a4e8ce",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada.atlas.amf3.deflate")):
            "b75bdee8e0a1bab2d4951d7884cf0e70217cc590bece5ce68ffefecf5f9e3a8d",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada.parts.amf3.deflate")):
            "3a4a7e3056e926844a62b85804a409c6731f119730054002eae2f0ad26811feb",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada.png")):
            "727255ea4d727d8dc40d9972ddafeb35e33b2f1b842814ebaa7f6d5f74bf094d",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada.timeline.amf3.deflate")):
            "1c39252e5a3bc907d43fe1844a0c80da33ef895064603ba3a90dceeb62048455",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_avatar.parts.amf3.deflate")):
            "fe2447496f9cdf8d06015c0b3c93c36f9604640f1ad3e1f65a73a86f20bd7bb1",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_avatar.timeline.amf3.deflate")):
            "c7b902537f9a488b8e3537d23c38e1243632b5951e2e6138dd402d1fa8325a51",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_avatar_summon.parts.amf3.deflate")):
            "b5176d360491efe37db1bd351b1e92751075f42be4c43e447c1a104d549cb8ad",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_avatar_summon.timeline.amf3.deflate")):
            "7974f0e87c120fdf34e5871702d8e5c39db6284fb4302e33e003f5b704a18396",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_charge.parts.amf3.deflate")):
            "028beba39ddcce00bf9787d95cbbcbe4a6751f463970f1b006057b3702de3977",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_charge.timeline.amf3.deflate")):
            "829c77cb9a66563f0570d142a9c59e1f8586832dde75d710d0bc92833468da1b",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_hit_burst.parts.amf3.deflate")):
            "aab307f85b78a6d5cc57b6a6fea81d778b2b0099b97f56f5e3f318844c89297e",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_hit_burst.timeline.amf3.deflate")):
            "4c62a222c3602985d5ac0a65f03f19ea4e56b5c1a22e46188e7c3cab6da574fb",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_volley_sword1_own.parts.amf3.deflate")):
            "97dd407b6eee548204bd3fe019932cfaa5834a684d40fcaebc94552cfb99131d",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_volley_sword1_own.timeline.amf3.deflate")):
            "b0eca996f790088213fb0417f34fd1367962a29114bde985160949fb0d5d5924",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_volley_sword2_own.parts.amf3.deflate")):
            "22afd78abbb29195220a5ceeb7a44ec381a61aec71ff99fd343c5b770532b1c0",
        ("file_sha256", ("common", "battle/effect/skill_unique/seofon_wind/cien_mil_espada/cien_mil_espada_volley_sword2_own.timeline.amf3.deflate")):
            "b0eca996f790088213fb0417f34fd1367962a29114bde985160949fb0d5d5924",
        ("file_sha256", ("common", "character/seofon_wind/battle/character_detail_skill_preview.battle.amf3.deflate")):
            "65260b9bb8253390b92b5d78ee127090d83d63aec7070bff3e370bd2b92bb4f6",
        ("file_sha256", ("common", "character/seofon_wind/pixelart/pixelart.frame.amf3.deflate")):
            "0fd0755551c5d48ae4ca72780233f43ca1c127e998d47cf2ed4720dc1649c491",
        ("file_sha256", ("common", "character/seofon_wind/pixelart/pixelart.timeline.amf3.deflate")):
            "51496c1a7e3bb20adce39eb963f79da2f7f9046eea131a323bef21b26b68e687",
        ("file_sha256", ("common", "character/seofon_wind/pixelart/special.frame.amf3.deflate")):
            "d59cb7971b996abe24822386e70b3e13e06045f814f875a5d6c9f2fac535fc08",
        ("file_sha256", ("common", "character/seofon_wind/pixelart/special.timeline.amf3.deflate")):
            "0fc764de3aaac697bcfc49e0dc8b2adc686c9df56bf92552560d8a6ce2518bfd",
        ("file_sha256", ("common", "character/seofon_wind/pixelart/special_sprite_sheet.atlas.amf3.deflate")):
            "37c97590867c2b7e2d0fcc3a0249a95b6fc7f9706b6ce5b03b11648609eb0c92",
        ("file_sha256", ("common", "character/seofon_wind/pixelart/special_sprite_sheet.png")):
            "f0ae222d3e665ede53e326f802e544053d7c9b8a26a0f4612558b38b7ccf152e",
        ("file_sha256", ("common", "character/seofon_wind/pixelart/sprite_sheet.atlas.amf3.deflate")):
            "d8b4e37b9aeb39f8152986477d44c9d27d85ec47d5b9972d1031c8f4c340a3d8",
        ("file_sha256", ("common", "character/seofon_wind/pixelart/sprite_sheet.png")):
            "8c9857937cc5f7868ce1cbb0d44f1dd589e4a58e638dba9ce706b6d49d572948",
        ("file_sha256", ("common", "character/seofon_wind/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate")):
            "e4fc292d56eefceaf1f5f56d0cb8e681f229efdae1028cf57a562994a8c6bb96",
        ("file_sha256", ("medium", "character/seofon_wind/ui/battle_control_board_0.png")):
            "e46ef6ec0e134f5ab80bcf528965ec4e6326af1e347f723ec738782b5205999c",
        ("file_sha256", ("medium", "character/seofon_wind/ui/battle_control_board_1.png")):
            "e2d72093d2d64c6c9abd5e9cb44e6c4cadb6d22eeb353ace9a17f08b94919eff",
        ("file_sha256", ("medium", "character/seofon_wind/ui/battle_member_status_0.png")):
            "268a30f7a291676b1c5132ca5fee55df0757b621a6028673d8c934622999f377",
        ("file_sha256", ("medium", "character/seofon_wind/ui/battle_member_status_1.png")):
            "847864c7a9f166d320fd96fb30447e73bbf7edeebe75f911b8f12a94d6829bef",
        ("file_sha256", ("medium", "character/seofon_wind/ui/cutin_skill_chain_0.png")):
            "5dabf8b3e5983f2cd8caf6a73097a31e6f15deded58fe2e7a2984741df2776c5",
        ("file_sha256", ("medium", "character/seofon_wind/ui/cutin_skill_chain_1.png")):
            "96a299d2e35dd6c87dde59a31eeb8603dc7de34b3c63353e06499aefb2446554",
        ("file_sha256", ("medium", "character/seofon_wind/ui/full_shot_1440_1920_0.png")):
            "bf4180eae13b16b24b116b4eebcc9de4c87234e615c525b26615c179fdf68759",
        ("file_sha256", ("medium", "character/seofon_wind/ui/full_shot_1440_1920_1.png")):
            "243e73bdc8f1f5c9289534223010d54a7d4c517524e91e0d5c049850ced2002b",
        ("file_sha256", ("medium", "character/seofon_wind/ui/illustration_setting_sprite_sheet.png")):
            "9ec4d632fe1daa2aad2e69293308ca18e10ec914b1833e4487e9ab8609554bfb",
        ("file_sha256", ("medium", "character/seofon_wind/ui/skill_cutin_0.png")):
            "e29c9ea69eea82dff33a94ea8a5863158b814f8a4abace45669d58e767dfbf66",
        ("file_sha256", ("medium", "character/seofon_wind/ui/skill_cutin_1.png")):
            "995259e751a6e699630d6e6bf1a13caae7e9c3961423bdfadc54f993663a6de7",
        ("file_sha256", ("medium", "character/seofon_wind/ui/square_0.png")):
            "9854a2bc2a858fc6d73f09c9d3418de638d40ddb5f4692ceab751aa5708c1074",
        ("file_sha256", ("medium", "character/seofon_wind/ui/square_1.png")):
            "ac8f862d33986b10697d7bf75888056073e9b741c2b2942417b0bfb753a1d1bd",
        ("file_sha256", ("medium", "character/seofon_wind/ui/square_132_132_0.png")):
            "381b4efa31ecdb8b8197ec4f13fe2ccecc7ae754f603d280b32df50e7f55dc0e",
        ("file_sha256", ("medium", "character/seofon_wind/ui/square_132_132_1.png")):
            "f654c72be58a88d85d54c83529b4ddcab2c0bf4f9b03c0e3633df78ed3c46fd7",
        ("file_sha256", ("medium", "character/seofon_wind/ui/square_round_136_136_0.png")):
            "864a89c8202f4576cdc52965ac28b2e112762478b86e9001e15a77b8e139236e",
        ("file_sha256", ("medium", "character/seofon_wind/ui/square_round_136_136_1.png")):
            "f14744fdc865ad113d328f3ce84699f451f21a6e0a8cbbc9f09081b64b80a25e",
        ("file_sha256", ("medium", "character/seofon_wind/ui/square_round_95_95_0.png")):
            "5a04c4a604aab48cdbbdd57dcc3b90eeae24d5fd2f696976a78b33f8f18ab3d6",
        ("file_sha256", ("medium", "character/seofon_wind/ui/square_round_95_95_1.png")):
            "a19913298a53e39bcf6770d31cd647ae79078ce50dbb6cbfaba5ff4ed89f781c",
        ("file_sha256", ("medium", "character/seofon_wind/ui/thumb_level_up_0.png")):
            "e7701466e7f48782c961881cf0380e0d2fb449dfac9b931f8ef0dcd0d1f4260a",
        ("file_sha256", ("medium", "character/seofon_wind/ui/thumb_level_up_1.png")):
            "64715609ae50da3be5d2acb7d1f150c57985bd5fd7f70f801cd1d66f2d11ede1",
        ("file_sha256", ("medium", "character/seofon_wind/ui/thumb_party_main_0.png")):
            "f83ca81c9edcd016aabc8151b7e12e4ab3dc5ae7dce211678a493d88a8cb79f6",
        ("file_sha256", ("medium", "character/seofon_wind/ui/thumb_party_main_1.png")):
            "b97702c6577624342203b1f69b24c89bc9d6d0bf14812df1e99000f2cb5d5470",
        ("file_sha256", ("medium", "character/seofon_wind/ui/thumb_party_unison_0.png")):
            "773d7b2cc2f227fd22569aa47449b93b63e4e51a2586e51c3ce223046a35c3cc",
        ("file_sha256", ("medium", "character/seofon_wind/ui/thumb_party_unison_1.png")):
            "93951b61469644c4ad5fc0b0e1e207f35f86d90e14771a296a26dc038342629b",
    },
    "149996": {
        ("ability", "1499961"):
            "2efb8e2aaa637ffe97663b5f54a5f0c21da0ed20ad8b0eec091646884de39448",
        ("ability", "1499962"):
            "832833dcc750f67c2ed540c20c8aaae1b35c37fcfbfbb7dc00c26ac24c86267b",
        ("ability", "1499963"):
            "346990e322a25e4da24b0db59c85b6a4c22026f61d311b47b71626cab4c454fa",
        ("ability", "1499964"):
            "9b9903d35518e6f87851208d3aaeca804f67816693d1fa78665dcb5453a93518",
        ("ability", "1499965"):
            "6baff40b9c211380da2db242b74326dc012b36256d84b185552b2873f065b9a0",
        ("ability", "1499966"):
            "0958a93042a6fdf8e5379e705f0be8ff607cbc5891362c02e53b522d43559996",
        ("leader", "149996"):
            "c21e7ca01594c50004b2461f1fce38371b073eee8a90fe4a48bafbe447925ba6",
        ("table", (CHAR, "149996")):
            "71a67487b5901a22a1228c1d076398ab713269059aa7c8e847396be7062e12e9",
        ("table", (SPEECH, "149996")):
            "08d055a64fbfb79c0df5e38a94646d50c07da07b528ee39b38d13eb2009ffd21",
        ("nested_table", (STATUS, "149996")):
            "0bc4ad146439fc18fe8984e545e19dce35bee0ad2d779c884b47137466e77982",
        ("text", "149996"):
            "3701a741cba7ebcbee5aaa45b15ce96dae9e26acf11266b30908d051d32a468f",
        ("table", (UPSKILL, "149996")):
            "712de961b0c45322b7c2fa49de61f4dd05d15415bee4d37d94c6639aeea481d4",
        ("action", "wind_spgirl_swim"):
            "adf9f2d9ff4341e069f264d91a28fa8c93e82263b5ae3696d7f93070e4ff5097",
        ("table", (PREVIEW, "149996")):
            "a8da063ee30ce4f0d0f25f2877ec471cce1525fea3d766cfab09bcf95fb5f7f4",
        ("dsl", "battle/action/skill/action/rare5/wind_spgirl_swim$wind_spgirl_swim_1"):
            "8b1243eaab7c0deb8a5b769c275106897c69c560396d37a3fde8cbd165b0febb",
        ("dsl", "battle/action/skill/action/rare5/wind_spgirl_swim$wind_spgirl_swim_2"):
            "d633db78e51b9a43e540631ea80e4a0668ff18525a4ba3f5581713ed2b0df1c0",
        ("dsl", "battle/action/skill/action/rare5/wind_spgirl_swim$wind_spgirl_swim_3"):
            "5fc940c20bd9f7d1656aef6fe6341cc40cc43361c7432dbb0ac08506ab88027f",
        ("server_text", "149996"):
            "3701a741cba7ebcbee5aaa45b15ce96dae9e26acf11266b30908d051d32a468f",
        ("nested_table", (CIMG, "149996")):
            "883dd683b63f5580722c50badde34cf8f66a351811b31e2a310bc8af588bdd1a",
        ("nested_table", (FSA, "149996")):
            "7f0cf44ce71ab5d4b6f19f06c9f5a659f4aaf79db092d6c898b246cf28926653",
        ("table", (TRIM, "character/wind_spgirl_swim/ui/full_shot_1440_1920_0")):
            "b6a08df4b9c1a9517164df1414a6d3f36bec2cfa4d818642856ddce0a3cbff0e",
        ("table", (TRIM, "character/wind_spgirl_swim/ui/skill_cutin_0")):
            "95c783b5fefa13a5e1a0bf9f60325b6ab152f5e70e86c02a22ecf365a0cd984f",
        ("table", (TRIM, "character/wind_spgirl_swim/ui/full_shot_1440_1920_1")):
            "c6ca0e0d64ec2bd893d749803ad3a53a96fc8e3710fdabc26392a0ea8a199846",
        ("table", (TRIM, "character/wind_spgirl_swim/ui/skill_cutin_1")):
            "4e8007a7d87a59b2f9917eaff214fbf14d02f0162904f25367d6aeafebcb39c4",
        ("cas", "ability_skill_wind_spgirl_swim_whirlwind"):
            "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        ("dsl", "battle/action/skill/action/ability_skill/ability_skill_wind_spgirl_swim_whirlwind$ability_skill_wind_spgirl_swim_whirlwind"):
            "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        ("file_sha256", ("android", "character/wind_spgirl_swim/ui/skill_cutin_0.atf.deflate")):
            "fc1ec5388988a336979a57ea185f84256277acdef6dc42a452bebd937548dbe4",
        ("file_sha256", ("android", "character/wind_spgirl_swim/ui/skill_cutin_1.atf.deflate")):
            "416cc4cabded3da8660b90d6ad0a54fc36516e45c2d0c5df0be46631e86e3a42",
        ("file_sha256", ("common", "battle/effect/skill_unique/wind_spgirl_swim/wind_spgirl_swim.atlas.amf3.deflate")):
            "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        ("file_sha256", ("common", "battle/effect/skill_unique/wind_spgirl_swim/wind_spgirl_swim.parts.amf3.deflate")):
            "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        ("file_sha256", ("common", "battle/effect/skill_unique/wind_spgirl_swim/wind_spgirl_swim.png")):
            "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        ("file_sha256", ("common", "battle/effect/skill_unique/wind_spgirl_swim/wind_spgirl_swim.timeline.amf3.deflate")):
            "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        ("file_sha256", ("common", "character/wind_spgirl_swim/battle/character_detail_skill_preview.battle.amf3.deflate")):
            "af96f9b510cfdac65bbb1e8a4c1764f6d3b84489b88be09a7fd6847b4da099ec",
        ("file_sha256", ("common", "character/wind_spgirl_swim/pixelart/pixelart.frame.amf3.deflate")):
            "c8d5ba6159428a041d0238d789740b13e5859f95ea9555b88cab3770fe07826f",
        ("file_sha256", ("common", "character/wind_spgirl_swim/pixelart/pixelart.timeline.amf3.deflate")):
            "51496c1a7e3bb20adce39eb963f79da2f7f9046eea131a323bef21b26b68e687",
        ("file_sha256", ("common", "character/wind_spgirl_swim/pixelart/special.frame.amf3.deflate")):
            "45ee93c8284b6d3b5972568b3a6fd8c102140f8707aa2f296b2a018a18a6831e",
        ("file_sha256", ("common", "character/wind_spgirl_swim/pixelart/special.timeline.amf3.deflate")):
            "19ae489d27ca218c79b80c9b3772d8e3d7ed7b0f0b2518222f5b601b77632730",
        ("file_sha256", ("common", "character/wind_spgirl_swim/pixelart/special_sprite_sheet.atlas.amf3.deflate")):
            "97cb6738a0b0ff0b640a12e8d370aaec7df07a0860d0e766488cae34e99ad8e3",
        ("file_sha256", ("common", "character/wind_spgirl_swim/pixelart/special_sprite_sheet.png")):
            "e5e13dcd9264ffa5f84c0f9dd4b96728c6126b85d8eb9790cfe6fffd3e2b039a",
        ("file_sha256", ("common", "character/wind_spgirl_swim/pixelart/sprite_sheet.atlas.amf3.deflate")):
            "96fea54b9f137c9759cab7ea7cc87b2e22c071086edb942b825122b9157b095a",
        ("file_sha256", ("common", "character/wind_spgirl_swim/pixelart/sprite_sheet.png")):
            "3e910cdf5bce19d2dec3b011c8425e9d884e30a00f3ec12381bfec2e0d066c5f",
        ("file_sha256", ("common", "character/wind_spgirl_swim/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate")):
            "da34b59dbf2eb35c79ff7bb968a204df94899acc15cc2da5e8705174a4666f47",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/battle_control_board_0.png")):
            "7ad5ae6904f3fe2f1bcaa4962388cacedd6558b3f2ce7f7e5d3179098ab55bc4",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/battle_control_board_1.png")):
            "71bb8c8ac4b716beaf84bf17fced22713eb43ba8d20156d77c94b6278d8db908",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/battle_member_status_0.png")):
            "d61e10762089760e83b21f45f23701ac44ff2ac2b6fa7f4f686ce0a70589331c",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/battle_member_status_1.png")):
            "4cc2cbfe0aa26917d9cebd56bd8f807f4b2058c38ef86f11325b36926d687cf0",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/cutin_skill_chain_0.png")):
            "0f8e4c2cf245fc96af5124b3d781c363d56d49430e50157d3dd4e49dbe3fa038",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/cutin_skill_chain_1.png")):
            "f06beeb36ca7a44e17c73734ea909eb855b6ccb935b231b1a5626fd310d76ba6",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/full_shot_1440_1920_0.png")):
            "71a746ae839913adc06c003ebacb41c1e2b15e91373fbc4b281c2b6ccfb5c9fa",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/full_shot_1440_1920_1.png")):
            "2eb35a31275a85acc727e03184df25d2175f72a064316158d87e352872a432da",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/illustration_setting_sprite_sheet.png")):
            "94fd3e3ebc93b092587e24eb6c7978e6de0d410f09f483c92059774a54879d43",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/skill_cutin_0.png")):
            "bb672b665f0e18acf590128e409bb0b819ffa40e884c8e800397c757f399ab89",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/skill_cutin_1.png")):
            "da56fc17023e991012d68c46f70a3741fc6cd24a1d76f4056559bdd6a34ce317",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/square_0.png")):
            "48d98a770d1b77604ff5fdbdcc6c38932fe4409e132b213fa28323a9ad46a838",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/square_1.png")):
            "b3dc656f4866f620454a0c9ac1d541a3bd5a3fc3a45beb12a279d64e533f087a",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/square_132_132_0.png")):
            "28e2490616ffea939ce71130e08bcc40a97c81aafed8cd44aced2c52550c0d1c",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/square_132_132_1.png")):
            "736bce4d1ba5bbae1df918136841dd6402b297122ab4440961f3063ef8a57e7e",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/square_round_136_136_0.png")):
            "9e59ee352dcd274e660253db9df474cc3c5f06b777010b87c99c16a62033135e",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/square_round_136_136_1.png")):
            "a177140edaa7c222a60e87f8dce6fc1228682204b59f85a80df4d111834bc829",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/square_round_95_95_0.png")):
            "9e379dfc1ec4434841497ac21b05b27dc2deabbb2de1905192fe1b1330c8260e",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/square_round_95_95_1.png")):
            "1db18f2dcb48cf86b964f687b62f46aac7b9ad6b7e838e8c46d8ce8de6daa798",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/thumb_level_up_0.png")):
            "b0c1b85369902f9d15ff2cd51d037317da02553104a2de081488e5404c7278f2",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/thumb_level_up_1.png")):
            "612499f9c8ae92fd01bff5974a4664d70b816b3b088025c12d8f7a3a57c22fcd",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/thumb_party_main_0.png")):
            "060a5a3db10e959851e7b6ac60be1af396afce08c4016ea5885b83ebbbdf0fed",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/thumb_party_main_1.png")):
            "1935a92668122616b203166b8d4f938174c35a6b534d377bc1575001ac93f782",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/thumb_party_unison_0.png")):
            "7f48fa26a18d10be9d03a55434e92ccd6c55cc83fbf5c490e6e6519c843ca4fb",
        ("file_sha256", ("medium", "character/wind_spgirl_swim/ui/thumb_party_unison_1.png")):
            "ca5abbe0966e1d78f7193912b77f4df1dba9036c4090380075a28511f857d7c1",
    },
    "149997": {
        ("ability", "1499971"):
            "f310d6741ac6555cc44e9f7fee3739847b833e079f8365237e16571345fc8e6c",
        ("ability", "1499972"):
            "9aaa2fa9a9546021a45533af68901a9a241052c40b3520fc6bd344a1cb634c0a",
        ("ability", "1499973"):
            "67dbdecf91e159f716d4ced6cdab46cc3a2d0ceffcc61cc83acd4d38cd5460b2",
        ("ability", "1499974"):
            "c93412688ffbb5ca342555b0c429ebe493483fd0ee34ac7b73ab62329ccb0b3f",
        ("ability", "1499975"):
            "ff9b6f177c8dc9e2bec0766986bae09466773719e13af939056a6e2bebc38b02",
        ("ability", "1499976"):
            "669b8e104f284eb75745797f91d628271d02693f2a5702131219d596739cbfa7",
        ("leader", "149997"):
            "fa27b1df32398053c67429e8e1f2cbe96c2cc79f5cd1657a2ee08ca1d2a16f1c",
        ("table", (CHAR, "149997")):
            "21a0d5ef2e3b7d5552190783b0653c89737e188dbb11b8960db9a17a8bf0ef66",
        ("table", (SPEECH, "149997")):
            "235035af4b620093813e095b929685c043351885a9e26d6fa670a5fcbf9bdcba",
        ("nested_table", (STATUS, "149997")):
            "d4d6867c82be4acf9ff30e4acdc5023578065267a5e8f4d4f2323e5f75984e9c",
        ("text", "149997"):
            "c19c063c5387e9ff34cfdf203e6d322942ea1fa68dcd2beab01f99bea7be4520",
        ("table", (UQ, "149997")):
            "a1a095dbc0dc908a31f0f4931e71f719899c0b28c5222fa5932055922845765e",
        ("table", (UQ, "1499970")):
            "1148be80be51e8317b857fae0517abb7235a4d4db4c23772a845369f1d9fe516",
        ("table", (UPSKILL, "149997")):
            "4844eaf7397037dc7d08f6faee762f5be1e687201ea654b0b3b593892c2a6009",
        ("action", "mosiyike"):
            "43eb1f80706e10346949b0705094f36a2737ffb63e80fef86359be1a74e73d70",
        ("table", (PREVIEW, "149997")):
            "a8da063ee30ce4f0d0f25f2877ec471cce1525fea3d766cfab09bcf95fb5f7f4",
        ("dsl", "battle/action/skill/action/rare5/mosiyike$mosiyike_1"):
            "8a21257d7e0b4844c18f7bb36e105633d5e983ea4a2c00d97afe61aae179b594",
        ("dsl", "battle/action/skill/action/rare5/mosiyike$mosiyike_2"):
            "cf8ecd48d87f6e9355ce1c0d825be99a52ad7e67eb04af712bfa8bf9e1fe08d7",
        ("server_text", "149997"):
            "c19c063c5387e9ff34cfdf203e6d322942ea1fa68dcd2beab01f99bea7be4520",
        ("nested_table", (CIMG, "149997")):
            "a520f8b0efbe74daef4b9d9af8ee14e64db577a76acd7b2bce3b49f3e1891a07",
        ("nested_table", (FSA, "149997")):
            "43d6c40ed101cddd2f97470be471b06408389ed737c19a535b496295f1c5c990",
        ("table", (TRIM, "character/mosiyike/ui/full_shot_1440_1920_0")):
            "b1bf4da9455523e67f7db833077c535f22d6479392de15bf5f0f1ed81baff7e2",
        ("table", (TRIM, "character/mosiyike/ui/skill_cutin_0")):
            "35cc935495210a260db86dc4da6cf4b5359f875d559d700c067eb1d93d52b1ca",
        ("table", (TRIM, "character/mosiyike/ui/full_shot_1440_1920_1")):
            "b5aef63edc8393075f1a85f2968cf3d5965ed234bc542e3c4066a4a01b3a2802",
        ("table", (TRIM, "character/mosiyike/ui/skill_cutin_1")):
            "4e8007a7d87a59b2f9917eaff214fbf14d02f0162904f25367d6aeafebcb39c4",
        ("file_sha256", ("android", "character/mosiyike/ui/skill_cutin_0.atf.deflate")):
            "149d47499ac82e2c4e46480d796fe1a385d0352408000d42aa5ad2af12623144",
        ("file_sha256", ("android", "character/mosiyike/ui/skill_cutin_1.atf.deflate")):
            "149d47499ac82e2c4e46480d796fe1a385d0352408000d42aa5ad2af12623144",
        ("file_sha256", ("common", "battle/effect/skill_unique/mosiyike/mosiyike_shield/mosiyike_shield.atlas.amf3.deflate")):
            "e279fec3ee42e9407e5d3ee9ff3458476c3e45e0507b0bb3a712742d5aa734c3",
        ("file_sha256", ("common", "battle/effect/skill_unique/mosiyike/mosiyike_shield/mosiyike_shield.png")):
            "f109b197e738ec666952cc6fcead43fe59223be57b07d826585659e01273ae94",
        ("file_sha256", ("common", "battle/effect/skill_unique/mosiyike/mosiyike_shield/mosiyike_shield_gather.parts.amf3.deflate")):
            "7c5082fa53a6b82a693842fc8b78ce46287759076f77d0d464e3ffe061ecf15c",
        ("file_sha256", ("common", "battle/effect/skill_unique/mosiyike/mosiyike_shield/mosiyike_shield_gather.timeline.amf3.deflate")):
            "4a47f87afc685348418f6bd21da622f02339d77848cd81fc20f16f43f2d9e087",
        ("file_sha256", ("common", "battle/effect/skill_unique/mosiyike/mosiyike_shield/mosiyike_shield_loop.parts.amf3.deflate")):
            "5b750188edda41eb7e96009985cad478d8a93a275745b8575d40217ee31097e3",
        ("file_sha256", ("common", "battle/effect/skill_unique/mosiyike/mosiyike_shield/mosiyike_shield_loop.timeline.amf3.deflate")):
            "12b5ea8ed332b121628b4ae88b7100657ca1f05c6ab8f11b4ce64ef4fe3abc3e",
        ("file_sha256", ("common", "character/mosiyike/battle/character_detail_skill_preview.battle.amf3.deflate")):
            "784f5d602bac71c02296c3622e17094896589c8b1a84bf290d2f703e1dd000e3",
        ("file_sha256", ("common", "character/mosiyike/pixelart/pixelart.frame.amf3.deflate")):
            "89aeb5edbd45ad09b78bdca455e857c2179b5b95df0e33f564f1a157beed8e29",
        ("file_sha256", ("common", "character/mosiyike/pixelart/pixelart.timeline.amf3.deflate")):
            "51496c1a7e3bb20adce39eb963f79da2f7f9046eea131a323bef21b26b68e687",
        ("file_sha256", ("common", "character/mosiyike/pixelart/special.frame.amf3.deflate")):
            "e331636eba3e54b735f5da75f6b504589497ca3b37c059b1041d272402ad3a2e",
        ("file_sha256", ("common", "character/mosiyike/pixelart/special.timeline.amf3.deflate")):
            "8a52e176b50b446f3fd6fe66f15a57b56b9e4fb26d2d6cae1076ce0aba0a7074",
        ("file_sha256", ("common", "character/mosiyike/pixelart/special_sprite_sheet.atlas.amf3.deflate")):
            "1529c15b41954a90b653e6ae83735cad9826f1d3fb2760375ff208cdedf44149",
        ("file_sha256", ("common", "character/mosiyike/pixelart/special_sprite_sheet.png")):
            "5f8305d7b7734b4a407db33584ea1b53bf77c73a337b1dbf5e7121e13421b12c",
        ("file_sha256", ("common", "character/mosiyike/pixelart/sprite_sheet.atlas.amf3.deflate")):
            "05f1323a62f944626c7d3025f97f590d103c14502a5d08b638ac9b7940c40254",
        ("file_sha256", ("common", "character/mosiyike/pixelart/sprite_sheet.png")):
            "0eebd1f5beed44807e1ca9ba1998cf766db64bde6fa3294077425c6d2514eb77",
        ("file_sha256", ("common", "character/mosiyike/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate")):
            "df3907e09baa90180ed92544eb000c7b2dea46b93d881d78077fdc566b48b743",
        ("file_sha256", ("medium", "character/mosiyike/ui/battle_control_board_0.png")):
            "70063cf6bce53161fab5d718dd67fb1554b62cd39c298e6203d2cdfc8aae4797",
        ("file_sha256", ("medium", "character/mosiyike/ui/battle_control_board_1.png")):
            "70063cf6bce53161fab5d718dd67fb1554b62cd39c298e6203d2cdfc8aae4797",
        ("file_sha256", ("medium", "character/mosiyike/ui/battle_member_status_0.png")):
            "47d9d9fd3374a6770f1748ff0e3ae5df74e2c430d81a308032829523383891ed",
        ("file_sha256", ("medium", "character/mosiyike/ui/battle_member_status_1.png")):
            "aa6aeff70dd159f2a918ff8f030a4863e8f073656954035d513a29a1bca9ae93",
        ("file_sha256", ("medium", "character/mosiyike/ui/cutin_skill_chain_0.png")):
            "88a5cdb0bf90dabd226c2e3cf7542bc301cd99f9d01707a5960a75c11dd5ccf2",
        ("file_sha256", ("medium", "character/mosiyike/ui/cutin_skill_chain_1.png")):
            "88a5cdb0bf90dabd226c2e3cf7542bc301cd99f9d01707a5960a75c11dd5ccf2",
        ("file_sha256", ("medium", "character/mosiyike/ui/full_shot_1440_1920_0.png")):
            "df5b0b288afc7ce2ce9b8fe72f9343195e7bf128e4eb6b3859f96f8440b70b77",
        ("file_sha256", ("medium", "character/mosiyike/ui/full_shot_1440_1920_1.png")):
            "6529d27f4a4e4ec56f0c7c646a8e578dc5ed17286ff1338551b6555ab4f4770b",
        ("file_sha256", ("medium", "character/mosiyike/ui/illustration_setting_sprite_sheet.png")):
            "d25086f187a97390041089e2e6071c036c1e4d52824b5f45f8908ebd7e1c71b2",
        ("file_sha256", ("medium", "character/mosiyike/ui/skill_cutin_0.png")):
            "b56e27d968712b0ce52a889013abee43553e055b8dfdc57ba80c4a4103aac7b2",
        ("file_sha256", ("medium", "character/mosiyike/ui/skill_cutin_1.png")):
            "b56e27d968712b0ce52a889013abee43553e055b8dfdc57ba80c4a4103aac7b2",
        ("file_sha256", ("medium", "character/mosiyike/ui/square_0.png")):
            "23a0b853cfff7935e67b1a523fbaf1018c52668488e5e8597b87311685ed89e0",
        ("file_sha256", ("medium", "character/mosiyike/ui/square_1.png")):
            "23a0b853cfff7935e67b1a523fbaf1018c52668488e5e8597b87311685ed89e0",
        ("file_sha256", ("medium", "character/mosiyike/ui/square_132_132_0.png")):
            "515748343e0f73cefd450c4a09031ff71666020c427f9d70713c41e25292d628",
        ("file_sha256", ("medium", "character/mosiyike/ui/square_132_132_1.png")):
            "515748343e0f73cefd450c4a09031ff71666020c427f9d70713c41e25292d628",
        ("file_sha256", ("medium", "character/mosiyike/ui/square_round_136_136_0.png")):
            "ec08c9ad66461c423c63378e989f579aed9e782ab856ca276b4ba3e7dc340925",
        ("file_sha256", ("medium", "character/mosiyike/ui/square_round_136_136_1.png")):
            "ec08c9ad66461c423c63378e989f579aed9e782ab856ca276b4ba3e7dc340925",
        ("file_sha256", ("medium", "character/mosiyike/ui/square_round_95_95_0.png")):
            "75497e67cd47085d3d5a2d8d4a8d7c044138e5732e4485c55b7a1fb51178ddab",
        ("file_sha256", ("medium", "character/mosiyike/ui/square_round_95_95_1.png")):
            "75497e67cd47085d3d5a2d8d4a8d7c044138e5732e4485c55b7a1fb51178ddab",
        ("file_sha256", ("medium", "character/mosiyike/ui/thumb_level_up_0.png")):
            "5dcde7f39fde95fdc2a47c9efda61e203523477ef4917ccbadce0be189729e74",
        ("file_sha256", ("medium", "character/mosiyike/ui/thumb_level_up_1.png")):
            "5dcde7f39fde95fdc2a47c9efda61e203523477ef4917ccbadce0be189729e74",
        ("file_sha256", ("medium", "character/mosiyike/ui/thumb_party_main_0.png")):
            "819ccbd0d6b2ff285bf73e3d5ac65ef59d1abd29027fe6f9b8cdd8d3e43801ed",
        ("file_sha256", ("medium", "character/mosiyike/ui/thumb_party_main_1.png")):
            "819ccbd0d6b2ff285bf73e3d5ac65ef59d1abd29027fe6f9b8cdd8d3e43801ed",
        ("file_sha256", ("medium", "character/mosiyike/ui/thumb_party_unison_0.png")):
            "28d4aee2377cd600b086c08be6555376fc9e172ab26a439cd53b51263d6e8e38",
        ("file_sha256", ("medium", "character/mosiyike/ui/thumb_party_unison_1.png")):
            "28d4aee2377cd600b086c08be6555376fc9e172ab26a439cd53b51263d6e8e38",
    },
}

#: 灰链 1.4.87→1.4.88 边的旋风程序（西微 bigwing_shaman_smr21_2 满强化本体去 StopBall、SLv/ALv 区间冻结到满值）。
WHIRLWIND_TREE = ['ActionDsl', 1, ['None'], False, False, False, False, False, False, False, 0,
 ['Block',
  [['Command',
    ['FindNearSubjects', -18, 1, 49, ['CreateImaginaryTarget', -1], 0,
     ['Block',
      [['Command',
        ['ShowEffect', '竜巻演出',
         ['SpecifyEffectDirectly', 'battle/effect/skill_unique/bigwing_shaman_smr21/bigwing_shaman_smr21_wind'], 0,
         ['ForesideOfCharacter'], ['SpecifyEffectLifetimeDirectly', 150], ['AB'], 0, 0, 0, False, False,
         ['Some', [{'min': 3, 'max': 3}]]]],
       ['Command',
        ['CreateHitArea', '*', 0, ['AB'], 0, 0, 0, False, False, ['Circle', [{'min': 175, 'max': 175}]], ['Center'],
         ['Center'], ['Single'], ['SpecifyHitAreaLifetimeDirectly', 150], ['CalculatedUsingMaxNumOfHits', 24],
         ['None'], False, True, ['None'], 1, ['Block', []], 2, 3,
         ['Block',
          [['Command', ['ShakeCamera', 1]],
           ['Command',
            ['CreateNormalAttack', 3, 255, [], [], 4, [{'min': 0.6666666666666666, 'max': 0.6666666666666666}],
             [{'min': 0, 'max': 0}], False, False, False, False, False,
             [{'min': 0.5416666666666666, 'max': 0.5416666666666666}], [{'min': 0.625, 'max': 0.625}], ['Fine'],
             True]],
           ['Command',
            ['CreateCondition', 3,
             [['ACToleranceOfElement', [{'min': 1200, 'max': 1200}], 4, [{'min': -0.15, 'max': -0.15}],
               [{'min': 1, 'max': 1}]]],
             [{'min': 1, 'max': 1}], ['GenericConditionHitEffect'], True, False, '', None, False, 3,
             [{'min': 1, 'max': 1}], False]]]],
         0, 0, ['None']]]]]]],
   ['Command',
    ['FindAllSubjects', 4, 33, [], [], [], [], [], ['DoNothing'],
     ['Block',
      [['Command',
        ['CreateCondition', 4,
         [['ACPowerFlipDamage', [{'min': 1200, 'max': 1200}], [{'min': 0.75, 'max': 0.75}],
           [{'min': 1, 'max': 1}]]],
         [{'min': 1, 'max': 1}], ['GenericConditionHitEffect'], True, False, '', None, False, 3,
         [{'min': 1, 'max': 1}], False]]]]]]]]]
WHIRLWIND_DEFLATE_SHA256 = "9bd03232d33ddb3728b456e716f3341642dc59e367658d2f9add25dd1e75d1c8"   # = 灰方审计 output_sha256；encode_tree 逐字节复现
WHIRLWIND_CAS_ROWS = [["额外发动「旋风」"]]

#: 立绘定位三表（灰链 1.4.91→1.4.92 第 2 包）：三人各自的行；只有希耶提与我方不同。
PRESENTATION_ROWS = {
    (CIMG, "149995"): {"0": [["283", "270", "1659", "1535"]], "1": [["183", "214", "1632", "1681"]]},
    (FSA, "149995"): {"0": [["1000", "1000", "1", "1003", "545"]], "1": [["1000", "1000", "1", "1003", "874"]]},
    (TRIM, "character/seofon_wind/ui/full_shot_1440_1920_0"): [["283", "270", "2000", "2000"]],
    (TRIM, "character/seofon_wind/ui/skill_cutin_0"): [["0", "0", "1024", "512"]],
    (TRIM, "character/seofon_wind/ui/full_shot_1440_1920_1"): [["183", "214", "2000", "2000"]],
    (TRIM, "character/seofon_wind/ui/skill_cutin_1"): [["0", "0", "1024", "512"]],
    (CIMG, "149996"): {"0": [["182", "150", "1562", "1841"]], "1": [["154", "49", "1775", "1821"]]},
    (FSA, "149996"): {"0": [["1000", "1000", "1", "1005", "480"]], "1": [["1000", "1000", "1", "1062", "519"]]},
    (TRIM, "character/wind_spgirl_swim/ui/full_shot_1440_1920_0"): [["182", "150", "2000", "2000"]],
    (TRIM, "character/wind_spgirl_swim/ui/skill_cutin_0"): [["141", "28", "1024", "512"]],
    (TRIM, "character/wind_spgirl_swim/ui/full_shot_1440_1920_1"): [["154", "49", "2000", "2000"]],
    (TRIM, "character/wind_spgirl_swim/ui/skill_cutin_1"): [["0", "0", "1024", "512"]],
    (CIMG, "149997"): {"0": [["176", "309", "1584", "1631"]], "1": [["161", "2", "1720", "1771"]]},
    (FSA, "149997"): {"0": [["1000", "1000", "1", "1099", "818"]], "1": [["1000", "1000", "1", "1164", "555"]]},
    (TRIM, "character/mosiyike/ui/full_shot_1440_1920_0"): [["176", "309", "2000", "2000"]],
    (TRIM, "character/mosiyike/ui/skill_cutin_0"): [["38", "10", "1024", "512"]],
    (TRIM, "character/mosiyike/ui/full_shot_1440_1920_1"): [["161", "2", "2000", "2000"]],
    (TRIM, "character/mosiyike/ui/skill_cutin_1"): [["0", "0", "1024", "512"]],
}

SUPPLEMENT_PROVENANCE = {
    "whirlwind_program": {
        "archive": "work/codex_out/gray-audit-20260830/gray/assets/asset-patch/active/pinball-1.4.87-1.4.88-1-0825-integrated-ginovi-spgirl-trio-rogue.zip",
        "archive_sha256": "0ee61e86757833ff65d8ed6c34da1284fbe84b70c587a9c37da55a64a7ab96ce",
        "member": "production/upload/3f/80f8d343d7b77bc6eeaef4490606633e320ef6",
        "sha256": "9bd03232d33ddb3728b456e716f3341642dc59e367658d2f9add25dd1e75d1c8",
        "audit": ("gray/assets/asset-patch/audit/integrated-cloudbase-1.4.87-to-1.4.88-seed-2026082508/patch-audit.json historical_character_terminal.149996 output_sha256 同值；源 = 官方 bigwing_shaman_smr21_2（source_sha256 5dadf280…）"),
    },
    "whirlwind_cas": {
        "archive": "work/codex_out/gray-audit-20260830/gray/assets/asset-patch/active/pinball-1.4.91-1.4.92-2-0829-home-load-rank-p5b.zip",
        "archive_sha256": "33868142fc355c932f6c5f41c74a73125b32657c041a89144a03461c9ecf45fc",
        "member": "production/upload/07/0c6e214359ccf27b1cb8078d3fc51aecfe0149",
        "table_sha256": "bd055b0a4a3a07887a930753ff412af5a024822efefb8316a164c8538f2348d0",
    },
    "presentation_rows": {
        "archive": "work/codex_out/gray-audit-20260830/gray/assets/asset-patch/active/pinball-1.4.91-1.4.92-2-0829-home-load-rank-p5b.zip",
        "archive_sha256": "33868142fc355c932f6c5f41c74a73125b32657c041a89144a03461c9ecf45fc",
        "members": {
            "master/generated/character_image.orderedmap": ["production/upload/3e/b411841802398d5b21d422579f2eaa65d30c0e",
                "ba81d73a2559c2478232c39b489e3ecd337bb63de7afab7199ff4d5c92c7b795"],
            "master/generated/trimmed_image.orderedmap": ["production/upload/fb/ab4344a7456dca88f3ce06f01208922f37e395",
                "56ebc489aef5472c02f883fed187cc55dded572d617907064bbf0ad0f0975952"],
            "master/character/full_shot_image_attribute.orderedmap": ["production/upload/b9/132d27178d27f9d91df89fc47e106bbaf2d5b5",
                "b2342273b33cc662e7b10cbf6053dcb353616c05b1f8584c411076a43bca70f0"],
        },
        "why": "希耶提灰版立绘 PNG 尺寸与我方不同；这批行的 pngW/pngH 与压缩包 PNG 实际尺寸逐一相等",
    },
}

#: 审过的导入结果签名（键集合；files 按 tier 计数）。灰方来源或 live 变了导致结果不同即拒绝。
#: REVIEWED_CHANGES = 非美术部分（表/DSL/文案/特效依赖）；REVIEWED_ART = 美术部分（is_art 的文件 + 立绘定位三表）。
REVIEWED_CHANGES = {
    "149997": {"ability": ["1499972", "1499973", "1499975"]},
    "149995": {
        "text": ["149995"], "action": ["seofon_wind"], "server_text": ["149995"],
        "dsl": ["battle/action/skill/action/rare5/seofon_wind$seofon_wind_1",
                "battle/action/skill/action/rare5/seofon_wind$seofon_wind_2"],
    },
    "149996": {
        "ability": ["1499961", "1499962", "1499963", "1499964", "1499966"], "leader": ["149996"],
        "text": ["149996"], "action": ["wind_spgirl_swim"], "server_text": ["149996"],
        "cas": [WHIRLWIND_KEY],
        "dsl": [WHIRLWIND_PROGRAM,
                "battle/action/skill/action/rare5/wind_spgirl_swim$wind_spgirl_swim_1",
                "battle/action/skill/action/rare5/wind_spgirl_swim$wind_spgirl_swim_2",
                "battle/action/skill/action/rare5/wind_spgirl_swim$wind_spgirl_swim_3"],
        "new_programs": [WHIRLWIND_PROGRAM],
        "files": {"common": 4},                  # 新特效族 battle/effect/skill_unique/wind_spgirl_swim（DSL 依赖）
    },
}
REVIEWED_ART = {
    "149997": {},
    "149995": {
        "presentation_table": [f"{FSA}|149995", f"{CIMG}|149995",
                               f"{TRIM}|character/seofon_wind/ui/full_shot_1440_1920_0",
                               f"{TRIM}|character/seofon_wind/ui/full_shot_1440_1920_1",
                               f"{TRIM}|character/seofon_wind/ui/skill_cutin_0"],
        "files": {"android": 2, "medium": 25},
    },
    "149996": {"files": {"android": 2, "common": 4, "medium": 25}},   # common 4 = 像素小人 sprite/special 的 PNG+图集
}

ART_PENDING, ART_ACCEPTED = "pending", "accepted"
#: 美术是否随 UNITS 导入。希耶提：作者 2026-09-27 看过对比图后拍板接受灰版美术（AskUserQuestion 答复，主会话逐字转述）：
#:   问题「希耶提的灰版美术要不要换进来？灰版觉醒立绘人物偏小偏下，脸在官方脸部区间之外，跟你在 1.4.447 实机否掉的构图
#:   一样；cut-in 上边和左边不透明。技能倍率和文案已经换成灰版了。」
#:   作者选「换成灰版美术」（27 个美术文件和 5 条定位行按灰版导入，包测试里 4 条构图检查按作者决定放宽）。
#: 核心导入已发布（1.4.1054），UNITS 里的希耶提按 BEFORE fail closed；美术由 wf_balance_20260927c_seofonart（包装
#: ART_UNITS）在第三轮 extra5 批次暂存；ART_REVIEW["149995"]["package_tests_red_if_accepted"] 那 4 条包测试已同单元
#: 改为按灰版 27 个文件的 sha256 豁免（work/character_packs/seofon_wind/gray_art_20260927.py）。
ART_DECISION = {"149997": ART_ACCEPTED, "149995": ART_ACCEPTED, "149996": ART_ACCEPTED}

#: 美术审查结论（数值由本机测试从压缩包 + live 复算；对比图 REVIEW_DIR）。
ART_REVIEW = {
    "149995": {
        "decision": "作者 2026-09-27 拍板接受灰版美术（「换成灰版美术」：27 个美术文件和 5 条定位行按灰版导入，"
                    "包测试里 4 条构图检查按作者决定放宽）；下列 findings 是作者知情接受的风险，不是阻断项。"
                    "暂存走 wf_balance_20260927c_seofonart（ART_UNITS）",
        "compare_images": [f"{REVIEW_DIR}/seofon_full_shot_compare.png", f"{REVIEW_DIR}/skill_cutin_edges_compare.png"],
        "official_face_y_p10_p90": [418, 646],
        "face_anchor": {"ours": {"0": [973, 505], "1": [1000, 505]}, "gray": {"0": [1003, 545], "1": [1003, 874]}},
        #: skill_cutin 最外一行/列 alpha 最大值 [上, 左, 右]（按包测试的采样步长）与覆盖率；官方 60 张三边中位数 0、覆盖率最大 0.772。
        "cutin_edges": {"ours": {"0": [0, 0, 0, 0.232], "1": [0, 0, 0, 0.303]},
                        "gray": {"0": [29, 0, 0, 0.464], "1": [75, 255, 0, 0.725]}},
        "findings": [
            "觉醒槽脸锚 (1003,874) 出官方 p10-p90 带 418-646，两槽脸锚不同高（545/874，我方 505/505）；2000 画布上觉醒人物"
            "缩在场景画框偏下处，普通槽人物也比我方小——就是作者 1.4.447 实机否决的构图（「立绘偏下、偏小」「觉醒的…也偏下」，"
            "当时 face_y 729/933）",
            "skill_cutin：灰版 _0 上边 alpha 29、_1 上边 75/左边 255（背景铺到左缘），我方两张三边均 0",
            "插画图集：灰版 PNG 361×789，图集（灰我同字节）按 363×781 打包——见 RISKS",
        ],
        "package_tests_red_if_accepted": [
            "work/character_packs/seofon_wind/test_runtime_regressions.py::test_skill_cutin_respects_the_official_transparent_edges"
            "（variant 0 上边 29；variant 1 上边 75、左边 255）",
            "work/character_packs/seofon_wind/test_runtime_regressions.py::"
            "test_trimmed_image_declares_the_2000_canvas_and_matches_character_image（槽 1 face_y 874 出 418-646；两槽 545≠874）",
            "work/character_packs/seofon_wind/test_build_workspace.py::test_full_shots_land_on_the_official_face_and_foot_anchors"
            "（包内两张立绘 ≠ seofon_art 产物；脚底线）",
            "work/character_packs/seofon_wind/test_build_workspace.py::"
            "test_generated_avatar_slots_are_face_centered_and_keep_donor_alpha（20 张头像/图标包内 ≠ seofon_art 产物）",
        ],
        "package_tests_evidence": (
            "在包工作区副本（去 build/）里写入灰版 27 个美术文件 + 定位行后跑两份包测试：上述 4 条（27 个子用例）新红；"
            "只写表/DSL/文案（本模块默认输出）时与未改副本结果相同（runtime 5/5 过）。manifest 封条测试的红是副本未重算 "
            "manifest 所致（真实回写由 RevisionCandidate.finish 重算），不计；6 条子进程 spec 测试在副本里因 ROOT 不同无法运行，"
            "它们只读生成器规格、不读包内美术"),
        "on_accept": [
            "作者在当次请求里明确接受灰版美术（含觉醒构图与 cut-in 边缘）",
            "暂存 ART_UNITS（只查美术输入基线，核心导入之后仍可跑；候选版本 1.0.4），或把 ART_DECISION['149995'] 改成 accepted 一次导入",
            "候选回写要走允许呈现改动的路径：RevisionCandidate.finish 的呈现保护会以 protected presentation asset changed 拒绝",
            "同一单元按作者签字改/退役上面 4 条包测试（改钉灰版字节与几何，或把美术来源登记为灰方导入）；"
            "seofon_art.py / build_workspace.py 的美术产出从此不再是真源",
        ],
    },
    "149996": {
        "decision": "随核心导入：灰版沿用我方定位行（尺寸与 PNG 相符），两槽脸锚 (1005,480)/(1062,519) 在官方带内且落在脸上",
        "compare_images": [f"{REVIEW_DIR}/swim_full_shot_compare.png", f"{REVIEW_DIR}/skill_cutin_edges_compare.png"],
        "cutin_edges": {"ours": {"0": [145, 255, 255, 0.442], "1": [30, 37, 38, 0.666]},
                        "gray": {"0": [2, 255, 255, 0.444], "1": [51, 38, 24, 0.63]}},
        "findings": ["cut-in 左右边不透明，但我方现行版同样如此（_0 上边我方 145、灰版 2），不是回退；泳装无 flow 包，无包测试"],
    },
}


class Gray3Error(ValueError):
    """灰方来源或 live 输入与审查时不符：拒绝导入（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _same(a: Any, b: Any) -> bool:
    """元组/列表不分、字典键序不分的值相等（与 digest 口径一致）。"""
    return digest(a) == digest(b)


def owns(key: str, cid: str, code: str) -> bool:
    return key.startswith(cid) or key == code or key.startswith(code + "_")


def owns_file(logical: str, code: str) -> bool:
    return (logical.startswith(f"character/{code}/")
            or logical.startswith(f"battle/effect/skill_unique/{code}/"))


def is_art(member: str, code: str) -> bool:
    """美术文件：medium/android 层，或 common 层 ``character/<code>/``（像素小人、UI 图集、详情预览）。
    ``battle/effect`` 特效是技能 DSL 的依赖，不算美术。"""
    tier, logical = member.split(":", 1)
    return tier in ("medium", "android") or logical.startswith(f"character/{code}/")


def is_art_input(cid: str, kind: str, key: Any) -> bool:
    """BEFORE 里属于美术的输入（ART_UNITS 只锁这些）。"""
    if kind == "file_sha256":
        return is_art(f"{key[0]}:{key[1]}", SPECS[cid]["code"])
    return kind in ("table", "nested_table") and key[0] in PRESENTATION_TABLES


def encode_row_text(rows: list[list[str]]) -> bytes:
    """与 live / 候选 flat codec 相同：zlib(CSV 文本，去尾换行)。live 立绘定位行没有尾换行，
    X.csv_write 会带 ``\\n``（希耶提包测试按 ``split(",")`` 读，会读出 ``"2000\\n"``）。"""
    return zlib.compress(core.write_csv_lines(rows).rstrip("\n").encode("utf-8"))


def encode_presentation(logical: str, value: Any) -> bytes:
    """立绘定位行的外层字节：嵌套表 = X.pack({inner: encode_row_text(rows)})，平表 = encode_row_text(rows)。"""
    if logical in NESTED_TABLES:
        return X.pack({inner: encode_row_text(rows) for inner, rows in value.items()})
    return encode_row_text(value)


def decode_value(logical: str, raw: bytes) -> Any:
    if logical == ACT:
        return [[inner, list(fields)] for inner, fields in core.decode_action_skill_row(raw)]
    if logical in NESTED_TABLES:
        return {inner: X.csv_read(value) for inner, value in X.unpack(raw).items()}
    return X.csv_read(raw)


def before_key(logical: str, key: str) -> tuple:
    kind = _STD_KIND.get(logical)
    if kind:
        return kind, key
    return ("nested_table" if logical in NESTED_TABLES else "table"), (logical, key)


def member_name(tier: str, logical: str) -> str:
    """压缩包内成员名（也是 GRAY_ROOT 下的相对路径，去掉开头的 ``production/``）。"""
    hashed = core.sha1_path(logical)
    return f"production/{TIER_DIRS[tier]}/{hashed[:2]}/{hashed[2:]}"


def open_archive(archive: Path | str | None = None) -> zipfile.ZipFile:
    """按 ARCHIVE_SHA256 核对整包后打开（内存）；不符即拒绝。"""
    path = Path(ARCHIVE if archive is None else archive)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise Gray3Error(f"gray archive not found: {path}") from exc
    if hashlib.sha256(data).hexdigest() != ARCHIVE_SHA256:
        raise Gray3Error(f"gray archive sha256 mismatch: {path}")
    return zipfile.ZipFile(io.BytesIO(data))


def extract(root: Path | str | None = None, archive: Path | str | None = None) -> int:
    """把钉哈希的压缩包解到 ``root``（默认 GRAY_ROOT）；逐成员核 GRAY_FILES，已相同的跳过。返回写入个数。
    只写 ``root`` 下的文件（默认仓库 work/gray3/production，已 gitignore）；不碰 live/assets/.cdn/候选。"""
    root = GRAY_ROOT if root is None else Path(root)
    expected = {member_name(*member.split(":", 1)): member for member in GRAY_FILES}
    written = 0
    with open_archive(archive) as zf:
        names = {name for name in zf.namelist() if not name.endswith("/")}
        if names != set(expected):
            raise Gray3Error("archive member list differs from GRAY_FILES")
        for name, member in sorted(expected.items()):
            data = zf.read(name)
            if hashlib.sha256(data).hexdigest() != GRAY_FILES[member]:
                raise Gray3Error(f"archive member changed: {member}")
            path = root / name.split("/", 1)[1]
            if path.is_file() and path.read_bytes() == data:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            written += 1
    return written


class ArchiveSource:
    """灰方压缩包成员：``root``（默认 GRAY_ROOT）下有就读它，没有就从钉哈希的 ``archive``（默认 ARCHIVE）直接读；
    每次取字节都按 GRAY_FILES 核 sha256（缺失/被改即拒绝）。``file_path`` 只认 ``root`` 下已解出的文件。"""

    def __init__(self, root: Path | str | None = None, archive: Path | str | None = None):
        self.root = GRAY_ROOT if root is None else Path(root)
        self.archive = ARCHIVE if archive is None else Path(archive)
        self._zip: zipfile.ZipFile | None = None
        self._tables: dict[str, dict[str, bytes]] = {}

    def path(self, tier: str, logical: str) -> Path:
        return self.root / member_name(tier, logical).split("/", 1)[1]

    def raw(self, tier: str, logical: str) -> bytes:
        member = f"{tier}:{logical}"
        want = GRAY_FILES.get(member)
        if want is None:
            raise Gray3Error(f"not an archive member: {member}")
        path = self.path(tier, logical)
        if path.is_file():
            data = path.read_bytes()
        elif self.archive.is_file():
            if self._zip is None:
                self._zip = open_archive(self.archive)
            data = self._zip.read(member_name(tier, logical))
        else:
            raise Gray3Error(f"archive member missing: {member} (neither {path} nor {self.archive}); "
                             "restore the zip and run `python mod-tools/wf_balance_20260927b_gray3.py extract`")
        if hashlib.sha256(data).hexdigest() != want:
            raise Gray3Error(f"archive member changed: {member}")
        return data

    def _table(self, logical: str) -> dict[str, bytes]:
        if logical not in self._tables:
            self._tables[logical] = X.unpack(self.raw("common", logical))
        return self._tables[logical]

    def owned_keys(self, logical: str, cid: str, code: str) -> list[str]:
        return [key for key in self._table(logical) if owns(key, cid, code)]

    def value(self, logical: str, key: str) -> Any:
        return decode_value(logical, self._table(logical)[key])

    def dsl(self, program: str) -> list:
        data = zlib.decompress(self.raw("common", wf_dsl.dsl_logical(program)), -15)
        if hashlib.sha256(data).hexdigest() != GRAY_DSL_AMF3_SHA256[program]:
            raise Gray3Error(f"gray DSL payload drift: {program}")
        return wf_dsl.parse_dsl(data)["tree"]

    def file_path(self, tier: str, logical: str) -> str:
        path = self.path(tier, logical)
        if not path.is_file():
            raise Gray3Error(f"extracted member missing: {tier}:{logical} ({path}); "
                             "run `python mod-tools/wf_balance_20260927b_gray3.py extract` first")
        self.raw(tier, logical)                          # 落地字节同样核 sha256
        return str(path)


def _read(read: Callable[[str, Any], Any], kind: str, key: Any) -> Any:
    try:
        return read(kind, key)
    except (KeyError, FileNotFoundError) as exc:
        if kind in ("cas", "dsl"):
            return None                                 # live 里没有（新增文案键 / 新程序）
        raise Gray3Error(f"live input unreadable: {kind}:{key} ({exc!r}); nested_table / file_sha256 "
                         "need the stage reader extension (notes.stage_integration)") from exc


def _baseline(cid: str, read: Callable[[str, Any], Any], before: dict | None = None) -> dict:
    values = {}
    for (kind, key), want in (BEFORE_BY_CID[cid] if before is None else before).items():
        value = _read(read, kind, key)
        if digest(value) != want:
            raise Gray3Error(f"unreviewed live baseline: {kind}:{key}")
        values[kind, key] = deepcopy(value)
    return values


def _empty() -> dict:
    return {"ability": {}, "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {}, "dsl": {},
            "server_text": {}, "server_character": {}, "nested_table": {}, "presentation_table": {},
            "files": {}, "new_programs": []}


def _put(out: dict, logical: str, key: str, value: Any) -> None:
    value = deepcopy(value)
    kind = _STD_KIND.get(logical)
    if kind == "action":
        out["action"][key] = [(inner, list(fields)) for inner, fields in value]
    elif kind:
        out[kind][key] = value
    elif logical in NESTED_TABLES:
        out["nested_table"][logical, key] = value
    else:
        out["table"][logical, key] = value


def signature(out: dict) -> dict:
    sig = {}
    for kind in ("ability", "leader", "cas", "text", "action", "dsl", "server_text", "table",
                 "nested_table", "presentation_table", "server_character"):
        keys = sorted("|".join(k) if isinstance(k, tuple) else k for k in out.get(kind, {}))
        if keys:
            sig[kind] = keys
    if out.get("new_programs"):
        sig["new_programs"] = sorted(out["new_programs"])
    files = Counter(key.split(":", 1)[0] for key in out.get("files", {}))
    if files:
        sig["files"] = dict(sorted(files.items()))
    return sig


def merge_signatures(a: dict, b: dict) -> dict:
    """两份签名合并（键列表取并集，files 按 tier 计数相加）。"""
    merged = {}
    for kind in sorted(set(a) | set(b)):
        if kind == "files":
            counts = Counter(a.get(kind, {})) + Counter(b.get(kind, {}))
            merged[kind] = dict(sorted(counts.items()))
        else:
            merged[kind] = sorted(set(a.get(kind, [])) | set(b.get(kind, [])))
    return merged


def row_problems(kind: str, row: list[str], cas_keys: set[str]) -> list[str]:
    problems = [f"legality: {p}" for p in L.client_legality_problems(kind, row)]
    problems += [f"declared: {p}" for p in L.declared_block_field_problems(kind, row)]
    problems += [f"element: {p}" for p in L.ability_element_column_problems(kind, row, ELEMENT)]
    problems += [f"invoke: {p}" for p in L.invoke_skill_string_problems(row, cas_keys, kind=kind)]
    caps = L.required_client_capabilities(kind, row)
    if caps:
        problems.append(f"capabilities {caps} not declared")
    return problems


def dsl_problems(tree) -> list[str]:
    problems = []
    back = wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"]
    if json.dumps(back) != json.dumps(tree):          # 连 int/float 一起比
        problems.append("AMF3 roundtrip mismatch")
    problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"scope: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    return problems


def _gates(out: dict, read: Callable[[str, Any], Any]) -> list[str]:
    problems = []
    rows = [("ability", key, row) for key, rows_ in out["ability"].items() for row in rows_]
    rows += [("leader_ability", key, row) for key, rows_ in out["leader"].items() for row in rows_]
    sids = set()
    for kind, _key, row in rows:
        col = int(wf_describe.layout(kind)["blocks"]["instant_content"])
        if row[col] == "629":
            sids.add(row[col + L.INVOKE_SKILL_STRING_OFFSET])
    cas_keys = set(out["cas"]) | {sid for sid in sids if _read(read, "cas", sid) is not None}
    for kind, key, row in rows:
        problems += [f"{kind}:{key}: {p}" for p in row_problems(kind, row, cas_keys)]
    for program, tree in out["dsl"].items():
        problems += [f"dsl {program}: {p}" for p in dsl_problems(tree)]
    return problems


def _presentation_changes(cid: str, live: dict) -> dict:
    code = SPECS[cid]["code"]
    changes = {}
    for (logical, key), value in PRESENTATION_ROWS.items():
        if key == cid or key.startswith(f"character/{code}/"):
            if not _same(value, live[before_key(logical, key)]):
                changes[logical, key] = deepcopy(value)
    return changes


def _changed_members(cid: str, live: dict, *, art: bool | None) -> list[str]:
    """压缩包里属于本角色、与 live 字节不同（或 live 缺）的文件成员；art=True/False 只取美术/非美术，None 全取。"""
    code = SPECS[cid]["code"]
    members = []
    for member, sha in sorted(GRAY_FILES.items()):
        tier, logical = member.split(":", 1)
        if (tier not in IMPORT_TIERS or logical.startswith("master/") or logical.endswith(DSL_SUFFIX)
                or not owns_file(logical, code)):
            continue
        if art is not None and is_art(member, code) != art:
            continue
        if live["file_sha256", (tier, logical)] != sha:
            members.append(member)
    return members


def revise_unit(cid: str, read: Callable[[str, Any], Any], gray: Any = None, art: str | None = None) -> dict:
    """一名角色：live（BEFORE 锁定）→ 灰版的键级替换。``gray`` 默认 ArchiveSource()。
    ``art`` 默认 ART_DECISION[cid]：pending = 美术（files 中 is_art 的成员 + 立绘定位三表）只列进 notes.art。"""
    spec = SPECS[cid]
    code = spec["code"]
    decision = ART_DECISION[cid] if art is None else art
    if decision not in (ART_PENDING, ART_ACCEPTED):
        raise Gray3Error(f"unknown art decision: {decision!r}")
    gray = gray if gray is not None else ArchiveSource()
    live = _baseline(cid, read)
    out = _empty()

    same = []
    for logical in GRAY_TABLES:
        want = EXPECTED_KEYS[cid].get(logical, [])
        got = gray.owned_keys(logical, cid, code)
        if sorted(got) != sorted(want):
            raise Gray3Error(f"gray key set drift: {logical}: {got} != {want}")
        for key in want:
            value = gray.value(logical, key)
            if _same(value, live[before_key(logical, key)]):
                same.append(f"{logical}|{key}")
            else:
                _put(out, logical, key, value)

    for kind, key in BEFORE_BY_CID[cid]:
        if kind == "dsl" and key != WHIRLWIND_PROGRAM:
            tree = gray.dsl(key)
            if _same(tree, live[kind, key]):
                same.append(f"dsl|{key}")
            else:
                out["dsl"][key] = tree

    text = gray.value(TXT, cid)
    if not _same(text, live["server_text", cid]):
        out["server_text"][cid] = deepcopy(text)

    if cid == "149996":
        if live["cas", WHIRLWIND_KEY] is None:
            out["cas"][WHIRLWIND_KEY] = deepcopy(WHIRLWIND_CAS_ROWS)
        if live["dsl", WHIRLWIND_PROGRAM] is None:
            out["dsl"][WHIRLWIND_PROGRAM] = deepcopy(WHIRLWIND_TREE)
            out["new_programs"].append(WHIRLWIND_PROGRAM)

    for member in _changed_members(cid, live, art=False):
        out["files"][member] = gray.file_path(*member.split(":", 1))
    art_members = _changed_members(cid, live, art=True)
    art_rows = _presentation_changes(cid, live)
    art_sig = signature({"files": dict.fromkeys(art_members), "presentation_table": art_rows})
    if art_sig != REVIEWED_ART[cid]:
        raise Gray3Error(f"art change set drifted from the reviewed one: {art_sig}")
    if decision == ART_ACCEPTED:
        for member in art_members:
            out["files"][member] = gray.file_path(*member.split(":", 1))
        out["presentation_table"].update(art_rows)

    problems = _gates(out, read)
    if problems:
        raise Gray3Error("; ".join(problems))
    expected = (REVIEWED_CHANGES[cid] if decision == ART_PENDING
                else merge_signatures(REVIEWED_CHANGES[cid], REVIEWED_ART[cid]))
    if signature(out) != expected:
        raise Gray3Error(f"import result drifted from the reviewed change set: {signature(out)}")
    out["notes"] = _notes(cid, out, same)
    out["notes"]["art"] = _art_notes(cid, decision, art_members, art_rows)
    return out


def revise_art(cid: str, read: Callable[[str, Any], Any], gray: Any = None) -> dict:
    """只导入美术（作者接受后用，见 ART_UNITS）：只锁美术输入（ART_BEFORE_BY_CID），所以核心导入之后仍可跑。"""
    gray = gray if gray is not None else ArchiveSource()
    live = _baseline(cid, read, ART_BEFORE_BY_CID[cid])
    out = _empty()
    art_members = _changed_members(cid, live, art=True)
    for member in art_members:
        out["files"][member] = gray.file_path(*member.split(":", 1))
    out["presentation_table"] = _presentation_changes(cid, live)
    if signature(out) != REVIEWED_ART[cid]:
        raise Gray3Error(f"art change set drifted from the reviewed one: {signature(out)}")
    spec = SPECS[cid]
    out["notes"] = {
        "source": "mod-tools/wf_balance_20260927b_gray3.py (ART_UNITS)",
        "character": f"{cid} {spec['code']} {spec['name']}",
        "requires": "作者在当次请求里明确接受灰版美术后才暂存；同一单元按作者签字改/退役 package_tests_red_if_accepted",
        "art": _art_notes(cid, ART_ACCEPTED, art_members, out["presentation_table"]),
        "risks": RISKS[cid],
        "stage_integration": STAGE_INTEGRATION,
        "runtime_verified": False,
    }
    return out


def _art_notes(cid: str, decision: str, members: list[str], rows: dict) -> dict:
    notes = {"decision": decision,
             "files": sorted(members),
             "presentation_table": sorted(f"{logical}|{key}" for logical, key in rows)}
    notes["status"] = ("imported" if decision == ART_ACCEPTED
                       else "deferred：未导入，等作者看对比图拍板（接受后暂存 ART_UNITS）")
    if cid in ART_REVIEW:
        notes["review"] = ART_REVIEW[cid]
    return notes


def _notes(cid: str, out: dict, same: list[str]) -> dict:
    spec = SPECS[cid]
    notes = {
        "source": "mod-tools/wf_balance_20260927b_gray3.py",
        "character": f"{cid} {spec['code']} {spec['name']}",
        "author_request": "对方灰服调整过的角色，把这版替换我本地的，然后一并纳入调整（作者 2026-09-27 聊天）",
        "archive": {"path": str(ARCHIVE), "sha256": ARCHIVE_SHA256, "gray_edge": list(ARCHIVE_EDGE),
                    "extracted_root": str(GRAY_ROOT), "members": len(GRAY_FILES)},
        "method": "键级替换：只取本角色外层键，灰值≠live 才返回；其他角色的行一律不带入（整表对比见测试夹具 other_character_diff）",
        "gray_changes": UNIT_CHANGES[cid],
        "same_as_live": same,
        "files": {"count": len(out["files"]), "tiers": dict(Counter(k.split(":", 1)[0] for k in out["files"])),
                  "ios": "压缩包 ios_upload 层 6 个 skill_cutin ATF 忽略（我方无 ios 根）"},
        "server": {"server_text": sorted(out["server_text"]),
                   "server_character": "灰版 character 行与我方相同（assets/cdndata/character.json 已核对），无需同步"},
        "overwrites_batch2": OVERWRITES_BATCH2[cid],
        "not_in_archive": NOT_IN_ARCHIVE[cid],
        "risks": RISKS[cid],
        "generators": GENERATORS[cid],
        "stage_integration": STAGE_INTEGRATION,
        "runtime_verified": False,
    }
    if cid == "149996":
        notes["supplement"] = {"whirlwind_program": SUPPLEMENT_PROVENANCE["whirlwind_program"],
                               "whirlwind_cas": SUPPLEMENT_PROVENANCE["whirlwind_cas"]}
    if cid == "149995":
        notes["supplement"] = {"presentation_rows（只随美术）": SUPPLEMENT_PROVENANCE["presentation_rows"]}
    return notes


UNIT_CHANGES = {
    "149997": {
        "ability:1499972#4": "持续·状态攻击力↑ → 触发者独立乘区强化弹射伤害 +50% → +15%（c113/c114 50000→15000）",
        "ability:1499973#0": "主位：技能发动 → 自身技能槽 +20% 加 CT 30 秒（c35 0→1800 帧）",
        "ability:1499975": "删行#2「技能发动 → 全队技能槽 +20%」，原 #3「技能发动 → 全队连击加成 8×1 次」前移（4 行→3 行）",
    },
    "149995": {
        "dsl:seofon_wind_1": "灵剑每刃倍率按剑神层数 1-2/3-5/6-8/9-11/12 级：25/35/50/70/90 → 25/30/40/50/70",
        "dsl:seofon_wind_2": "进化后：30/40/55/75/90 → 30/35/45/55/80（只改 CreateNormalAttack 倍率，结构不变）",
        "text": "技能文案三处（action_skill×2、character_text c5/c7/c9、服务端 character_text）改为按级列倍率的新文案",
        "art（作者 09-27 接受；核心导入时未带，extra5 seofonart 暂存）": ("立绘/图标/cut-in 等 25 张 medium PNG + 2 个 android cut-in ATF 换成灰版美术"
                                "（灰链 1.4.89→1.4.90 同批）"),
        "presentation_table（随美术）": "character_image/trimmed_image/full_shot_image_attribute 跟新立绘尺寸（灰链 1.4.92）",
    },
    "149996": {
        "ability:1499961#1": "每 77 连击自身技能槽 +2.5%（限 77）→ +5%（限 101）",
        "ability:1499962#0-2": "每 77 连击全队攻击/直击/技能伤害 +12.5%：对象由全队改为全队(风)（c49 (None)→Green）",
        "ability:1499963": ("主位：瞬发「每 77 连击独立乘区技能/直击 +2.5%（限 5）」→ 持续「每 77 连击一层、最多 10 层，"
                            "每层独立乘区技能/直击 +20%」（during 411/410），新增行「连击≥777 → 连击数置 0」（kind 390）"),
        "ability:1499964": "第二批 B4 的「每 77 连击自身直击 +20%（限 5）」→ 灰版「每 77 连击自身眩晕蓄积 +25%（限 101）」",
        "ability:1499966": ("主位：全队技能槽 +2.5%（限 77）→ 全队(风) +5%（限 101）；删「技能发动 → 追加连击 77」；"
                            "新增「技能发动（CT 1 秒）→ 发动「旋风」」（629，西微风怒龙卷＋满强化本体：24 段×0.667=16 倍、"
                            "敌风耐性 -15% 20 秒、全队强化弹射伤害 +75% 20 秒）"),
        "leader:149996": ("#2/#3「风编成≥6：每 77 连击全队攻击/直击 +12.5%（限 101）」→ #2「风编成≥6：每 777 连击全队(风)"
                          "技能槽 +150%」、#3「风编成≥6：全队(风)技能槽上限 +50%」（245），新增 #4「风编成≥6：强化弹射 Lv3 → "
                          "全队(风)技能槽 +77%」"),
        "dsl:wind_spgirl_swim_1..3": ("CreateNormalAttack p14 5→7（灰方工具注释：连击加成 0.5%→0.7%/连击）；Lv3 贯通 630→720 帧；"
                                      "技能特效由官方 wind_spgirl 改为自有 wind_spgirl_swim 特效族（4 个新文件）"),
        "text": "技能文案：「以肉眼无法看清的闪击对前方和后方的敌方造成风属性伤害【根据连击数提升伤害】／赋予自身贯通、最大速度固定。」",
        "art": "25 张 medium PNG + 2 个 cut-in ATF + 像素小人 sprite/special 的 PNG 与图集（灰链 1.4.87→1.4.88）",
    },
}
OVERWRITES_BATCH2 = {
    "149997": "无：第二批 B2 改的是 PF 覆盖树 p13（lv2 5→4、lv3 5→2.5），压缩包不含 PF 树，第二批结果保留",
    "149995": "无：第二批 B3 改的是「剑界回响」629 树 p13（2.0→0.2），压缩包不含该树，第二批结果保留",
    "149996": ("覆盖：ability 1499964（第二批 B4 删眩晕蓄积→直击 +20%×5）回到灰版「眩晕蓄积 +25%（限 101）」，需任务 B 重审。"
               "导入后 live 1499964 的摘要 == wf_balance_20260927b_swimceltie.BEFORE[('ability','1499964')]（0d0e70e8…），"
               "第二批泳装模块因此重新可应用：gray3 之后禁止重跑它（会把 B4 静默叠回灰版行）；A4 的去留只归任务 B"),
}
NOT_IN_ARCHIVE = {
    "149997": ("PF 覆盖树 mosiyike_pf lv1-3 与 power_flip_action 不在压缩包：灰链 1.4.85（mosiyike-balance）把风刃每发倍率 "
               "12.5/8.28/6.44 降到 7.5/6.0/4.5、p13 仍 5；我方 live = 我方发给灰的版本 + 第二批 p13。未导入，"
               "若要连 PF 一起换灰版，需灰方当前（1.4.131）的 PF 三档文件"),
    "149995": ("「剑界回响」629 树、custom_ability_string 不在压缩包：灰链 ≤1.4.93 的回响树 = 我方第二批之前（p13 2.0），"
               "文案键与我方相同；语音与我方相同"),
    "149996": ("19 条语音不在压缩包：灰链 1.4.88 重编码过（字节不同、未导入）。旋风 629 程序与文案不在压缩包但为硬依赖，"
               "已从灰链归档补齐（supplement）"),
}
RISKS = {
    "149997": [],
    "149995": [
        "美术（作者 2026-09-27 知情接受，ART_REVIEW['149995']）：灰版觉醒立绘脸锚 y=874 出官方带 418-646、两槽脸锚不同高（545/874），"
        "即作者 1.4.447 实机否决的「偏下、偏小」构图；cut-in _0 上边 alpha 29、_1 上边 75/左边 255（我方三边均 0）；"
        "接受后希耶提包内 4 条测试（27 个子用例）按作者决定对灰版 27 个文件的 sha256 豁免，其余检查照旧",
        "（仅在接受美术时）灰版 illustration_setting_sprite_sheet.png 为 361×789，图集（灰我同字节）按 363×781 打包："
        "两个矩形宽 362/363 越出右缘 1-2 px，PNG 又比图集高 8 px（y 781-788 不在任何矩形里）。实测灰版这 8 行与 x≥361 "
        "全透明（alpha 0），两幅画内容在 x 1-360、y 31-360 / 425-780，分别落在矩形 0（y 0-409）与矩形 1（y 411-780）内，"
        "没有可见像素被裁；只是画在矩形里的位置与我方不同。灰服自 1.4.90 起如此运行",
        "（仅在接受美术时）立绘定位三表取自灰链 1.4.92 快照（2026-08-30 审计副本）；灰链 1.4.93→1.4.131 若再调过居中，"
        "本地会与灰服略有差",
        "（仅在接受美术时）RevisionCandidate.finish 的呈现保护会拒绝 medium/android/ui 与立绘定位表的改动："
        "候选回写需主会话走允许呈现改动的路径",
    ],
    "149996": [
        "旋风 629：每次 24 段×p13 0.5417 ≈ 13 削韧、CT 1 秒，高于本批「能力调用技能 CT≤3 秒每次 ≤1」口径——留给任务 B",
        "A4 眩晕蓄积 +25%×101（第二批删掉的无上限蓄积）随灰版回来——留给任务 B；gray3 之后不得重跑第二批泳装模块"
        "（见 overwrites_batch2）",
        "旋风程序与文案来自灰链归档（1.4.88/1.4.92），灰链 1.4.93→1.4.131 若改过旋风，本地会与灰服不同",
        "灰版插画图集 PNG（361×798，与我方同尺寸）与图集矩形（灰我同字节）错位：第一幅画占 y 0-428，矩形 0 只到 y 425——"
        "第一幅下缘 3 行被裁，其中 y 427-428（x 172-238，alpha ≤216）落进矩形 1（y 427-797）顶部，觉醒插画顶端会露出 2 行碎边；"
        "第二幅 y 433-793 完整在矩形 1 内。灰服同样如此，非致命",
        "cut-in 左右边不透明（上/左/右 alpha：_0 2/255/255、_1 51/38/24），我方现行版同样如此（_0 145/255/255、_1 30/37/38），非回退",
    ],
}
GENERATORS = {
    "149997": ("work/character_packs/mosiyike/build_kit.py ability_rows() 会按旧设计重建 1499971-76（含 1499972#4 +50%、"
               "1499973#0 无 CT、1499975 四行）——灰版是新真源，不得直接重跑；build_pf.py 只管 PF 树（第二批已同步，本次不涉及）"),
    "149995": ("work/character_packs/seofon_wind：seofon_dsl.py 第 81-82 行的每层倍率表（lv1 90/70/50/35/25、lv2 90/75/55/40/30）"
               "会重建我方旧技能树；seofon_tables.py 重建旧技能文案（character_text/action_skill）——灰版是新真源，不得直接重跑。"
               "美术：作者 2026-09-27 接受灰版美术后，seofon_art.py / build_workspace.py 的立绘/图标/cut-in 与定位行不再是真源"
               "（不得重跑覆盖灰版美术）；同一单元已按灰版 27 个文件的 sha256 豁免包测试 test_runtime_regressions.py"
               "::test_skill_cutin_respects_the_official_transparent_edges、"
               "::test_trimmed_image_declares_the_2000_canvas_and_matches_character_image，test_build_workspace.py"
               "::test_full_shots_land_on_the_official_face_and_foot_anchors、"
               "::test_generated_avatar_slots_are_face_centered_and_keep_donor_alpha（副本实测 27 个子用例变红）。"
               "seofon_kit.py 的能力/队长行与灰版相同（本次无差异），seofon_dsl.build_ability_skill_tree() 只管回响树"
               "（第二批 p13 待同步，见第二批 notes）"),
    "149996": ("无 flow 包。work/character_packs/xierti_swim/build_workspace.py、_patch_kit.py 等历史脚本会写回旧行/旧美术——"
               "不得重跑；灰方源工具在 work/codex_out/gray-audit-20260830/gray/tools/fantasy-gauntlet-mod-tools/"
               "wf_spgirl_balance.py（只作证据，不在我方运行）；第二批 wf_balance_20260927b_swimceltie 也不得在 gray3 之后重跑"),
}
STAGE_INTEGRATION = [
    "read 新种类 nested_table：(logical, outer) → {inner: X.csv_read(v) for inner, v in X.unpack(X.unpack(表)[outer]).items()}",
    "read 新种类 file_sha256：(tier, logical) → live 文件 sha256 或 None（common=table_path，medium/android=wf_assets.path_in_root）",
    "files：逐项读字节、按 GRAY_FILES 复核 sha256 后 emit(tier, logical, bytes)；路径在 GRAY_ROOT（默认 work/gray3/production，"
    "缺了先跑 `python mod-tools/wf_balance_20260927b_gray3.py extract`）",
    "默认 UNITS 只有泳装希尔媞带 files（35 个：特效 4 + 像素 4 + medium 25 + android 2），没有 presentation_table",
    "presentation_table（只在暂存 ART_UNITS 或 ART_DECISION 改 accepted 时出现）：平表 trimmed_image 走 splice(logical, {key: rows})；"
    "嵌套表 character_image / full_shot_image_attribute 走 splice(logical, {key: encode_presentation(logical, value)}, "
    "codec='raw_outer')——内层行不带尾换行（旧写法 X.csv_write 会带 \\n，希耶提包测试按 split(',') 读会读出 '2000\\n'）。"
    "平表同理：extra5 暂存脚本的 flat splice 用 X.csv_write（带尾换行），所以 trimmed_image 也先 encode_presentation"
    "（= encode_row_text，无尾换行）再按已有 flat claim 原样写入（extra5 stage_batch.splice_presentation）",
    "BarePlan（149996）的命名空间断言需放行 ability_skill_wind_spgirl_swim_whirlwind（灰方命名；先例 ability_skill_seofon_wind_echo）",
    "Plan（seofon_wind）默认只回写表/DSL/文案，RevisionCandidate.finish 可过；ART_UNITS 回写美术时 finish 会以 protected "
    "presentation asset changed 拒绝，需主会话提供允许呈现改动的回写路径（本模块不改共享库）",
    "三名角色共用 snapshot 键 revision_20260927b：第二批 mosiyike/siete 测试的候选版本断言已放宽为 {第二批, gray3}；"
    "ART_UNITS 把 seofon_wind 升到 1.0.4 时同步放宽 test_balance_20260927b_siete.py 的版本集合",
    "gray3 之后的暂存计划里不得再出现第二批 wf_balance_20260927b_swimceltie（它的 BEFORE 与导入后的 1499964 相同，会重放 B4）",
]

#: ART_UNITS 只锁的美术输入（BEFORE 的子集；核心导入会改的表/DSL/文案键不在其中）。
ART_BEFORE_BY_CID = {cid: {(kind, key): want for (kind, key), want in before.items() if is_art_input(cid, kind, key)}
                     for cid, before in BEFORE_BY_CID.items()}


def _unit(cid: str) -> dict:
    spec = SPECS[cid]
    return dict(CID=cid, CODE=spec["code"], PACKAGES=list(spec["packages"]),
                PACKAGE_VERSION=dict(spec["version"]), CAPABILITIES=[], REVIEWED_DRIFT=spec["drift"],
                BEFORE=BEFORE_BY_CID[cid], ART_DECISION=ART_DECISION[cid],
                revise=lambda read, _cid=cid: revise_unit(_cid, read))


#: 暂存顺序：墨斯伊克（只有表行）→ 希耶提（表/DSL/文案；美术当时待拍板；作者 09-27 接受后经 ART_UNITS / seofonart 另行暂存）→ 泳装希尔媞（无包，含美术与新特效族）。
UNITS = [_unit(cid) for cid in ("149997", "149995", "149996")]

#: 作者接受灰版美术之后才暂存（不在 UNITS 里）：希耶提美术与立绘定位行。作者 2026-09-27 已接受；第三轮 extra5 批次经
#: wf_balance_20260927c_seofonart 暂存（候选 1.0.3 → 1.0.4）。
ART_UNITS = [dict(CID="149995", CODE="seofon_wind", PACKAGES=["seofon_wind"],
                  PACKAGE_VERSION={"seofon_wind": "1.0.4"}, CAPABILITIES=[], REVIEWED_DRIFT={},
                  BEFORE=ART_BEFORE_BY_CID["149995"], REQUIRES_AUTHOR_SIGNOFF=True,
                  revise=lambda read: revise_art("149995", read))]


# ---------------------------------------------------------------- 命令行：解包 / 生成美术对比图

def _png(data: bytes):
    from PIL import Image
    import wf_assets
    return Image.open(io.BytesIO(wf_assets.png_decode(data))).convert("RGBA")


def cutin_edges(image) -> list:
    """[上, 左, 右] 最外一行/列 alpha 最大值（与希耶提包测试同采样步长）+ 覆盖率（alpha>8，步长 4）。"""
    width, height = image.size
    alpha = image.getchannel("A").load()
    top = max(alpha[x, 0] for x in range(0, width, 8))
    left = max(alpha[0, y] for y in range(0, height, 4))
    right = max(alpha[width - 1, y] for y in range(0, height, 4))
    covered = sum(1 for y in range(0, height, 4) for x in range(0, width, 4) if alpha[x, y] > 8)
    return [top, left, right, round(covered / ((height // 4) * (width // 4)), 3)]


def render_review(out_dir: Path | str | None = None, store: Path | str | None = None) -> list[str]:
    """只读 live store + 压缩包，生成给作者看的对比图（2000 画布立绘 + 脸锚 / cut-in 边缘）。返回写出的路径。"""
    from PIL import Image, ImageDraw, ImageFont
    import wf_assets
    store = Path(core.resolve_active_store() if store is None else store)
    out_dir = REPO / REVIEW_DIR if out_dir is None else Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    gray = ArchiveSource()
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22)
    except OSError:
        font = ImageFont.load_default()
    band = ART_REVIEW["149995"]["official_face_y_p10_p90"]

    def live_png(tier, logical):
        return _png(wf_assets.path_in_root(store, tier, logical).read_bytes())

    def live_nested(logical, outer):
        table = X.unpack(core.table_path(store, logical).read_bytes())
        return {inner: X.csv_read(v) for inner, v in X.unpack(table[outer]).items()}

    def checker(w, h, n):
        img = Image.new("RGBA", (w, h), (235, 235, 235, 255))
        draw = ImageDraw.Draw(img)
        for y in range(0, h, n):
            for x in range(0, w, n):
                if (x // n + y // n) % 2:
                    draw.rectangle([x, y, x + n - 1, y + n - 1], fill=(210, 210, 210, 255))
        return img

    def canvas(png, cimg, fsa, title):
        x, y, w, h = map(int, cimg[0])
        fx, fy = int(fsa[0][3]), int(fsa[0][4])
        base = checker(2000, 2000, 50)
        base.alpha_composite(png, (x, y))
        draw = ImageDraw.Draw(base)
        draw.rectangle([0, band[0], 1999, band[1]], outline=(0, 160, 0, 255), width=6)
        draw.rectangle([x, y, x + w - 1, y + h - 1], outline=(0, 90, 255, 255), width=6)
        draw.line([fx - 60, fy, fx + 60, fy], fill=(255, 0, 0, 255), width=10)
        draw.line([fx, fy - 60, fx, fy + 60], fill=(255, 0, 0, 255), width=10)
        tile = Image.new("RGBA", (600, 680), (255, 255, 255, 255))
        tile.alpha_composite(base.resize((600, 600), Image.LANCZOS), (0, 80))
        draw = ImageDraw.Draw(tile)
        ok = band[0] <= fy <= band[1]
        draw.text((8, 4), f"{title}  PNG {w}x{h}@({x},{y})", fill=(0, 0, 0, 255), font=font)
        draw.text((8, 40), f"脸锚({fx},{fy}) {'在' if ok else '不在'}官方带{band[0]}-{band[1]}",
                  fill=(0, 120, 0, 255) if ok else (200, 0, 0, 255), font=font)
        return tile

    written = []
    for cid, name, filename in (("149995", "希耶提", "seofon_full_shot_compare.png"),
                                ("149996", "泳装希尔媞", "swim_full_shot_compare.png")):
        code = SPECS[cid]["code"]
        ours_cimg, ours_fsa = live_nested(CIMG, cid), live_nested(FSA, cid)
        tiles = []
        for slot in ("0", "1"):
            logical = f"character/{code}/ui/full_shot_1440_1920_{slot}.png"
            tiles.append(canvas(live_png("medium", logical), ours_cimg[slot], ours_fsa[slot], f"我方 live 槽{slot}"))
            tiles.append(canvas(_png(gray.raw("medium", logical)), PRESENTATION_ROWS[CIMG, cid][slot],
                                PRESENTATION_ROWS[FSA, cid][slot], f"灰版 槽{slot}"))
        sheet = Image.new("RGBA", (1230, 70 + 2 * 700), (255, 255, 255, 255))
        ImageDraw.Draw(sheet).text((10, 10), f"{name} {cid} 立绘 2000×2000 画布：绿框=官方脸锚y带 蓝框=PNG "
                                             "红十字=脸锚（槽1=觉醒）", fill=(0, 0, 0, 255), font=font)
        for i, tile in enumerate(tiles):
            sheet.alpha_composite(tile, ((i % 2) * 630, 70 + (i // 2) * 700))
        path = out_dir / filename
        sheet.convert("RGB").save(path)
        written.append(str(path))

    tiles = []
    for code in ("seofon_wind", "wind_spgirl_swim"):
        for slot in ("0", "1"):
            logical = f"character/{code}/ui/skill_cutin_{slot}.png"
            for who, image in (("我方", live_png("medium", logical)), ("灰版", _png(gray.raw("medium", logical)))):
                top, left, right, _cover = cutin_edges(image)
                bg = checker(1024, 512, 32)
                bg.alpha_composite(image)
                draw = ImageDraw.Draw(bg)
                for value, box in ((top, [0, 0, 1023, 5]), (left, [0, 0, 5, 511]), (right, [1018, 0, 1023, 511])):
                    if value >= 8:
                        draw.rectangle(box, fill=(255, 0, 0, 255))
                tile = Image.new("RGBA", (512, 292), (255, 255, 255, 255))
                tile.alpha_composite(bg.resize((512, 256), Image.LANCZOS), (0, 36))
                label = f"{'希耶提' if code == 'seofon_wind' else '泳装'} cut-in{slot} {who} 边alpha 上{top}左{left}右{right}"
                ImageDraw.Draw(tile).text((4, 4), label, font=font,
                                          fill=(200, 0, 0, 255) if max(top, left, right) >= 8 else (0, 120, 0, 255))
                tiles.append(tile)
    sheet = Image.new("RGBA", (1054, 60 + 4 * 308), (255, 255, 255, 255))
    ImageDraw.Draw(sheet).text((10, 10), "skill_cutin：红边 = 该边 alpha≥8（官方 60 张三边中位数 0）",
                               fill=(0, 0, 0, 255), font=font)
    for i, tile in enumerate(tiles):
        sheet.alpha_composite(tile, ((i % 2) * 542, 60 + (i // 2) * 308))
    path = out_dir / "skill_cutin_edges_compare.png"
    sheet.convert("RGB").save(path)
    written.append(str(path))
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="灰服三角色导入：解包 / 生成美术对比图")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("extract", help="把钉哈希的灰方压缩包解到 GRAY_ROOT（默认 work/gray3/production）")
    cmd.add_argument("--root", default=None)
    cmd.add_argument("--archive", default=None)
    cmd = sub.add_parser("review", help="只读 live store + 压缩包，生成美术对比图到 work/gray3/review")
    cmd.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    if args.command == "extract":
        count = extract(args.root, args.archive)
        print(f"extracted {count} new/changed member(s) to {GRAY_ROOT if args.root is None else args.root}")
    else:
        for path in render_review(args.out):
            print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
