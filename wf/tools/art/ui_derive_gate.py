# -*- coding: utf-8 -*-
"""角色 UI 派生图门禁:形状蒙版、不透明度包络、同宽高比槽同构图。

三条判据全部来自**官方 1.4.0 全量档**(`.cdn/cn/archive-medium-full/pinball-1.4.0-*.zip`)
的普查,不是从 live store 统计的 —— store 里混着自制角色,拿它当基线会把自己的偏差
当成官方标尺(见 memory `wf-official-baseline-not-store`)。

普查口径(2026-08-28):489 个官方角色 × 每个图标槽的 `_0`/`_1` 两张。

1. **尺寸**:每个槽在全表几乎只有一个尺寸(`battle_member_status` 488/489 是 58×58,
   `thumb_party_main` 488/489 是 186×392)。客户端 `trimmed_image` 按官方尺寸给每张
   UI 图套 frame,换尺寸不同步表 = 游戏内错位。
2. **形状蒙版**:异形框(圆/六边形/水滴条/圆角方)的形状就写在官方 alpha 里。
   `battle_control_board` 978 张里 84.7% alpha 逐字节相同、`cutin_skill_chain` 99.8%
   相同 —— 蒙版取**众数图案**,不能取并集(少数官方满框件会把并集撑成矩形)。
   派生图必须满足 `new_alpha <= mask`;否则游戏里就是一块方砖而不是六边形/水滴。
3. **不透明度包络**:官方图标是**不透明**的(有底),`square` 覆盖率 `_0` p1=0.690。
   派生图如果是抠图直接落盘,覆盖率会掉到 0.2~0.4,游戏里表现为「角色浮在空框里 /
   只剩上半身」。
   包络**按 `_0` / `_1` 两个立绘槽分开统计**(`OFFICIAL_COVERAGE_BY_LEVEL`):两槽的
   分布并不同分布,只按 `_0` 定包络会两头出错 —— 详见该常量上方的注释。
   合并口径 `OFFICIAL_COVERAGE` 只在拿不到槽号时用。
4. **同宽高比槽同构图**:官方 `square`/`square_132_132`/`square_round_136_136`/
   `square_round_95_95` 是**同一张图的不同分辨率**(60 个官方角色实测,缩放后
   mean|ΔRGB| ≤ 1.1/255);`thumb_level_up` 与 `thumb_party_unison` 同理。
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

# 槽 -> 官方标准尺寸 (W, H)
OFFICIAL_ICON_SIZES: dict[str, tuple[int, int]] = {
    'square': (212, 212),
    'square_132_132': (132, 132),
    'square_round_136_136': (136, 136),
    'square_round_95_95': (95, 95),
    'battle_member_status': (58, 58),
    'battle_control_board': (104, 268),
    'cutin_skill_chain': (276, 319),
    'thumb_level_up': (252, 329),
    'thumb_party_main': (186, 392),
    'thumb_party_unison': (144, 188),
    'skill_cutin': (1024, 512),
}

# 槽 -> (p1, p99) 官方不透明像素占比(alpha > 8),**`_0` 与 `_1` 两个立绘槽合并**。
# 只在拿不到立绘槽号时用;知道槽号就走 OFFICIAL_COVERAGE_BY_LEVEL(见下)。
OFFICIAL_COVERAGE: dict[str, tuple[float, float]] = {
    'square': (0.697, 1.000),
    'square_132_132': (0.702, 1.000),
    'square_round_136_136': (0.699, 0.986),
    'square_round_95_95': (0.707, 0.987),
    'battle_member_status': (0.663, 0.808),
    'battle_control_board': (0.682, 0.683),
    'cutin_skill_chain': (0.753, 0.754),
    'thumb_level_up': (0.639, 0.995),
    'thumb_party_main': (0.447, 0.995),
    'thumb_party_unison': (0.643, 0.996),
    # cut-in 是**透明抠图**,不是不透明图标;整幅不透明会在战斗里盖住场地。
    'skill_cutin': (0.208, 0.845),
}

# 同一口径按**立绘槽**分开。官方 `_1`(觉醒/二形态)普遍比 `_0` 更满,`skill_cutin`
# 尤其:`_0` 465 张 p1/p99/max = 0.199/0.741/**0.784**,`_1` 483 张 = 0.252/0.867/**1.000**。
# `_1` 里整幅不透明是有官方先例的 —— `flame_witch_1` 正好 1.000,
# `psychic_yamikawa_1` 0.886、`shadow_redhood_1` 0.882(483 张里 3 张 > 0.88,罕见但存在)。
# 反过来 `thumb_party_main` 的下界必须看 `_1`:`_0` p1 = 0.569 而 `_1` p1 = **0.451**。
# ⇒ 只按 `_0` 定包络两头都会错:上界会把合法的官方风格 `_1` cut-in 判成不合格,
#   下界会把官方 `_1` 里那种「细长角色 + 大片留白」的缩略图判成不合格。
OFFICIAL_COVERAGE_BY_LEVEL: dict[str, dict[str, tuple[float, float]]] = {
    'square': {'0': (0.690, 1.000), '1': (0.727, 1.000)},
    'square_132_132': {'0': (0.698, 1.000), '1': (0.732, 1.000)},
    'square_round_136_136': {'0': (0.695, 0.986), '1': (0.731, 0.986)},
    'square_round_95_95': {'0': (0.700, 0.987), '1': (0.737, 0.987)},
    'battle_member_status': {'0': (0.657, 0.808), '1': (0.680, 0.808)},
    'battle_control_board': {'0': (0.682, 0.683), '1': (0.682, 0.683)},
    'cutin_skill_chain': {'0': (0.753, 0.754), '1': (0.753, 0.754)},
    'thumb_level_up': {'0': (0.636, 0.995), '1': (0.691, 0.995)},
    'thumb_party_main': {'0': (0.569, 0.995), '1': (0.451, 0.995)},
    'thumb_party_unison': {'0': (0.638, 0.996), '1': (0.693, 0.996)},
    'skill_cutin': {'0': (0.198, 0.741), '1': (0.251, 0.868)},
}

# 带形状蒙版的槽(官方 alpha 即形状)。`square` / `square_132_132` 满框无蒙版;
# `skill_cutin` 的 alpha 是角色自己的剪影,不是框,不能拿别人的 alpha 去 min。
SHAPE_SLOTS: tuple[str, ...] = (
    'square_round_136_136', 'square_round_95_95', 'battle_member_status',
    'battle_control_board', 'cutin_skill_chain',
    'thumb_level_up', 'thumb_party_main', 'thumb_party_unison',
)

# 同宽高比、官方为同一张图的槽组
ASPECT_GROUPS: tuple[tuple[str, ...], ...] = (
    ('square', 'square_132_132', 'square_round_136_136', 'square_round_95_95'),
    ('thumb_level_up', 'thumb_party_unison'),
)

ALPHA_ON = 8               # 视为「有内容」的 alpha 阈值
MASK_VIOLATION_MAX = 0.005  # 蒙版外允许的杂散像素占比
GROUP_DIVERGENCE_MAX = 4.0  # 同组 LANCZOS 缩放后 mean|dRGB|,官方 50 角色实测 max 1.07
COVERAGE_SLACK = 0.02       # 包络两端的相对放宽


def _rgba(image) -> np.ndarray:
    arr = np.asarray(image)
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError(f'需要 RGBA 数组,收到 shape={arr.shape}')
    return arr.astype(np.uint8, copy=False)


def coverage(image) -> float:
    """不透明像素占比。"""
    alpha = _rgba(image)[:, :, 3]
    return float((alpha > ALPHA_ON).mean())


def mask_violation_ratio(image, mask) -> float:
    """蒙版之外仍然不透明的像素 / 蒙版之外的像素总数。"""
    alpha = _rgba(image)[:, :, 3]
    mask = np.asarray(mask)
    if mask.shape != alpha.shape:
        raise ValueError(f'蒙版尺寸 {mask.shape} 与图 {alpha.shape} 不一致')
    outside = mask <= ALPHA_ON
    if not outside.any():
        return 0.0
    return float((alpha[outside] > ALPHA_ON).sum() / outside.sum())


def _lanczos(arr: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """LANCZOS 缩放到 (W, H)。官方同组图之间就是这个关系(实测残差 < 1.1/255)。"""
    from PIL import Image  # PIL 已是 mod-tools 既有依赖(wf_ui_derive / wf_canary_skin)
    return np.asarray(Image.fromarray(arr, 'RGBA').resize(size, Image.Resampling.LANCZOS))


def group_divergence(a, b) -> float:
    """两张同宽高比图:把大的 LANCZOS 缩到小的尺寸,再比双方都实心处的 mean|dRGB|。

    只在 alpha > 250 处比,避开异形蒙版边缘 —— 蒙版把边缘 RGB 连带清掉,
    在边上比会把「蒙版差异」误报成「构图差异」。官方 50 个角色实测 max 1.07。
    """
    A, B = _rgba(a), _rgba(b)
    if A.shape[0] * A.shape[1] < B.shape[0] * B.shape[1]:
        A, B = B, A
    if A.shape[:2] != B.shape[:2]:
        A = _lanczos(A, (B.shape[1], B.shape[0]))
    both = (A[:, :, 3] > 250) & (B[:, :, 3] > 250)
    if both.sum() < 64:
        return float('inf')
    return float(np.abs(A[:, :, :3].astype(int) - B[:, :, :3].astype(int))[both].mean())


def coverage_envelope(slot: str, level: str | None = None) -> tuple[float, float]:
    """该槽的官方不透明占比包络;给了立绘槽号(``'0'`` / ``'1'``)就用按槽口径。

    槽号未知时退回合并口径。合并口径是两槽**混样**后的 p1/p99,不是两槽包络的并集
    —— 混样会把分位点拉动一点,大多数槽两者相差 ≤0.010(小于 ``COVERAGE_SLACK``,
    判定不变),但 `skill_cutin` 的上界差 0.023(`_1` 0.868 vs 合并 0.845)、
    `thumb_party_main` 的下界差 0.122(`_0` 0.569 vs 合并 0.447)。
    ⇒ **知道槽号就一定要传 ``level``**,退化路径只是兜底。
    """
    if level is not None:
        per_level = OFFICIAL_COVERAGE_BY_LEVEL.get(slot)
        if per_level is not None and level in per_level:
            return per_level[level]
    return OFFICIAL_COVERAGE[slot]


def derived_icon_problems(icons: Mapping[str, object],
                          masks: Mapping[str, object] | None = None,
                          groups: Sequence[Sequence[str]] | None = None,
                          level: str | None = None) -> list[str]:
    """检查一套派生图标;返回人读的问题列表(空 = 通过)。

    ``icons``  槽名 -> RGBA 数组(H, W, 4)。未知槽名忽略。
    ``masks``  槽名 -> 官方形状蒙版 alpha(H, W)。缺省则跳过蒙版判据。
    ``level``  这套图是哪个立绘槽(``'0'`` / ``'1'``);给了就用按槽的占比包络。
    """
    problems: list[str] = []
    for slot, image in sorted(icons.items()):
        if slot not in OFFICIAL_ICON_SIZES:
            continue
        arr = _rgba(image)
        h, w = arr.shape[:2]
        want = OFFICIAL_ICON_SIZES[slot]
        if (w, h) != want:
            problems.append(f'{slot}: 尺寸 {w}x{h} != 官方 {want[0]}x{want[1]}')
            continue
        lo, hi = coverage_envelope(slot, level)
        cov = coverage(arr)
        if cov < lo - COVERAGE_SLACK:
            problems.append(f'{slot}: 不透明占比 {cov:.3f} 低于官方下界 {lo:.3f}'
                            f'(游戏里会露出空框)')
        elif cov > min(1.0, hi + COVERAGE_SLACK):
            problems.append(f'{slot}: 不透明占比 {cov:.3f} 高于官方上界 {hi:.3f}')
        if masks and slot in SHAPE_SLOTS and slot in masks:
            over = mask_violation_ratio(arr, masks[slot])
            if over > MASK_VIOLATION_MAX:
                problems.append(f'{slot}: 形状蒙版外有 {over:.1%} 的不透明像素'
                                f'(异形框会显示成方块)')
    for group in (groups if groups is not None else ASPECT_GROUPS):
        present = [s for s in group if s in icons]
        for other in present[1:]:
            d = group_divergence(icons[present[0]], icons[other])
            if d > GROUP_DIVERGENCE_MAX:
                problems.append(f'{present[0]} 与 {other}: 同宽高比槽构图不一致'
                                f'(mean|dRGB|={d:.1f} > {GROUP_DIVERGENCE_MAX})')
    return problems
