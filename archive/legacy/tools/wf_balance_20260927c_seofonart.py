# -*- coding: utf-8 -*-
"""希耶提 149995 灰版美术导入（2026-09-27 第三轮 extra5 批次；包装 ``wf_balance_20260927b_gray3.ART_UNITS``）。

作者 2026-09-27 的决定（AskUserQuestion 答复，主会话逐字转述）：
  问题「希耶提的灰版美术要不要换进来？灰版觉醒立绘人物偏小偏下，脸在官方脸部区间之外，跟你在 1.4.447 实机否掉的构图
  一样；cut-in 上边和左边不透明。技能倍率和文案已经换成灰版了。」
  → 作者选「换成灰版美术」（27 个美术文件和 5 条定位行按灰版导入，包测试里 4 条构图检查按作者决定放宽）。

内容 = ``gray3.revise_art("149995")``：灰服压缩包里希耶提与 live 字节不同的 27 个美术文件（medium 25 张 PNG +
android 2 个 cut-in ATF，逐个钉 ``gray3.GRAY_FILES`` 的 sha256）+ 立绘定位 5 行（character_image / full_shot_image_attribute
各 1 个外层键、trimmed_image 3 行，取自灰链 1.4.92，pngW/pngH 与灰版 PNG 实际尺寸相等）。技能倍率/文案（gray3 核心导入）
已在 1.4.1054 发布，本模块不碰。

- BEFORE = ``gray3.ART_BEFORE_BY_CID["149995"]``：只锁美术输入（37 个 ``file_sha256`` + 6 条定位行），这些输入在 gray3 核心
  导入前后都没变，所以就是 live 1.4.1054 的值；美术导入后再跑即 fail closed。
- 输出键：``files``（``{"<tier>:<logical>": 解出文件路径}``，路径在 ``gray3.GRAY_ROOT``）与 ``presentation_table``
  （``{(logical, outer): rows | {inner: rows}}``），外加 ``notes.file_sha256``（27 个文件的钉住字节，暂存/预检复核）。
  暂存：extra5 ``stage_batch.splice_presentation``——字节 = ``gray3.encode_presentation``（内层行无尾换行，与 live 同格式），
  候选走 ``Plan`` 的呈现直写 + manifest 重封路径（RevisionCandidate.finish 的呈现保护不允许玩法修订改美术）。
- 候选 ``work/character_packs/seofon_wind``：manifest 现值 1.0.3（gray3 核心导入）→ 1.0.4（= ``ART_UNITS`` 声明值）。
- 包测试：``work/character_packs/seofon_wind/gray_art_20260927.py`` 钉这 27 个文件的 sha256；包内 4 条构图/边缘/生成器
  一致性检查只对这些字节豁免，其余检查照旧（作者 2026-09-27 选择灰版美术）。``seofon_art.py`` / ``build_workspace.py``
  的美术产出从此不再是真源，不得重跑覆盖。

纯函数：``revise`` 只读 ``read()`` 与钉住哈希的灰方来源，不写任何文件；不写 live/assets/.cdn/候选，不发布，不 git。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

import wf_balance_20260927b_gray3 as G3

CID = "149995"
CODE = "seofon_wind"
PACKAGES = ["seofon_wind"]
#: 候选 manifest 现值 1.0.3（gray3 核心导入后回读）→ 递增；与 gray3.ART_UNITS 声明的版本相同。
PACKAGE_VERSION = {"seofon_wind": "1.0.4"}
CAPABILITIES: list[str] = []
REVIEWED_DRIFT: dict = {}
#: live 1.4.1054 的美术输入基线（gray3 核心导入不改这些键）。
BEFORE = G3.ART_BEFORE_BY_CID[CID]
digest = G3.digest

AUTHOR_DECISION = {
    "date": "2026-09-27",
    "channel": "AskUserQuestion 答复（主会话逐字转述）",
    "question": ("希耶提的灰版美术要不要换进来？灰版觉醒立绘人物偏小偏下，脸在官方脸部区间之外，跟你在 1.4.447 实机否掉的"
                 "构图一样；cut-in 上边和左边不透明。技能倍率和文案已经换成灰版了。"),
    "answer": "换成灰版美术",
    "scope": "27 个美术文件和 5 条定位行按灰版导入，包测试里 4 条构图检查按作者决定放宽",
}

#: 包测试豁免登记（按 sha256；豁免只对灰版字节生效，文件被重新生成即恢复检查）。
PACKAGE_TEST_EXEMPTIONS = [
    "work/character_packs/seofon_wind/test_runtime_regressions.py::test_skill_cutin_respects_the_official_transparent_edges"
    "（灰版 cut-in 豁免上/左/右三边透明；覆盖率 ≤0.772 照旧）",
    "work/character_packs/seofon_wind/test_runtime_regressions.py::"
    "test_trimmed_image_declares_the_2000_canvas_and_matches_character_image（灰版立绘豁免脸锚 y 官方带与两槽同高；"
    "2000 画布、两表 tx/ty、pngW/H、装进画布、脸锚在图内照旧）",
    "work/character_packs/seofon_wind/test_build_workspace.py::test_full_shots_land_on_the_official_face_and_foot_anchors"
    "（灰版立绘豁免「包内字节 = seofon_art 产物」；生成器自身的构图检查照旧）",
    "work/character_packs/seofon_wind/test_build_workspace.py::"
    "test_generated_avatar_slots_are_face_centered_and_keep_donor_alpha（灰版头像/图标豁免「包内 = 独立脸部裁切」；"
    "生成器产物检查照旧）",
]


def revise(read: Callable[[str, Any], Any], gray: Any = None) -> dict:
    """live（BEFORE 锁定的美术输入）→ 灰版美术与定位行。``gray`` 默认 ``gray3.ArchiveSource()``（钉哈希的解出目录/压缩包）。"""
    out = G3.revise_art(CID, read, gray)
    pins = {member: G3.GRAY_FILES[member] for member in out["files"]}
    notes = out["notes"]
    notes.update(
        source="mod-tools/wf_balance_20260927c_seofonart.py（包装 wf_balance_20260927b_gray3.ART_UNITS / revise_art）",
        author_decision=deepcopy(AUTHOR_DECISION),
        requires=("作者 2026-09-27 已在当次请求里接受灰版美术（含觉醒构图与 cut-in 边缘），见 author_decision；"
                  "同一单元已按灰版 27 个文件的 sha256 豁免包内 4 条测试"),
        file_sha256=pins,
        presentation_encoding=("gray3.encode_presentation：嵌套表 raw_outer、平表 flat claim，内层行均无尾换行"
                               "（extra5 stage_batch.splice_presentation）"),
        package=dict(package="seofon_wind", version_from="1.0.3", version_to=PACKAGE_VERSION["seofon_wind"],
                     test_exemptions=list(PACKAGE_TEST_EXEMPTIONS)),
        runtime_verified=False,
    )
    return out


#: 多角色接口（extra5 stage_batch 按 UNITS 暂存；单条 ⇒ plan 名 seofonart--seofon_wind）。
UNITS = [dict(CID=CID, CODE=CODE, PACKAGES=list(PACKAGES), PACKAGE_VERSION=dict(PACKAGE_VERSION),
              CAPABILITIES=list(CAPABILITIES), REVIEWED_DRIFT=dict(REVIEWED_DRIFT), BEFORE=BEFORE,
              REQUIRES_AUTHOR_SIGNOFF=True, AUTHOR_DECISION=AUTHOR_DECISION, revise=revise)]
