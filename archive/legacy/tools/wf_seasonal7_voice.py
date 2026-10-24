"""七角色季节换装版（seasonal7-20260916）语音工具链。

design json 的 voice 字段 → Seed Audio 请求（复用 wf_art_voice_api.payload/generate）
→ 后处理（-14 LUFS、真峰 ≤-1.65 dBTP、44.1k 单声道 96k CBR、mp3_encode 严格校验）
→ 装包（存储态 MP3、character_speech 8 行、matched_skill_ready 原生路由、表 claims）。

边界：不写 live store、assets、.cdn、src；装包函数只写调用方给定的候选 package。
密钥只从进程环境 WF_SEED_AUDIO_KEY 读取；--key-file 由父进程读文件后注入子进程环境，
不进参数、日志、回执或报告。
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager, ExitStack
from copy import deepcopy
from dataclasses import asdict
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import wave
import zlib

import numpy as np

import wf_art_voice_api as api
import wf_assets
import wf_mod_tool as core
import wf_voice_gate as gate
from wf_art_voice_audio import amplitude
from wf_art_voice_enablement import native_excluded
from wf_gerald_voice_audio import metadata, pcm
from wf_gerald_voice_level_audio import measure

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'work' / 'character_packs' / 'seasonal7-20260916'
DESIGN_DIR = PACK / 'design'
VOICE_DIR = PACK / 'voice'
REFS_DIR = VOICE_DIR / 'refs'
REFS_INDEX = REFS_DIR / 'refs.json'
GENERATION_DIR = VOICE_DIR / 'generation'
SMOKE_DIR = VOICE_DIR / 'smoke'
KEY_FILE = PACK / '.secrets' / 'seed_audio.key'
KEY_ENV = 'WF_SEED_AUDIO_KEY'

# role 键只用小写字母（wf_art_voice_api.generate 的输出目录正则 [a-z]+）。
ROLES = {
    'regis': dict(cid='139994', code='rec_android_seaside', template_id='131020', template_code='rec_android_1anv'),
    'tekuto': dict(cid='139993', code='super_robot_tailcoat', template_id='131092', template_code='super_robot'),
    'zantetsu': dict(cid='159998', code='samurai_robot_plum', template_id='151117', template_code='samurai_robot_smr22'),
    'zehr': dict(cid='159997', code='guildknight_leader_tavern', template_id='151069', template_code='guildknight_leader'),
    'philia': dict(cid='159996', code='wind_oracle_yukata', template_id='141165', template_code='wind_oracle_meteor23'),
    'primula': dict(cid='169992', code='blackflower_wiz_yukata', template_id='161123', template_code='blackflower_wiz_smr22'),
    'yuki': dict(cid='129991', code='psychic_yuki_swim', template_id='121147', template_code='psychic_yuki_ny23'),
}

# 相对 character/<code>/voice/ 的官方目录结构（不带 .mp3）。home 用 home_N：
# wf_assets.char_asset_manifest 只认 home_0..9 这类自定义名，其他名导出/直推会丢。
HOME_SLOTS = tuple(f'home/home_{i}' for i in range(6))
SLOTS = ('ally/join', 'ally/evolution', *HOME_SLOTS,
         'battle/battle_start_0', 'battle/battle_start_1',
         'battle/skill_ready', 'battle/matched_skill_ready',
         *(f'battle/skill_{i}' for i in range(4)),
         'battle/power_flip_0', 'battle/power_flip_1',
         'battle/outhole_0', 'battle/outhole_1',
         'battle/win_0', 'battle/win_1')
# 引擎实际支持的全集（`CharacterShortVoiceLogic.generateVoicePaths` 扫到 511，这里只开到
# 有台词稿先例的号段）。SLOTS 是它的子序列，所以用 ALL_SLOTS 排序不会改变旧的槽位次序。
ALL_SLOTS = ('ally/join', 'ally/evolution',
             *(f'home/home_{i}' for i in range(10)),
             *(f'battle/battle_start_{i}' for i in range(4)),
             'battle/skill_ready', 'battle/matched_skill_ready',
             *(f'battle/skill_{i}' for i in range(8)),
             *(f'battle/matched_skill_{i}' for i in range(4)),
             'battle/power_flip_0', 'battle/power_flip_1',
             'battle/outhole_0', 'battle/outhole_1',
             'battle/win_0', 'battle/win_1')
# 凯尔：标准 22 槽 + 技能发动 skill_4/skill_5（序号池均匀随机）
# + battle_start_2/battle_start_3（技能准备引擎硬上限 2 条，多出的两条改投开战池）。
KYLE_EXTRA_SLOTS = ('battle/skill_4', 'battle/skill_5', 'battle/battle_start_2', 'battle/battle_start_3')
SLOTS_26 = tuple(s for s in ALL_SLOTS if s in set(SLOTS) | set(KYLE_EXTRA_SLOTS))
SUBTITLE_SLOTS = (*HOME_SLOTS, 'ally/join', 'ally/evolution')
SUBTITLE_MAX = 82          # 官方 home 字幕最长 82 字；气泡不缩字、不截断
SUBTITLE_MAX_LINES = 4

# 表演时长目标（官方 p50–p90，见 mech_voice.md §4.1）；拼进 direction。v1 专用。
TIMING = {
    'join': '加入语音，从容完整，目标9至13秒',
    'evolution': '进化语音，情感完整，目标10至15秒',
    'home': '主页闲聊，从容自然，句间短暂换气，不拖长尾音，目标10至15秒',
    'battle_start_N': '开战短句，紧凑清晰，目标1.5至2.6秒',
    'skill_ready': '技能准备提示，紧凑清晰，尾音自然收住，目标1.2至2.2秒',
    'skill_N': '技能发动，坚定有力，只表达一个意象，目标1.8至3.2秒',
    'power_flip_N': '强力弹射的短促喊声，干脆利落，目标0.6至1.5秒',
    'outhole_N': '落洞时的短促反应，目标0.6至1.8秒',
    'win_N': '胜利台词，自然清晰，目标3至5.4秒',
}

# v2 逐槽时长分位：官方 8891 条实测（${WF_ROOT}/角色语音 全量 ffprobe），
# prompt 里写 **p25–p75**（第一轮写 p50–p90，实测中位偏长 +26%~+81%，准备音最离谱）。
# chars = 按实测语速（战斗短槽 4.5–5.5 字/秒、长槽 3.5–4.5 字/秒）倒推的日文字数（不含标点）。
SLOT_TARGETS = {
    'home':           dict(p10=7.15, p25=8.88, p50=10.93, p75=13.22, p90=15.80, official_max=26.25, chars=(32, 52)),
    'join':           dict(p10=6.70, p25=8.23, p50=10.01, p75=11.83, p90=13.85, official_max=21.68, chars=(30, 48)),
    'evolution':      dict(p10=8.03, p25=9.46, p50=11.40, p75=13.54, p90=15.10, official_max=20.90, chars=(34, 54)),
    'battle_start_N': dict(p10=1.18, p25=1.46, p50=1.83, p75=2.30, p90=2.61, official_max=5.85, chars=(7, 12)),
    'skill_ready':    dict(p10=0.90, p25=1.15, p50=1.49, p75=1.88, p90=2.22, official_max=3.84, chars=(5, 9)),
    'skill_N':        dict(p10=1.55, p25=2.01, p50=2.38, p75=2.82, p90=3.24, official_max=5.04, chars=(9, 14)),
    'power_flip_N':   dict(p10=0.71, p25=0.86, p50=1.07, p75=1.41, p90=1.72, official_max=3.17, chars=(2, 6)),
    'outhole_N':      dict(p10=0.65, p25=0.81, p50=1.02, p75=1.44, p90=1.91, official_max=3.40, chars=(3, 7)),
    'win_N':          dict(p10=2.38, p25=2.98, p50=3.63, p75=4.47, p90=5.43, official_max=9.06, chars=(11, 18)),
    'login':          dict(p10=1.82, p25=2.25, p50=2.93, p75=3.69, p90=4.26, official_max=5.51, chars=(8, 16)),
}
# 战斗短槽：句内停顿与拖长是第一轮「录得不好」的主因，`……` 在这些槽里一律不用。
SHORT_BATTLE_FAMILIES = frozenset({'skill_ready', 'skill_N', 'power_flip_N', 'outhole_N', 'battle_start_N'})

# 语速：本轮 v2 冒烟 4 条的实测（标准态时长 ÷ 去标点字数）
#   battle_start_0 12 字 / 1.855s = 6.47、skill_ready 11 字 / 1.907s = 5.77、
#   power_flip_0    4 字 / 0.862s = 4.64、home_0      58 字 / 13.218s = 4.39。
# 预算取实测**下沿**（短槽 5.0、长槽 4.0）：字数 ÷ 语速 = 预估秒数，语速取小 ⇒ 预估秒数取大
# ⇒ 预算偏紧，宁可让稿子短一点，也不要钱花完了才被 duration_band 毙掉。
# 这两个数同时是 `take_score` 的语速基准，全工具只有这一处真源。
CHARS_PER_SECOND_SHORT = 5.0
CHARS_PER_SECOND_LONG = 4.0
# 边缘裁剪只对战斗槽开：长槽的呼吸起手是表演的一部分。
TRIM_FAMILIES = SHORT_BATTLE_FAMILIES | {'win_N'}
TRIM_HEAD_SECONDS = 0.10
TRIM_TAIL_SECONDS = 0.15
TRIM_ACTIVE_DBFS = -48.0

SPEECH_TABLE = 'master/character/character_speech.orderedmap'
CHARACTER_TABLE = 'master/character/character.orderedmap'
SWITCH_TABLE = 'master/skill/switched_action_skill.orderedmap'
ACTION_TABLE = 'master/skill/action_skill.orderedmap'
SERVER_CHARACTER = 'cdndata/character.json'
VOICE_ACTOR = 'AI 合成配音'

# 生成
MAX_WORKERS = 2
MAX_AUTO_RETRIES = 1            # 同一请求（同指纹）最多自动重试 1 次，跨续跑累计
AUDIT_CODES = frozenset({'45001125'})
REFERENCE_AUDIT_CODES = frozenset({'45001127'})   # tts_create_ref：被拒的是参考音，不是台词
RETRY_BACKOFF = {429: 30.0}
DEFAULT_BACKOFF = 10.0
# 跨进程锁目录（mod-tools/work 已 gitignore）：同一角色只许一个进程在生成。
LOCK_DIR = ROOT / 'mod-tools' / 'work' / 'voice-locks'

# 后处理（杰拉德 -14 LUFS 方案：wf_gerald_voice_level_audio）
TARGET_LUFS = -14.0
PEAK_CEILING = -1.65
LIMITER_CEILING = -1.2
MAX_LIMITER_REDUCTION_DB = 4.0
LOUDNESS_TOLERANCE = 1.0
SAMPLE_DELTA_LIMIT = 128
MASTER_PARAMS = dict(target_lufs=TARGET_LUFS, peak_ceiling_dbtp=PEAK_CEILING,
                     limiter_ceiling_dbfs=LIMITER_CEILING,
                     max_limiter_reduction_db=MAX_LIMITER_REDUCTION_DB,
                     limiter='alimiter attack=5 release=80 level=disabled latency=enabled @176.4k',
                     codec='libmp3lame 44100Hz mono 96k CBR xing no-id3')
# v2：两遍 loudnorm（measured_* + linear=true），限幅只当安全网（削减 ≤2 dB）。
LOUDNORM_TP = -1.5
LOUDNORM_LRA = 11
SAFETY_LIMITER_REDUCTION_DB = 2.0
# 原始响度硬门：recipe 写 -20，本轮实测放宽到 -26（见 take_gates 的注释与 pipeline-v2.md）。
RAW_LUFS_FLOOR = -26.0

# 成品响度合格带（唯一真源）。数字来自官方原声实测，不是拍脑袋的 ±0.5：
# `rework2/voice/scratch/official_loudness.py` 随机取 40 个角色逐槽族量整合响度 ——
#   skill_ready p10 -14.4 / p50 -13.2 / p90 -12.3    outhole_0  p10 -18.3 / p50 -13.9 / p90 -12.2
#   power_flip_0 p10 -13.9 / p50 -12.8 / p90 -12.0   skill_0    p10 -13.5 / p50 -13.0 / p90 -12.4
#   battle_start_0 p10 -14.1 / p50 -13.0 / p90 -12.3 win_0      p10 -14.6 / p50 -13.5 / p90 -12.8
#   join p10 -14.9 / p50 -13.9 / p90 -13.2           真峰 p50 -0.4 ~ -1.1 dBFS
# 官方自己的离散度（p10→p90 约 2 dB）就比旧闸门 |final-(-14)|>0.5 的 1 dB 宽，
# 于是「比官方还准」的条目照样被判不过。改成以官方为准的非对称带：下限压着 join/win 的
# p10 再留一点，上限压着 power_flip 的 p50。TARGET_LUFS 仍是 -14（带内偏保守的一侧）。
MASTER_LOUDNESS_BAND = (-15.0, -12.8)


def loudness_verdict(lufs) -> str:
    """成品响度判定的唯一真源。

    `master_voice` 写进 QC 的 `loudness_status` 与 `take_gates` 的 `master_loudness`
    以前各写各的数（前者 ±LOUDNESS_TOLERANCE=1.0、后者 ±0.5），于是 QC 说 ok 的条目
    选优时照样被丢。两处都必须走这一个函数。
    """
    if lufs is None:
        return 'unmeasured'
    low, high = MASTER_LOUDNESS_BAND
    lufs = float(lufs)
    if lufs < low:
        return 'under_target'
    if lufs > high:
        return 'over_target'
    return 'ok'


# ---- 自适应密度级（仅 v2 / two_pass；v1 定增益路径一字不动）-----------------------
#
# 为什么需要它：两遍 loudnorm 用 linear=true，增益是 min(I目标-I实测, TP目标-TP实测)，
# 也就是 **成品响度被峰均比钉死**：final ≈ TP目标 - crest。凯尔原始音峰均比 18~22 dB
# （raw 中位 -20.1 LUFS / 峰值 -1.8 dBFS），官方成品只有约 12~13 dB，所以成品中位卡在
# -15.5、短句掉到 -18～-21.8。主控已验证放宽限幅上界无用（2/3/4/6 dB 四档 home_0 全是
# -15.0）——限幅在定增益段之后，压根不改 loudnorm 那一步的峰均比。唯一的杠杆是压缩。
#
# 档位表由实测网格选出（`scratch/` 的 crest_grid 两轮，10 条凯尔样本）：
#   仅压缩 thr-18dBFS/r2.5/attack5ms（=主控实验的形状） 峰均比中位 17.1，几乎没动；
#   attack 快到 1 ms 以下才咬得住齿音/爆破音；纯 alimiter（峰均比中位 14.7）不如压缩。
# 阈值写成「峰值以下多少 dB」而不是绝对 dBFS：先用纯增益把峰值归到
# DENSITY_NORMALIZE_PEAK_DBFS（增益不改变峰均比，所以这一步不做任何动态处理），
# 档位含义就与源的绝对电平无关，跨角色/跨 take 可复现。
DENSITY_NORMALIZE_PEAK_DBFS = -1.0
DENSITY_STAGES = (
    dict(name='light', threshold_below_peak_db=-20.0, ratio=2.5, attack_ms=1.0,
         release_ms=80.0, knee=4.0),
    dict(name='medium', threshold_below_peak_db=-24.0, ratio=3.5, attack_ms=0.7,
         release_ms=70.0, knee=4.0),
    dict(name='firm', threshold_below_peak_db=-28.0, ratio=5.0, attack_ms=0.5,
         release_ms=60.0, knee=4.0),
)


def density_filter(stage: dict, normalize_peak_dbfs: float = DENSITY_NORMALIZE_PEAK_DBFS) -> str:
    """一档密度级的 ffmpeg 滤镜串（软拐点、无 makeup —— 电平交给后面的 loudnorm）。"""
    threshold = 10 ** ((normalize_peak_dbfs + stage['threshold_below_peak_db']) / 20)
    return (f'acompressor=level_in=1:threshold={threshold:.9f}:ratio={stage["ratio"]:g}'
            f':attack={stage["attack_ms"]:g}:release={stage["release_ms"]:g}'
            f':knee={stage["knee"]:g}:makeup=1:detection=peak:link=average')


def density_ladder(normalize_peak_dbfs: float = DENSITY_NORMALIZE_PEAK_DBFS) -> str:
    """策略参数里记的那一行：只描述档位表，**不含**逐条用了哪一档。

    用了哪一档是逐条自适应的结果，写进 params 会让每条的 params 各不相同，
    续跑时 `process_run` 拿策略重算的期望值必然对不上 ⇒ 满屏假「QC drift」。
    """
    return (f'adaptive acompressor before loudnorm; peak normalised to {normalize_peak_dbfs:g} dBFS; '
            + '; '.join(f'{s["name"]}=thr {s["threshold_below_peak_db"]:g}dB below peak/'
                        f'ratio {s["ratio"]:g}/attack {s["attack_ms"]:g}ms/'
                        f'release {s["release_ms"]:g}ms/knee {s["knee"]:g}'
                        for s in DENSITY_STAGES))


def limiter_bound(mode: str, max_limiter_reduction_db: float = MAX_LIMITER_REDUCTION_DB) -> float:
    """限幅削减上界的唯一真源：两遍 loudnorm 下限幅只当安全网，钳到 2 dB。

    钳位必须只写在这一处。`master_voice`（实际处理 + 写 QC 报告）与 `process_run`
    （按策略重算期望参数判漂移）曾各自算一遍：前者钳到 2.0、后者留 4.0，于是
    第二遍 `process` 的缓存分支恒判 `params != expected`，抛「QC drift…use a new
    run directory」逼人重开 run 目录 = 按抽卡预算重复计费。
    """
    if mode == 'two_pass':
        return min(max_limiter_reduction_db, SAFETY_LIMITER_REDUCTION_DB)
    return max_limiter_reduction_db


def master_params(*, mode: str = 'fixed_gain', trim: bool = False,
                  max_limiter_reduction_db: float = MAX_LIMITER_REDUCTION_DB,
                  density: bool = False) -> dict:
    """QC 报告里记的处理参数；`process_run` 用它判 QC 漂移，所以必须随策略变化。

    `density` 记的是「本条允许上密度级 + 档位表」这个**策略**，不是逐条的结果。
    """
    max_limiter_reduction_db = limiter_bound(mode, max_limiter_reduction_db)
    density = bool(density) and mode == 'two_pass'
    if (mode == 'fixed_gain' and not trim and not density
            and max_limiter_reduction_db == MAX_LIMITER_REDUCTION_DB):
        return MASTER_PARAMS
    params = dict(MASTER_PARAMS, mode=mode, max_limiter_reduction_db=max_limiter_reduction_db)
    if mode == 'two_pass':
        params['loudnorm'] = f'two-pass measured linear=true I={TARGET_LUFS} TP={LOUDNORM_TP} LRA={LOUDNORM_LRA}'
    if density:
        params['density'] = density_ladder()
    if trim:
        params['edge_trim'] = (f'RMS {TRIM_ACTIVE_DBFS:g} dBFS/10ms, head {TRIM_HEAD_SECONDS:g}s, '
                               f'tail {TRIM_TAIL_SECONDS:g}s')
    return params

# 参考音频（校园配方）
REF_FILTERS = ('silenceremove=start_periods=1:start_duration=0.03:start_threshold=-55dB,'
               'areverse,silenceremove=start_periods=1:start_duration=0.03:start_threshold=-55dB,'
               'areverse,highpass=f=70,loudnorm=I=-20:TP=-2:LRA=11')
REF_RANGES = {'battle': (1.5, 6.0), 'home': (10.0, 15.0)}

# v2 参考音：归一目标从 I=-20 提到 I=-16（第一轮参考音 -20 ⇒ 接口原始输出中位 -24.8 LUFS
# ⇒ 32% 成品达不到 -14、92 条顶满 4 dB 限幅；thorn 用未归一的 -15.9 原声，0/22 未达标）。
REF_FILTERS_V2 = ('silenceremove=start_periods=1:start_duration=0.03:start_threshold=-55dB,'
                  'areverse,silenceremove=start_periods=1:start_duration=0.03:start_threshold=-55dB,'
                  'areverse,highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11')
# 本身就够响的源（索恩的 GBF 原声 -15.9/-17.6 LUFS）不再归一：第一轮全批只有它 0/22 未达标。
REF_FILTERS_V2_KEEP_LEVEL = ('silenceremove=start_periods=1:start_duration=0.03:start_threshold=-55dB,'
                             'areverse,silenceremove=start_periods=1:start_duration=0.03:start_threshold=-55dB,'
                             'areverse,highpass=f=70')
# 内部停顿也要去掉的配方（作者自带样本：停顿会被模型当节奏学走，recon §P0-4）。
# `start_periods` 在本机 ffmpeg 里只接受 [0,9000]；去掉内部停顿靠 `stop_periods=-1`。
REF_FILTERS_V2_GAPLESS = ('silenceremove=start_periods=1:start_duration=0.25:start_threshold=-45dB:'
                          'stop_periods=-1:stop_duration=0.25:stop_threshold=-45dB,'
                          'highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11')
# 按族给下限：官方 skill_ready p50 只有 1.49s、power_flip p50 只有 1.07s，
# 第一轮的 battle 统一 1.5s 下限把 9/11 角色的官方短喊声全判成「太短」踢掉了。
REF_RANGES_V2 = {'ready': (0.5, 2.5), 'pf': (0.5, 2.5), 'outhole': (0.5, 2.5),
                 'skill': (1.2, 3.5), 'start': (0.8, 3.0), 'win': (2.0, 6.0),
                 'home': (8.0, 15.0), 'join': (6.0, 15.0),
                 'short': (0.5, 6.0), 'long': (4.0, 15.0)}

# ---- 参考音电平：极短片段测不出整合响度，必须换一把尺 ----
# EBU R128 的整合响度有 400ms 的块与 -70 LUFS 的绝对门；清洗后 <0.4s 的片段测出来恒是
# -70，`loudnorm=I=-16` 拿不到有效测量值 ⇒ **一点增益都没加**。实测后果：refs-v2 里 5 条
# 这样的参考音 RMS 在 -11.8～-16.7 dBFS、全部顶在 -1.5 dBFS，比其余 80 条热 3～5 dB，
# 而索引里记的却是「-70.0 LUFS」这个假数。这些片段改走 RMS 归一（峰值封顶），
# 索引如实记 `loudness_method`。
LOUDNESS_UNMEASURABLE_LUFS = -69.0      # ffmpeg 在测不出时回报 -70.0
SHORT_REFERENCE_SECONDS = 0.4           # R128 的整合窗；短于它就别信整合响度
# 目标 RMS = 现有 80 条「整合响度可测」参考音的实测 RMS 中位数（-16.80 dBFS，
# p25 -17.32 / p75 -16.26）。这样 RMS 归一的短片段与 loudnorm=I=-16 的长片段等响。
REFERENCE_TARGET_RMS_DBFS = -16.8
REFERENCE_PEAK_CEILING_DBFS = -1.5      # 与 loudnorm 的 TP=-1.5 对齐
_LOUDNORM_COMPONENT = re.compile(r'(?:^|,)\s*loudnorm=[^,]*')
# 按顺序取第一条清洗后时长落在区间内的官方语音。首选项与 mech_voice.md §3.4 一致；
# 斩铁/勇希/普莉姆拉 skill_ready 太短，战斗参考用 battle_start/win。
REF_CANDIDATES = {
    'regis': {'battle': [('rec_android_1anv', 'battle/skill_ready'), ('rec_android_1anv', 'battle/battle_start_0')],
              'home': [('rec_android_1anv', 'home/otto_mitsukatte'), ('rec_android_1anv', 'home/sate_shinmiri')]},
    'tekuto': {'battle': [('super_robot', 'battle/battle_start_0'), ('super_robot', 'battle/battle_start_1')],
               'home': [('super_robot', 'home/kondosa'), ('super_robot', 'home/jibunomitsuketakute')]},
    'zantetsu': {'battle': [('samurai_robot_smr22', 'battle/battle_start_0'), ('samurai_robot_smr22', 'battle/win_0')],
                 'home': [('samurai_robot', 'home/ninjazamuraiwa'), ('samurai_robot', 'home/ninjazamuraino'),
                          ('samurai_robot', 'home/muron_ninjazamuraiga')]},
    'zehr': {'battle': [('guildknight_leader', 'battle/battle_start_1'), ('guildknight_leader', 'battle/battle_start_0')],
             'home': [('guildknight_leader', 'home/yurukuyarebaiisa'), ('guildknight_leader', 'home/n_iikazefuiterunaa')]},
    'philia': {'battle': [('wind_oracle_meteor23', 'battle/skill_ready'), ('wind_oracle_meteor23', 'battle/win_0')],
               'home': [('wind_oracle_meteor23', 'home/konoisho'), ('wind_oracle_meteor23', 'home/hitoni')]},
    'primula': {'battle': [('blackflower_wiz_smr22', 'battle/battle_start_1'), ('blackflower_wiz_smr22', 'battle/win_1')],
                'home': [('blackflower_wiz_smr22', 'home/bakansunante'), ('blackflower_wiz_smr22', 'home/kondoarisusanto'),
                         ('blackflower_wiz_smr22', 'home/a_au_konokakko')]},
    'yuki': {'battle': [('psychic_yuki_ny23', 'battle/battle_start_1'), ('psychic_yuki_ny23', 'battle/win_0')],
             'home': [('psychic_yuki_ny23', 'home/dattesa_kibun'), ('psychic_yuki_ny23', 'home/inahochanno')]},
}
REF_NOTES = {
    'zantetsu': 'samurai_robot_smr22 自身 6 条 home 均 ≥15.2s，cheiyaraaa_muu 开头为长喊声；'
                'home 参考取同角色同 CV 的基础版 samurai_robot。',
}

SMOKE_LINE = dict(
    role='regis', slot='battle/battle_start_0',
    persona=('成熟从容的成年男性机人绅士声音，优雅风趣、略带戏谑的低笑，把观察和记录人类当乐趣；'
             '措辞考究，自称“私”，自然清晰的日语发音'),
    direction='海边度假的轻松午后，从容优雅地招呼同伴出发',
    ja='さあ、行きましょう。', zh='来吧，我们出发。')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def find_tool(name: str) -> Path:
    found = shutil.which(name)
    if found:
        return Path(found)
    fallback = Path('C:/ProgramData/HP/LCDDisplayHelper/bin') / (name + '.exe')
    if fallback.is_file():
        return fallback
    raise FileNotFoundError(f'{name} not found on PATH')


# ---------------------------------------------------------------- 槽位、字幕、路由

def role_slots(role: str | None = None) -> tuple[str, ...]:
    """按角色取槽表：`ROLES[role]['slots']` 存在就用它，否则用全局 22 槽。

    凯尔需要 26 槽（多 skill_4/5 与 battle_start_2/3）；其余 11 人仍是 22 槽 ——
    以前 `SLOTS` 是全局常量、`validate_voice_plan` 要求精确相等，多开一个槽会把
    所有角色都要求凑 26 条。
    """
    info = ROLES.get(role) if role else None
    slots = (info or {}).get('slots')
    if not slots:
        return SLOTS
    unknown = [s for s in slots if s not in ALL_SLOTS]
    if unknown:
        raise ValueError(f'role {role!r} declares slots outside the engine set: {unknown}')
    return tuple(slots)


def slot_order(slot: str) -> int:
    """稳定排序键；SLOTS 是 ALL_SLOTS 的子序列，所以旧的 22 槽次序不变。"""
    return ALL_SLOTS.index(slot)


def normalize_slot(name, slots=None) -> str:
    """`skill_0` / `battle/skill_0` → `battle/skill_0`；默认只接受 22 个官方槽。

    `slots` 传角色槽表时按该表校验（凯尔 26 槽）。未知槽名报清楚的错并列出可用槽。
    """
    allowed = SLOTS if slots is None else tuple(slots)
    if not isinstance(name, str) or not name.strip():
        raise ValueError('voice slot must be a non-empty string')
    text = name.strip()
    if '/' not in text:
        group = 'ally' if text in ('join', 'evolution') else 'home' if text.startswith('home_') else 'battle'
        text = group + '/' + text
    if text not in allowed:
        raise ValueError(f'unsupported voice slot: {name!r}; this role accepts {", ".join(allowed)}')
    return text


def family(slot: str) -> str:
    """官方时长族；matched_skill_ready 共用 skill_ready 预算、matched_skill_N 共用 skill_N。"""
    if slot == 'battle/matched_skill_ready':
        fam = 'skill_ready'
    elif re.fullmatch(r'battle/matched_skill_\d+', slot):
        fam = 'skill_N'
    else:
        fam = gate.slot_family(slot)
    if fam not in gate.OFFICIAL_DURATION:
        raise ValueError(f'slot has no official duration family: {slot}')
    return fam


def prompt_band(slot: str) -> tuple[float, float]:
    """v2 prompt 里写的时长目标 = 官方 p25–p75。"""
    target = SLOT_TARGETS[family(slot)]
    return target['p25'], target['p75']


def chars_per_second(fam: str) -> float:
    """该族的预算语速（字/秒）。短战斗槽与长槽两档，实测依据见常量注释。"""
    return CHARS_PER_SECOND_SHORT if fam in SHORT_BATTLE_FAMILIES else CHARS_PER_SECOND_LONG


def char_budget(fam: str) -> dict:
    """字数预算的唯一真源，口径与 `take_gates` 的 duration_band 自洽。

    两档：

    * ``hard_max = floor(语速 × p90)``（**error**）—— 超过它，按实测语速这一条必然越过
      duration_band 的上沿，无论抽几次全部 take 都会被 `select` 毙掉，钱是白花的。
      例：outhole_N 的 p90=1.91s、语速 5.0 ⇒ 9 字；13 字 ÷ 5.0 ≈ 2.6s > 1.91s。
    * ``target``（**warn**）= ``SLOT_TARGETS[fam]['chars']``，约等于语速 × p25–p75，
      也就是 prompt 里写给模型的那条时长带。超出只是「大概率偏长」，不是必死。

    ``hard_min = ceil(语速 × p10)`` 同理给出下沿，但只当 warn：模型会用长元音把短句
    撑开，短句落在带内的概率比长句高得多。
    """
    target = SLOT_TARGETS[fam]
    cps = chars_per_second(fam)
    low, high = target['chars']
    return dict(family=fam, chars_per_second=cps, target=(int(low), int(high)),
                hard_max=int(cps * target['p90']), hard_min=int(math.ceil(cps * target['p10'])),
                band_seconds=(target['p25'], target['p75']),
                p10_seconds=target['p10'], p90_seconds=target['p90'])


def compose_direction(direction, slot: str) -> str:
    # payload 会接「。只说以下日语台词：」，这里不留句末标点，避免「。。」。
    parts = []
    for text in (direction or '', TIMING[family(slot)]):
        text = str(text).strip().rstrip('。.；; ')
        if text:
            parts.append(text)
    return '；'.join(parts)


# ---------------------------------------------------------------- v2 文本（表演指导 / 注音 / 台词规则）

_RUBY = re.compile(r'[一-鿿々〆々]+[（(]([぀-ゟ゠-ヿー・]+)[）)]')
_SENTENCE_END = '。！？!?'
_CLAUSE_SPLIT = re.compile(r'[；;：:，,、。．.！!？?\n]')
_KANA_ONLY = re.compile(r'^[぀-ゟ゠-ヿー・、。！？…\s]*$')


def expand_ruby(text: str) -> str:
    """`黒狼騎士（こくろうきし）` → `こくろうきし`：注音括号展开成读音本体。

    实证：带 `（ ）` 的请求里注音会被念出来（kyle/skill_0、kyle/home_2），
    所以 tts_text 必须是纯发音文本。这里做的是 ruby 语义的确定性替换 ——
    紧贴括号前的汉字串是注音底字，括号里是读音。
    """
    return _RUBY.sub(lambda m: m.group(1), text)


def strip_display_quotes(text: str) -> str:
    """表演指导里的 `「」『』` 去掉：它们会随说明一起进 prompt，没必要冒险。"""
    return text.translate(str.maketrans('', '', '「」『』'))


QUOTE_POLICIES = ('strip', 'positional', 'positional_inline')
_DISPLAY_QUOTED = re.compile('[「『]([^「」『』]*)[」』]')
_SENTENCE_SPLIT = re.compile('[。！？!?]+')
_HAS_KANA = re.compile('[\u3040-\u30ff]')


def _comparable(text: str) -> str:
    """片假名→平假名、去标点空格（与 normalize_spoken 同形，定义在它之前所以自带一份）。"""
    out = []
    for ch in text or '':
        if ch.isspace() or ch in '。、，,.！？!?…‥・ー〜～—―-「」『』':
            continue
        code = ord(ch)
        out.append(chr(code - 0x60) if 0x30A1 <= code <= 0x30F6 else ch)
    return ''.join(out)


def quote_reference(fragment: str, spoken_forms) -> str | None:
    """表演指导里引的一段台词 → 「第二句句尾」这类位置指代；不是台词里的话返回 None。"""
    want = _comparable(fragment)
    if not want:
        return None
    for spoken in spoken_forms:
        sentences = [c for c in (_comparable(p) for p in _SENTENCE_SPLIT.split(spoken or '')) if c]
        if not sentences:
            continue
        joined = ''.join(sentences)
        at = joined.find(want)
        if at < 0:
            continue
        starts, offset = [], 0
        for sentence in sentences:
            starts.append(offset)
            offset += len(sentence)
        first = max(i for i, start in enumerate(starts) if start <= at)
        last = max(i for i, start in enumerate(starts) if start < at + len(want))
        total = len(sentences)

        def label(i):
            if total == 1:
                return '这句'
            return '第一句' if i == 0 else '最后一句' if i == total - 1 else f'第{i + 1}句'

        if last > first:
            whole = at == starts[first] and at + len(want) == starts[last] + len(sentences[last])
            return f'{label(first)}到{label(last)}' if whole else f'{label(first)}后半到{label(last)}'
        sentence, local = sentences[first], at - starts[first]
        if len(want) == len(sentence):
            return label(first)
        if local == 0:
            return label(first) + '开头'
        if local + len(want) == len(sentence):
            return label(first) + '句尾'
        return label(first) + '中段'
    return None


def neutralize_quotes(text: str, spoken_forms) -> str:
    """`「台词片段」` → 位置指代。引的不是台词：含假名的换成「该处」，不含的只去括号。

    实证（中秋第二轮 kyle/stinel/magnus）：performance 里只去括号留下的日语片段，会被模型抢到
    句首念出来（回执 subtitle = 片段 + 整句），同一槽位连抽 4 次都复现 ⇒ 是 prompt 决定的，重抽无效。
    """
    def swap(match):
        inner = match.group(1)
        ref = quote_reference(inner, spoken_forms)
        if ref:
            return ref
        return '该处' if _HAS_KANA.search(inner) else inner
    return _DISPLAY_QUOTED.sub(swap, text)


_CLAUSE_UNITS = re.compile('[。！？!?、，,…‥—―\\s]+')


def _is_japanese_char(ch: str) -> bool:
    code = ord(ch)
    return 0x3040 <= code <= 0x30FF or 0x4E00 <= code <= 0x9FFF or ch in '々〆'


def neutralize_inline(text: str, spoken_forms) -> str:
    """没加「」直接写在说明里的台词片段（hibiki/charlene 的稿子）→ 位置指代。

    从左到右贪心取「说明里从这里开始、能在台词里原样找到的最长一段」。只换两类，宁可漏不可错：
    含假名的片段（单个假名也换：「重音在そ」照样会被抢到句首；中文说明里出现假名只可能是在引台词），以及恰好是台词里一整个分句的
    纯汉字片段（`金木犀`、`報酬`）。纯汉字的半截词（`一口`、`一曲`）不换 —— 它和中文说明里的
    「一口气」分不开，换错了会把指导本身改坏，而漏掉的代价只是那一条被 text 门拦下重抽。
    只给全中文说明的稿子用：日文写的语气描述（「素っ気ない口調」）会和台词撞上两字假名。
    """
    forms = [f for f in spoken_forms if f]
    clauses = {_comparable(c) for f in forms for c in _CLAUSE_UNITS.split(f) if _comparable(c)}
    out, i = [], 0
    while i < len(text):
        best = 0
        if _is_japanese_char(text[i]):
            for form in forms:
                size = 0
                while i + size < len(text) and text[i:i + size + 1] in form:
                    size += 1
                best = max(best, size)
        fragment = text[i:i + best].rstrip('。、，！？!?…—')
        keep = bool(_HAS_KANA.search(fragment)) or (len(fragment) >= 2 and _comparable(fragment) in clauses)
        ref = quote_reference(fragment, forms) if keep else None
        if ref:
            out.append(ref)
            i += best                                        # 片段后面跟着的标点一起吃掉
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)


def _clause(text: str, limit: int = 16) -> str:
    head = next((p for p in _CLAUSE_SPLIT.split(text) if p.strip()), '').strip()
    return head[:limit]


def compose_performance(direction, slot: str, *, quote_policy: str = 'strip',
                        spoken_forms=()) -> tuple[str, str]:
    """design/台词稿的 direction → (performance, tone)。

    direction 支持两种形状：字符串（整条当 performance，tone 取第一个分句），
    或对象 {tone, pace, breath, volume, stress, ending}。

    `quote_policy='positional'`（逐条 opt-in，稿里写 `quote_policy`）：引用的台词片段先换成位置指代
    再去括号。默认 `strip` 保持原样 —— 改默认会让已生成 take 的请求指纹全部变 stale。
    """
    if quote_policy not in QUOTE_POLICIES:
        raise ValueError(f'unknown quote_policy {quote_policy!r}')
    if quote_policy != 'strip':
        def clean(value):
            value = neutralize_quotes(str(value), spoken_forms)
            return neutralize_inline(value, spoken_forms) if quote_policy == 'positional_inline' else value
        if isinstance(direction, dict):
            direction = {k: clean(v) if isinstance(v, str) else v for k, v in direction.items()}
        else:
            direction = clean(direction or '')
    low, high = prompt_band(slot)
    tail = f'整条目标 {low:g}–{high:g} 秒，不拖字、不逐字慢读'
    if isinstance(direction, dict):
        tone = strip_display_quotes(str(direction.get('tone') or '').strip())
        pattern = (('语速', 'pace'), ('气息', 'breath'), ('音量', 'volume'),
                   ('重音落在', 'stress'), ('收尾', 'ending'))
        parts = [label + strip_display_quotes(str(direction[name]).strip())
                 for label, name in pattern if str(direction.get(name) or '').strip()]
        body = '；'.join(parts)
        if not tone:
            tone = _clause(body) or '自然'
    else:
        body = strip_display_quotes(str(direction or '').strip()).rstrip('。.；; ')
        tone = _clause(body) or '自然'
    performance = '；'.join(p for p in (body, tail) if p)
    return performance, tone


def speaker_label(voice: dict) -> tuple[str, str]:
    """(persona_short, voice_tag)：显式字段优先，缺省时按句号切 persona。

    persona 第一句 = 一句话定位，其余句子 = 音色括注（累计不超过 60 字）。
    """
    short = strip_display_quotes(str(voice.get('persona_short') or '').strip())
    tag = strip_display_quotes(str(voice.get('voice_tag') or '').strip())
    if short and tag:
        return short, tag
    persona = strip_display_quotes(str(voice.get('persona') or '').strip())
    sentences = [s for s in re.split(f'(?<=[{_SENTENCE_END}])', persona) if s.strip()]
    if not sentences:
        raise ValueError('persona is required to derive the speaker label')
    short = short or sentences[0].strip().rstrip(_SENTENCE_END)
    if not tag:
        picked, total = [], 0
        for sentence in sentences[1:]:
            body = sentence.strip().rstrip(_SENTENCE_END)
            if total + len(body) > 60 and picked:
                break
            picked.append(body)
            total += len(body)
        tag = '；'.join(picked) or short
    return short, tag


_CONTENT_RUN = re.compile(r'[一-鿿ァ-ヶー]{2,}')


def repeated_phrases(text: str) -> list[str]:
    """一句话里出现两次以上的实词（汉字/片假名连串）。"""
    counts = {}
    for run in _CONTENT_RUN.findall(text or ''):
        counts[run] = counts.get(run, 0) + 1
    return sorted(word for word, count in counts.items() if count >= 2)


def spoken_chars(text: str) -> int:
    """去标点后的日文字数（字数预算与语速换算都用这一把尺）。"""
    return len(re.sub(r'[^\w぀-ヿ一-鿿]', '', text or ''))


def check_ja_rules(slot: str, ja: str, tts: str, *, has_tts_text: bool = False) -> list[dict]:
    """台词硬规则的可机判部分；返回 findings（level='error' 的由调用方拦下）。

    符号硬门只卡**实际发给接口的文本**（`tts`，缺省时就是 ja）。`ja` 里允许留装饰符号
    （丝缇涅尔的 ♡ 是作者点名的「杂鱼」变奏，写进字幕/稿子没问题），但那时必须另写一条
    不含这些符号的 `tts_text`；缺了就报错并指名要补哪一条。

    `has_tts_text=False` 表示稿里没写 tts_text（管线会拿 ja 当发音文本）。
    """
    findings = []
    fam = family(slot)
    sent_bad = sorted({c for c in tts if c in api.FORBIDDEN_TTS_CHARS})
    ja_bad = sorted({c for c in ja if c in api.FORBIDDEN_TTS_CHARS})
    if sent_bad:
        if has_tts_text:
            fix = f'把 tts_text 里的 {"".join(sent_bad)} 删掉（ja 可以保留，字幕走 zh/ja）'
        else:
            fix = (f'这一条没写 tts_text，管线会把 ja 原样发给接口。'
                   f'补一条不含 {"".join(sent_bad)} 的 tts_text（纯发音文本，不带注音括号）')
        findings.append(dict(level='error', rule='forbidden_symbol', slot=slot, family=fam,
                             field='tts_text', detail=''.join(sent_bad), chars=spoken_chars(tts),
                             has_tts_text=has_tts_text, fix=fix,
                             why='引号/装饰符号的内容会被抢到句首先念、原位只剩 ☃ 占位；'
                                 '括号注音会被读出来'))
    elif ja_bad:
        findings.append(dict(level='warn', rule='decorative_symbol_in_ja', slot=slot, family=fam,
                             field='ja', detail=''.join(ja_bad),
                             why='ja 带装饰符号是允许的，但发给接口的是 tts_text —— '
                                 '这一条已经另写了干净的 tts_text，保持这样'))
    if fam in SHORT_BATTLE_FAMILIES and '…' in tts:
        findings.append(dict(level='error', rule='ellipsis_in_short_slot', slot=slot, family=fam,
                             field='tts_text', fix='把 …… 去掉，或者把这一条改成两句里的一句',
                             why='带 …… 的句内最大间隔中位 0.84s vs 不带 0.32s，'
                                 f'{fam} 的 p90 只有 {SLOT_TARGETS[fam]["p90"]:g}s，装不下'))
    if '　' in tts:
        findings.append(dict(level='error', rule='ideographic_space', slot=slot, family=fam,
                             field='tts_text', fix='删掉全角空格；要停顿就断句',
                             why='全角空格会被吞掉，停顿根本不会出现'))
    # 注音展开后汉字会变成假名，重复词只在 ja 里看得见 ⇒ 两边取并集。
    for phrase in sorted(set(repeated_phrases(tts)) | set(repeated_phrases(ja))):
        findings.append(dict(level='warn', rule='repeated_phrase', slot=slot, family=fam,
                             detail=phrase, fix=f'把重复的「{phrase}」改掉一处',
                             why='重复的显眼词会被抢到句首当假起手（第一轮 11 例；'
                                 '本轮冒烟 fluffy/home_0 的「整列」实证复现）'))
    chars = spoken_chars(tts)
    budget = char_budget(fam)
    low, high = budget['target']
    seconds = round(chars / budget['chars_per_second'], 2)
    shared = dict(slot=slot, family=fam, field='tts_text', chars=chars,
                  chars_per_second=budget['chars_per_second'], estimated_seconds=seconds,
                  target_chars=[low, high], hard_max_chars=budget['hard_max'],
                  band_seconds=list(budget['band_seconds']), p90_seconds=budget['p90_seconds'],
                  p10_seconds=budget['p10_seconds'])
    if chars > budget['hard_max']:
        findings.append(dict(level='error', rule='over_char_budget', limit=budget['hard_max'],
                             fix=f'删到 ≤{budget["hard_max"]} 字（理想 {low}–{high} 字）',
                             why=f'{chars} 字 ÷ {budget["chars_per_second"]:g} 字/秒 ≈ {seconds:g}s '
                                 f'> 官方 p90 {budget["p90_seconds"]:g}s，'
                                 f'select 的 duration_band 会把这一条的全部 take 毙掉', **shared))
    elif chars > high:
        findings.append(dict(level='warn', rule='over_char_target', limit=high,
                             fix=f'建议删到 ≤{high} 字（硬上限 {budget["hard_max"]} 字）',
                             why=f'{chars} 字 ≈ {seconds:g}s，超出 prompt 写的目标带 '
                                 f'{budget["band_seconds"][0]:g}–{budget["band_seconds"][1]:g}s', **shared))
    elif chars < low:
        findings.append(dict(level='warn', rule='under_char_budget', limit=low,
                             fix=f'建议加到 ≥{low} 字',
                             why=f'{chars} 字 ≈ {seconds:g}s，低于目标带下沿 '
                                 f'{budget["band_seconds"][0]:g}s', **shared))
    return findings


def _clean_text(value, *, allow_newline: bool, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f'{label} must be a string')
    text = value.strip()
    allowed = {'\n'} if allow_newline else set()
    if any((ord(c) < 32 and c not in allowed) or c == '\x7f' for c in text):
        raise ValueError(f'{label} contains control characters')
    return text


def check_subtitle(text: str) -> None:
    visible = text.replace('\n', '')
    if not visible:
        raise ValueError('empty subtitle')
    if len(visible) > SUBTITLE_MAX:
        raise ValueError(f'subtitle exceeds {SUBTITLE_MAX} characters ({len(visible)}): {visible[:20]}…')
    if text.count('\n') + 1 > SUBTITLE_MAX_LINES:
        raise ValueError(f'subtitle exceeds {SUBTITLE_MAX_LINES} lines')


ROUTE_ALIASES = {
    'hphigh': '0', 'hp_high': '0',
    'conditionexist': '1', 'condition_exist': '1', 'condition': '1',
    'changeskillflag': '3', 'change_skill_flag': '3', 'skill_flag': '3', 'skillflag': '3',
}


def switch_key(code: str) -> str:
    return code + '_voice_ready'


def _first(route: dict, *names):
    for name in names:
        if name in route and route[name] not in (None, ''):
            return str(route[name]).strip()
    raise ValueError('route lacks ' + '/'.join(names))


def normalize_route(route, code: str) -> list[str]:
    """返回 character c9–c16 八列。支持 kind 0=HpHigh(c13)、1=ConditionExist(c10/c11)、3=ChangeSkillFlag。

    kind 2（多球，会出编成缤带）、4（IsUnison，主位永不成立）与其他值一律拒绝。
    """
    key = switch_key(code)
    if isinstance(route, dict) and ('columns' in route or 'c9_16' in route):
        route = route.get('columns', route.get('c9_16'))
    if isinstance(route, (list, tuple)):
        cols = ['' if x is None else str(x).strip() for x in route]
    elif isinstance(route, dict):
        raw = str(route.get('kind', '')).strip()
        kind = raw if raw in ('0', '1', '3') else ROUTE_ALIASES.get(raw.lower().replace('-', '_'))
        if kind is None:
            raise ValueError(f'unsupported matched_skill_ready route kind: {raw!r}')
        cols = [kind, '', '', '', '', key, 'false', 'false']
        if kind == '0':
            cols[4] = _first(route, 'hp_threshold', 'threshold', 'c13')
        elif kind == '1':
            cols[1] = _first(route, 'condition_kind', 'c10')
            cols[2] = _first(route, 'condition_id', 'unique_id', 'c11')
    else:
        raise ValueError('missing matched_skill_ready route (matched 条在战斗里永远不会播)')
    if len(cols) != 8:
        raise ValueError('route must be exactly character columns 9..16')
    kind, c10, c11, c12, c13, c14, c15, c16 = cols
    if kind not in ('0', '1', '3'):
        raise ValueError(f'unsupported route kind {kind!r}; only 0/1/3 are native-safe')
    if c12 or c14 != key or (c15, c16) != ('false', 'false'):
        raise ValueError('route must target <code>_voice_ready with voice flags false')
    if kind == '0':
        try:
            threshold = float(c13)
        except ValueError:
            raise ValueError('HpHigh threshold must be numeric') from None
        if c10 or c11 or not 0 < threshold <= 1:
            raise ValueError('HpHigh route needs only c13 in (0, 1]')
    elif kind == '1':
        if not (c10.isdigit() and c11.isdigit()) or c13:
            raise ValueError('ConditionExist route needs numeric c10/c11 and empty c13')
    elif c10 or c11 or c13:
        raise ValueError('ChangeSkillFlag route carries no condition columns')
    return cols


# ---------------------------------------------------------------- design → 请求

def load_design_voice(path) -> dict:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    voice = data.get('voice') if isinstance(data, dict) else None
    if not isinstance(voice, dict):
        raise ValueError(f'design json lacks a voice object: {path}')
    return voice


def load_refs_index(path=REFS_INDEX) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def reference_defects(record: dict) -> list[str]:
    """一条参考音记录的闸门判据：区间外 / 电平测不出且没换尺 ⇒ 不许用。

    `range_ok=False` 与「整合响度是 -70 这个测不出的下限」都只在第一版里被打印成
    warning，plan/generate 照用 —— 于是 9 个 group 超区间、其中 5 个响度是假数、
    实际比其它参考音热 3～5 dB，全批 158 条请求就挂着它们出发。
    """
    defects = []
    if record.get('range_ok') is False:
        low, high = record.get('range_seconds') or (None, None)
        defects.append(f'cleaned duration {record.get("seconds")}s outside {low}-{high}s')
    method = record.get('loudness_method')
    lufs = record.get('lufs_i')
    unmeasurable = lufs is None or float(lufs) <= LOUDNESS_UNMEASURABLE_LUFS
    if unmeasurable and method != 'rms':
        defects.append(f'integrated loudness is unmeasurable (lufs_i={lufs}) and the record does '
                       f'not say it was RMS-normalised (loudness_method={method!r})')
    return defects


def check_reference_record(role: str, slot: str, name: str, label: str, record: dict) -> None:
    exempt = str(record.get('exempt_reason') or '').strip()
    defects = reference_defects(record)
    if not defects or exempt:
        return
    raise ValueError(
        f'{role}:{slot} → reference group {name!r} ({label}) is not fit to send: '
        + '; '.join(defects)
        + f'. Fix it in the role reference policy (recipe.reference_policy.per_role.{role}) — '
          f'swap in another official take from the same family and re-run `refs2`, or declare '
          f'`exemptions: {{"{name}": "<理由>"}}` there if this really is the only usable source.')


def group_references(role: str, slot: str, refs_index: dict) -> list[dict]:
    """v2 逐槽参考音：slot → group → [@音频1 (+@音频2)]，绝不跨 group。

    第一轮 11/12 角色的每一条请求都同时挂 battle+home 两条，0.6 秒的 PF 请求里
    有一半条件音频是 10–13 秒的家常独白 ⇒ 模型对齐长参考的节奏，短槽系统性拖长。

    区间/电平不合格的参考音在这里就报错（除非角色的参考音策略里显式豁免），
    不再是「只记一条 warning 然后照样发出去」。
    """
    entry = refs_index['roles'][role]
    groups = entry.get('groups')
    if not groups:
        raise ValueError(f'{role}: reference index has no per-slot groups; run refs with the v2 builder')
    mapping = entry.get('slot_to_group') or {}
    name = mapping.get(slot)
    if name is None:
        raise ValueError(f'{role}: no reference group mapped for {slot}')
    group = groups.get(name)
    if group is None:
        raise ValueError(f'{role}: reference group {name!r} missing from the index')
    check_reference_record(role, slot, name, 'primary', group)
    items = [dict(path=group['path'], sha256=group['sha256'])]
    second = group.get('second')
    if second:
        check_reference_record(role, slot, name, 'second', second)
        items.append(dict(path=second['path'], sha256=second['sha256']))
    return items


def resolve_references(role: str, spec, refs_index: dict | None = None, *, slot: str | None = None) -> list[dict]:
    """design 的 references → [{path, sha256}]，读文件核对哈希。

    spec：None/'refs'/'default' 取 refs.json（索引带 groups 且给了 slot 时按槽解析）；
    列表项可为 {path, sha256}、{kind}、'battle'/'home'。
    """
    def indexed():
        index = refs_index if refs_index is not None else load_refs_index()
        entries = index['roles'][role]['references']
        return {e['kind']: e for e in entries}, entries

    items = []
    if spec in (None, '', 'refs', 'default', 'groups') or spec == []:
        index = refs_index if refs_index is not None else load_refs_index()
        entry = index['roles'].get(role) or {}
        if slot is not None and (entry.get('groups') or 'references' not in entry):
            items = group_references(role, slot, index)
        else:
            items = [dict(path=e['path'], sha256=e['sha256']) for e in entry['references']]
    elif isinstance(spec, list):
        for item in spec:
            kind = item if isinstance(item, str) else item.get('kind') if isinstance(item, dict) else None
            if isinstance(item, dict) and 'path' in item:
                if not isinstance(item.get('sha256'), str):
                    raise ValueError('explicit reference requires sha256')
                items.append(dict(path=str(item['path']), sha256=item['sha256']))
            elif kind in ('battle', 'home'):
                entry = indexed()[0][kind]
                items.append(dict(path=entry['path'], sha256=entry['sha256']))
            else:
                raise ValueError(f'unsupported reference item: {item!r}')
    else:
        raise ValueError('references must be omitted, "refs" or a list')
    if not 1 <= len(items) <= 2:
        raise ValueError('expected one or two reference recordings')
    for item in items:
        path = Path(item['path'])
        if path.suffix.lower() not in ('.wav', '.mp3') or not path.is_file():
            raise ValueError(f'reference recording missing or unsupported: {path}')
        if sha(path.read_bytes()) != item['sha256']:
            raise ValueError('reference hash drift')
    return items


def request_lines(role: str, voice: dict, *, refs_index: dict | None = None,
                  allow_partial: bool = False, version: int | None = None,
                  strict_text: bool = True) -> list[dict]:
    """design voice → wf_art_voice_api 同构的逐条请求（按角色槽表顺序）。

    version=2 时走本轮配方：逐槽参考音、performance/tone 拆分、台词全角引号封边、wav 返回。

    `strict_text=False` 时台词硬规则的 error 不抛异常，只留在每条的 `findings` 里 ——
    只给 `plan` 用：它要把 12 份台词稿的问题**逐条列全**给改稿的人看，而不是撞上第一条就
    整个角色 plan 不出来。生成路径（`generate`）永远是 strict：错的稿子不许花钱。
    """
    if role not in ROLES:
        raise ValueError(f'unknown role {role!r}')
    info = ROLES[role]
    if version is None:
        version = int(voice.get('prompt_version') or 1)
    if version not in (1, 2):
        raise ValueError(f'unsupported prompt template version: {version!r}')
    persona = _clean_text(voice.get('persona'), allow_newline=False, label='persona')
    if not persona:
        raise ValueError('persona is required')
    slots = role_slots(role)
    shared_references = None if version == 2 else resolve_references(role, voice.get('references'), refs_index)
    persona_short, voice_tag = speaker_label(voice) if version == 2 else ('', '')
    raw_lines = voice.get('lines')
    if not isinstance(raw_lines, list) or not raw_lines:
        raise ValueError('voice.lines must be a non-empty list')
    output, seen, findings = [], set(), []
    for item in raw_lines:
        if not isinstance(item, dict):
            raise ValueError('voice line must be an object')
        slot = normalize_slot(item.get('slot'), slots)
        if slot in seen:
            raise ValueError(f'duplicate voice slot {slot}')
        seen.add(slot)
        ja = _clean_text(item.get('ja'), allow_newline=False, label=f'{slot}.ja')
        zh = _clean_text(item.get('zh'), allow_newline=True, label=f'{slot}.zh')
        if not ja or not zh:
            raise ValueError(f'{slot} requires ja and zh')
        if slot in SUBTITLE_SLOTS:
            check_subtitle(zh)
        design_direction = item.get('direction') or ''
        line = dict(role=role, slot=slot, code=info['code'], character_id=info['cid'],
                    family=family(slot), persona=persona,
                    direction=compose_direction(design_direction, slot),
                    design_direction=design_direction, ja=ja, zh=zh,
                    references=shared_references)
        if item.get('tts_text'):
            line['tts_text'] = _clean_text(item['tts_text'], allow_newline=False, label=f'{slot}.tts_text')
        if version == 2:
            spoken = expand_ruby(line.get('tts_text') or ja)
            quote_policy = str(item.get('quote_policy') or 'strip')
            forms = (expand_ruby(ja), spoken)
            performance, tone = compose_performance(item.get('direction'), slot,
                                                    quote_policy=quote_policy, spoken_forms=forms)
            explicit_tone = str(item.get('tone') or '')
            if explicit_tone and quote_policy != 'strip':
                explicit_tone = neutralize_quotes(explicit_tone, forms)
                if quote_policy == 'positional_inline':
                    explicit_tone = neutralize_inline(explicit_tone, forms)
            line.update(prompt_version=2, audio_format='wav', tts_text=spoken,
                        persona_short=persona_short, voice_tag=voice_tag,
                        tone=strip_display_quotes(explicit_tone or tone),
                        performance=performance, prompt_band=list(prompt_band(slot)),
                        references=resolve_references(role, voice.get('references'), refs_index, slot=slot))
            line['findings'] = check_ja_rules(slot, expand_ruby(ja), spoken,
                                              has_tts_text=bool(item.get('tts_text')))
            findings += [f for f in line['findings'] if f['level'] == 'error']
        output.append(line)
    if findings and strict_text:
        raise ValueError('voice lines break the hard text rules: ' +
                         '; '.join(f'{f["slot"]}:{f["rule"]}' + (f'({f["detail"]})' if f.get('detail') else '')
                                   for f in findings))
    missing = [slot for slot in slots if slot not in seen]
    if missing and not allow_partial:
        raise ValueError(f'incomplete {len(slots)}-slot voice set; missing ' + ', '.join(missing))
    output.sort(key=lambda x: slot_order(x['slot']))
    return output


def plan_role(role: str, design_path=None, *, refs_index=None, allow_partial=False,
              version: int | None = None, strict_text: bool = True) -> dict:
    path = Path(design_path) if design_path else DESIGN_DIR / f'{role}.json'
    voice = load_design_voice(path)
    lines = request_lines(role, voice, refs_index=refs_index, allow_partial=allow_partial,
                          version=version, strict_text=strict_text)
    route = voice.get('route')
    findings = [f for line in lines for f in line.get('findings', [])]
    warnings = [f for f in findings if f['level'] != 'error']
    return dict(role=role, design=str(path), lines=lines, slots=list(role_slots(role)),
                prompt_version=lines[0].get('prompt_version', 1) if lines else (version or 1),
                text_warnings=warnings, text_errors=[f for f in findings if f['level'] == 'error'],
                route=normalize_route(route, ROLES[role]['code']) if route is not None else None)


def request_fingerprint(line: dict) -> str:
    """与 wf_art_voice_api.generate 的 request_fingerprint 同算法。"""
    return api.sha(json.dumps(api.payload(line), ensure_ascii=False, sort_keys=True).encode())


# ---------------------------------------------------------------- 生成（并发 ≤2、重试 ≤1、续跑）

def classify_failure(meta: dict) -> str:
    status = meta.get('http_status')
    code = str(meta.get('api_code') or '')
    message = str(meta.get('api_message') or '').lower()
    # 45001127 = `tts_create_ref` 审核拒了**参考音**，不是台词。第一轮它靠 message 里有 audit
    # 落进 needs_rewrite，于是队列指引操作者去改台词 —— remedy 指错对象（charlene 22/22 全中）。
    if status == 400 and (code in REFERENCE_AUDIT_CODES or 'tts_create_ref' in message):
        return 'needs_new_reference'
    if status == 400 and (code in AUDIT_CODES or 'audit' in message):
        return 'needs_rewrite'
    if status is None or status == 429 or status >= 500 or 200 <= status < 300:
        return 'retryable'
    return 'fatal'


# ---------------------------------------------------------------- 跨进程配额锁

def _lock_handle(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+b')
    if handle.tell() == 0:
        handle.write(b'0')
        handle.flush()
    handle.seek(0)
    return handle


def _try_lock(handle) -> bool:
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.lockf(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB, 1)
    except OSError:
        return False
    return True


def _unlock(handle) -> None:
    handle.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.lockf(handle.fileno(), fcntl.LOCK_UN, 1)
    finally:
        handle.close()


@contextmanager
def exclusive_lock(name: str, *, lock_dir=None, timeout: float = 0.0, sleep=time.sleep):
    """同名锁只允许一个持有者（跨进程）。timeout=0 表示抢不到立刻报错。

    用途：同一角色同时被两个进程生成 = 重复计费（第一轮发生过）。
    """
    path = Path(lock_dir or LOCK_DIR) / f'{name}.lock'
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        handle = _lock_handle(path)
        if _try_lock(handle):
            try:
                yield path
            finally:
                _unlock(handle)
            return
        handle.close()
        if time.monotonic() >= deadline:
            raise RuntimeError(f'another process holds the voice lock {name!r} ({path})')
        sleep(0.5)


_QUOTA_HELD: set[tuple[str, int]] = set()
_QUOTA_GUARD = threading.Lock()


@contextmanager
def quota_slot(*, slots: int = MAX_WORKERS, lock_dir=None, sleep=time.sleep, timeout: float = 900.0):
    """全局 HTTP 配额槽：所有本机语音生成进程共用 `slots` 个并发位。

    每个在途请求占一个位，`slots` 与 `--workers` 同语义 —— 一个进程自己跑满 2 个 worker
    就占满全局配额，第二个进程只能等，不会两边一起打接口把配额（和钱）翻倍。

    进程内还有一层 `_QUOTA_HELD`：POSIX 的 `fcntl.lockf` 是按进程记账的，同一进程的
    第二个线程再锁同一个字节会「成功」，光靠文件锁数不准并发位。
    """
    deadline = time.monotonic() + timeout
    while True:
        for index in range(slots):
            path = Path(lock_dir or LOCK_DIR) / f'slot-{index}.lock'
            key = (str(path), index)
            with _QUOTA_GUARD:
                if key in _QUOTA_HELD:
                    continue
                _QUOTA_HELD.add(key)
            try:
                handle = _lock_handle(path)
            except OSError:
                with _QUOTA_GUARD:           # 开不了锁文件也要把占位放回去，否则这一位永久漏掉
                    _QUOTA_HELD.discard(key)
                raise
            if _try_lock(handle):
                try:
                    yield index
                finally:
                    _unlock(handle)
                    with _QUOTA_GUARD:
                        _QUOTA_HELD.discard(key)
                return
            handle.close()
            with _QUOTA_GUARD:
                _QUOTA_HELD.discard(key)
        if time.monotonic() >= deadline:
            raise RuntimeError('no free Seed Audio quota slot')
        sleep(1.0)


def _attempt_records(base: Path, slot: str) -> list[tuple[Path, dict]]:
    folder = base / 'attempts' / slot
    if not folder.is_dir():
        return []
    return [(p, json.loads(p.read_bytes())) for p in sorted(folder.glob('*.json'))]


def _archive_attempt(receipt: Path, base: Path, slot: str) -> Path:
    folder = base / 'attempts' / slot
    folder.mkdir(parents=True, exist_ok=True)
    index = 1 + max((int(p.stem) for p in folder.glob('*.json') if p.stem.isdigit()), default=0)
    target = folder / f'{index:03d}.json'
    receipt.replace(target)
    return target


def _outcome(line: dict, status: str, **extra) -> dict:
    return dict(role=line['role'], slot=line['slot'], status=status, **extra)


def generate_line(line: dict, output, key: str, *, opener=urllib.request.urlopen,
                  sleep=time.sleep, max_retries: int = MAX_AUTO_RETRIES) -> dict:
    """单条生成；失败回执归档到 attempts/<slot>/NNN.json，按指纹累计重试预算。

    审核失败（400/45001125）不重试，返回 needs_rewrite；改写台词后指纹变化自动放行。
    已有不同指纹的成品会返回 conflict（请换 --run 目录重录）。
    """
    if max_retries not in (0, 1):
        raise ValueError('automatic retries are capped at one')
    role, slot = line['role'], line['slot']
    if role not in ROLES or slot not in role_slots(role):
        raise ValueError('unsafe or unknown recording path')
    base = Path(output) / role
    target = base / 'raw' / (slot + '.' + api.audio_format(line))
    receipt = base / 'receipts' / (slot + '.json')
    fingerprint = request_fingerprint(line)
    if receipt.is_file() and not target.exists():
        saved = json.loads(receipt.read_bytes())
        if saved.get('status') != 'failed':
            return _outcome(line, 'conflict', error='receipt without audio is not a failed attempt')
        _archive_attempt(receipt, base, slot)
    prior = [meta for _path, meta in _attempt_records(base, slot)
             if meta.get('request_fingerprint') == fingerprint]
    last = {k: prior[-1].get(k) for k in ('http_status', 'api_code', 'api_message', 'error')} if prior else {}
    blocked = next((classify_failure(m) for m in prior
                    if classify_failure(m) in ('needs_rewrite', 'needs_new_reference')), None)
    if blocked:
        return _outcome(line, blocked, attempts=len(prior), **last)
    budget = 1 + max_retries - len(prior)
    if budget <= 0:
        return _outcome(line, 'retry_exhausted', attempts=len(prior), **last)
    result = None
    for attempt in range(budget):
        try:
            result = api.generate(line, output, key, opener=opener)
        except ValueError as exc:
            return _outcome(line, 'conflict', error=str(exc).replace(key, '[REDACTED]') if key else str(exc))
        if result['status'] == 'cached':
            return result
        result['attempts'] = len(prior) + attempt + 1
        if result['status'] == 'generated':
            return result
        meta = json.loads(receipt.read_bytes())
        _archive_attempt(receipt, base, slot)
        kind = classify_failure(meta)
        if kind in ('needs_rewrite', 'needs_new_reference'):
            return dict(result, status=kind)
        if kind == 'fatal':
            return result
        if attempt + 1 < budget:
            sleep(RETRY_BACKOFF.get(meta.get('http_status'), DEFAULT_BACKOFF))
    return result


REMEDY = {
    'needs_rewrite': '改写 ja（避开审核敏感措辞）后重跑；台词变化即新指纹，自动放行',
    'needs_new_reference': '换参考音（45001127 = tts_create_ref 拒的是参考音，不是台词）：'
                           '取同 group 第二选或重新清洗后重跑；参考音变化即新指纹，自动放行',
}


def rewrite_queue(lines: list[dict], output) -> list[dict]:
    """当前指纹下仍被卡住的条目：needs_rewrite（改台词）与 needs_new_reference（换参考音）。"""
    queue = []
    for line in lines:
        base = Path(output) / line['role']
        fingerprint = request_fingerprint(line)
        hits = [(p, m, classify_failure(m)) for p, m in _attempt_records(base, line['slot'])
                if m.get('request_fingerprint') == fingerprint
                and classify_failure(m) in REMEDY]
        if hits:
            path, meta, kind = hits[-1]
            queue.append(dict(role=line['role'], slot=line['slot'], ja=line['ja'], zh=line['zh'],
                              blocked_by=kind,
                              design_direction=line.get('design_direction', ''),
                              references=[r['path'] for r in line.get('references') or []],
                              http_status=meta.get('http_status'), api_code=meta.get('api_code'),
                              api_message=meta.get('api_message'), receipt=str(path),
                              action=REMEDY[kind]))
    return queue


def scrub_secret(folder, key: str) -> list[str]:
    """兜底：输出目录里任何 JSON 出现密钥原文即替换并返回命中路径。"""
    hits = []
    if not key or not Path(folder).is_dir():
        return hits
    for path in Path(folder).rglob('*.json'):
        text = path.read_text(encoding='utf-8', errors='ignore')
        if key in text:
            path.write_text(text.replace(key, '[REDACTED]'), encoding='utf-8')
            hits.append(str(path))
    return hits


def run_generation(lines: list[dict], output, key: str, *, workers: int = MAX_WORKERS,
                   opener=urllib.request.urlopen, sleep=time.sleep,
                   max_retries: int = MAX_AUTO_RETRIES, on_result=None,
                   lock_dir=None, role_locks: bool = True, lock_timeout: float = 0.0,
                   quota_slots: int = MAX_WORKERS, quota_timeout: float = 900.0) -> dict:
    """并发 ≤2、重试 ≤1、按指纹续跑。

    两层跨进程保护，默认都开（防重复计费不能靠操作者记得加参数）：

    * `role_locks=True`：同一角色只许一个进程在生成（第一轮发生过重复计费）。
    * `quota_slots`：全局并发生成槽，与 `--workers` 同语义 —— 每个在途请求占一位，
      本机所有语音进程共用这 `quota_slots` 位；`quota_slots=0` 关掉（只给单测用）。
    """
    if workers not in range(1, MAX_WORKERS + 1):
        raise ValueError('Seed Audio concurrency is capped at 2')
    output = Path(output)
    started = time.monotonic()
    results = []

    def one(line):
        if not quota_slots:
            return generate_line(line, output, key, opener=opener, sleep=sleep, max_retries=max_retries)
        with quota_slot(slots=quota_slots, lock_dir=lock_dir, sleep=sleep, timeout=quota_timeout):
            return generate_line(line, output, key, opener=opener, sleep=sleep, max_retries=max_retries)

    with ExitStack() as stack:
        held = []
        if role_locks:
            for role in sorted({line['role'] for line in lines}):
                stack.enter_context(exclusive_lock(f'role-{role}', lock_dir=lock_dir,
                                                   timeout=lock_timeout, sleep=sleep))
                held.append(role)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(one, line) for line in lines]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                if on_result:
                    on_result(result)
    results.sort(key=lambda r: (r['role'], slot_order(r['slot'])))
    queue_path = output / 'rewrite_queue.json'
    selected = {(line['role'], line['slot']) for line in lines}
    kept = [item for item in (json.loads(queue_path.read_bytes()) if queue_path.is_file() else [])
            if (item['role'], item['slot']) not in selected]     # --only 子集不清掉其他待改项
    queue = sorted(kept + rewrite_queue(lines, output), key=lambda x: (x['role'], slot_order(x['slot'])))
    _write_json(queue_path, queue)
    counts = {}
    for result in results:
        counts[result['status']] = counts.get(result['status'], 0) + 1
    summary = dict(finished_at=_now(), requests=len(lines), workers=workers, max_auto_retries=max_retries,
                   elapsed_seconds=round(time.monotonic() - started, 2), counts=counts,
                   role_locks=held if role_locks else [], quota_slots=quota_slots,
                   rewrite_queue=len(queue),
                   needs_new_reference=[f'{x["role"]}:{x["slot"]}' for x in queue
                                        if x.get('blocked_by') == 'needs_new_reference'],
                   results=results)
    _write_json(output / 'generation-summary.json', summary)
    leaked = scrub_secret(output, key)
    if leaked:
        raise RuntimeError(f'credential text was found and redacted in {len(leaked)} file(s)')
    return summary


# ---------------------------------------------------------------- 后处理（-14 LUFS）

def _ffmpeg(ffmpeg, args, **kwargs):
    result = subprocess.run([str(ffmpeg), '-hide_banner', '-nostats', *args], capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace')[-2000:])
    return result


def _mono_filters(channels: int) -> list[str]:
    if channels == 1:
        return []
    if channels == 2:
        return ['pan=mono|c0=0.5*c0+0.5*c1']
    raise ValueError(f'unreviewed source channel layout: {channels}')


def _trim_filters(trim) -> list[str]:
    if not trim:
        return []
    start, end = trim
    return [f'atrim=start={start:.4f}:end={end:.4f}', 'asetpts=PTS-STARTPTS']


def encode_voice(source: Path, output: Path, *, ffmpeg, channels: int, gain_db: float = 0.0,
                 limiter_ceiling_db: float | None = None, trim=None, loudnorm: str | None = None) -> dict:
    filters = _trim_filters(trim) + _mono_filters(channels)
    if loudnorm:
        filters += [loudnorm]
    if limiter_ceiling_db is None:
        filters += ['aresample=44100', f'volume={gain_db:.8f}dB']
    else:
        limit = 10 ** (limiter_ceiling_db / 20)
        filters += ['aresample=176400', f'volume={gain_db:.8f}dB',
                    f'alimiter=limit={limit:.12f}:attack=5:release=80:level=disabled:latency=enabled',
                    'aresample=44100']
    output.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg(ffmpeg, ['-y', '-v', 'error', '-i', str(source), '-map', '0:a:0', '-map_metadata', '-1', '-vn',
                     '-af', ','.join(filters), '-c:a', 'libmp3lame', '-compression_level', '0',
                     '-ar', '44100', '-ac', '1', '-b:a', '96k', '-minrate', '96k', '-maxrate', '96k',
                     '-write_xing', '1', '-id3v2_version', '0', str(output)])
    return measure(output, Path(ffmpeg))


def oversampled_peak_db(source: Path, *, ffmpeg, channels: int, trim=None) -> float:
    filters = ','.join(_trim_filters(trim) + _mono_filters(channels) + ['aresample=176400'])
    raw = _ffmpeg(ffmpeg, ['-v', 'error', '-i', str(source), '-map', '0:a:0', '-af', filters,
                           '-ac', '1', '-f', 'f32le', 'pipe:1']).stdout
    values = np.frombuffer(raw, dtype='<f4')
    if not len(values):
        raise ValueError('empty decoded audio')
    return 20 * math.log10(max(float(np.max(np.abs(values))), 1e-12))


def decoded_pcm(source: Path, *, ffmpeg, trim=None, rate: int = 44100) -> np.ndarray:
    """按 44.1k 单声道解码（可带 atrim），用于样本级对照。"""
    args = ['-v', 'error', '-i', str(source), '-map', '0:a:0']
    filters = _trim_filters(trim)
    if filters:
        args += ['-af', ','.join(filters)]
    raw = _ffmpeg(ffmpeg, args + ['-f', 'f32le', '-ar', str(rate), '-ac', '1', 'pipe:1']).stdout
    return np.frombuffer(raw, dtype='<f4')


def edge_bounds(source: Path, *, ffmpeg, head: float = TRIM_HEAD_SECONDS, tail: float = TRIM_TAIL_SECONDS,
                threshold_dbfs: float = TRIM_ACTIVE_DBFS) -> tuple[float, float]:
    """10 ms 块 RMS 判活，头留 `head`、尾留 `tail` 的边缘裁剪区间。

    第一轮不裁静音（`SAMPLE_DELTA_LIMIT=128` + no_trim），短战斗槽空气占比
    p50=20% / p90=44% / 最大 81%（kyle power_flip_0 句首静音 1.28s）全部原样进了包。
    同仓已验证先例：`_codex_voice_pipeline_20260910/prepare_delivery.py:edge_trim()`。
    """
    rate = 48000
    block = rate // 100
    samples = decoded_pcm(Path(source), ffmpeg=ffmpeg, rate=rate).astype(np.float64)
    count = len(samples) // block
    if count < 1:
        raise ValueError('audio is shorter than one analysis block')
    rms = np.sqrt(np.mean(samples[:count * block].reshape(-1, block) ** 2, axis=1))
    active = np.flatnonzero(rms > 10 ** (threshold_dbfs / 20))
    if not len(active):
        raise ValueError('silent generated audio: nothing above the activity threshold')
    duration = len(samples) / rate
    start = max(0.0, float(active[0]) * block / rate - head)
    end = min(duration, float(active[-1] + 1) * block / rate + tail)
    if end - start < 0.05:
        raise ValueError('edge trim would leave less than 50 ms of audio')
    return round(start, 4), round(end, 4)


def loudnorm_measure(source: Path, *, ffmpeg, target_lufs: float, trim=None, channels: int = 1) -> dict:
    """第一遍：测量 loudnorm 需要的 measured_* 四个量。"""
    filters = ','.join(_trim_filters(trim) + _mono_filters(channels) +
                       [f'loudnorm=I={target_lufs}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}:print_format=json'])
    text = _ffmpeg(ffmpeg, ['-i', str(source), '-map', '0:a:0', '-af', filters,
                            '-f', 'null', os.devnull]).stderr.decode('utf-8', errors='replace')
    blocks = re.findall(r'\{[^{}]+\}', text)
    if not blocks:
        raise ValueError('loudnorm did not report a measurement')
    return json.loads(blocks[-1])


def loudnorm_filter(measured: dict, *, target_lufs: float) -> str:
    return (f'loudnorm=I={target_lufs}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}:'
            f'measured_I={measured["input_i"]}:measured_TP={measured["input_tp"]}:'
            f'measured_LRA={measured["input_lra"]}:measured_thresh={measured["input_thresh"]}:'
            f'offset={measured["target_offset"]}:linear=true')


def duration_findings(code: str, slot: str, seconds: float) -> list[dict]:
    fam = family(slot)
    _n, low, p50, p90, _p95, _p99, high = gate.OFFICIAL_DURATION[fam]
    detail = dict(character=code, slot=slot, family=fam, seconds=round(seconds, 3))
    if seconds > high:
        return [dict(level='error', rule='over_official_max', limit=high, **detail)]
    if seconds > p90:
        return [dict(level='warn', rule='over_official_p90', limit=p90, official_max=high, **detail)]
    if seconds < low:
        return [dict(level='warn', rule='below_official_min', limit=low, p50=p50, **detail)]
    return []


def density_render(source: Path, target: Path, *, ffmpeg, channels: int, stage: dict,
                   peak_dbfs: float,
                   normalize_peak_dbfs: float = DENSITY_NORMALIZE_PEAK_DBFS) -> None:
    """把源渲染成「压缩过的同长度单声道 WAV」，供后面原封不动地走同一条链。

    两步：纯增益把峰值归到 `normalize_peak_dbfs`（增益不改变峰均比，纯粹是让档位阈值
    有确定含义），再过一道 acompressor。不变速、不裁剪、不拼接，样本数与源逐样本对应，
    所以 `master_voice` 的 `sample_delta` 仍然拿**原始源**做对照，这一刀照样抓得住。
    输出 f32 WAV：中间态不会削波，削波判定仍在最终 MP3 上做。
    """
    filters = _mono_filters(channels) + [f'volume={normalize_peak_dbfs - peak_dbfs:.8f}dB',
                                         density_filter(stage, normalize_peak_dbfs)]
    target.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg(ffmpeg, ['-y', '-v', 'error', '-i', str(source), '-map', '0:a:0', '-map_metadata', '-1',
                     '-vn', '-af', ','.join(filters), '-c:a', 'pcm_f32le', '-ac', '1', str(target)])


def master_voice(source, target, *, slot: str, code: str, ffmpeg, ffprobe,
                 target_lufs: float = TARGET_LUFS, peak_ceiling: float = PEAK_CEILING,
                 limiter_ceiling: float = LIMITER_CEILING,
                 max_limiter_reduction_db: float = MAX_LIMITER_REDUCTION_DB,
                 mode: str = 'fixed_gain', trim: bool = False, density: bool = False,
                 slots=None) -> tuple[bytes, dict]:
    """把整条表演做到 -14 LUFS；真峰超限时用有界 lookahead 限幅。

    `mode='fixed_gain'`（默认，旧行为）= 整条定增益 + 限幅。
    `mode='two_pass'` = 两遍 loudnorm（measured_* + linear=true），限幅只当安全网。
    `trim=True` 时按 RMS 判活做边缘裁剪（头 100ms / 尾 150ms），不变速、不拼接。
    `density=True`（只在 two_pass 下生效）= 先按现行流程做；成品仍低于合格带下限时，
    逐档加一道温和压缩再走同一流程，够了就停。限幅在密度级之后仍然只是安全网。
    返回 (存储态字节, QC 报告)；target 写标准态 MP3。时长超官方族最大值不抛错，写入 findings。
    """
    source, target = Path(source), Path(target)
    if slot not in (SLOTS if slots is None else tuple(slots)):
        raise ValueError('unknown voice slot')
    if mode not in ('fixed_gain', 'two_pass'):
        raise ValueError(f'unsupported mastering mode: {mode!r}')
    source_raw = source.read_bytes()
    info = metadata(source, Path(ffprobe))
    channels = int(info['streams'][0]['channels'])
    _mono_filters(channels)
    temporary = target.with_name(target.stem + '.tmp.mp3')
    dense_path = target.with_name(target.stem + '.dense.wav')
    bounds = edge_bounds(source, ffmpeg=ffmpeg) if trim else None
    if mode == 'two_pass':
        max_limiter_reduction_db = limiter_bound(mode, max_limiter_reduction_db)
    use_density = bool(density) and mode == 'two_pass'
    source_loud = (loudnorm_measure(source, ffmpeg=ffmpeg, target_lufs=target_lufs,
                                    trim=bounds, channels=channels)
                   if mode == 'two_pass' else None)

    def render(stage):
        """跑一遍完整的响度定型。`stage is None` = 原样源（与打密度级之前逐字相同）。"""
        if stage is None:
            work, work_channels, loud = source, channels, source_loud
        else:
            density_render(source, dense_path, ffmpeg=ffmpeg, channels=channels, stage=stage,
                           peak_dbfs=base_peak)
            work, work_channels = dense_path, 1
            loud = loudnorm_measure(work, ffmpeg=ffmpeg, target_lufs=target_lufs,
                                    trim=bounds, channels=work_channels)
        normalize = loudnorm_filter(loud, target_lufs=target_lufs) if mode == 'two_pass' else None
        baseline = encode_voice(work, temporary, ffmpeg=ffmpeg, channels=work_channels,
                                trim=bounds, loudnorm=normalize)
        if baseline['lufs_i'] <= -69.0:
            raise ValueError('source too short or silent for integrated loudness')
        pre_peak = oversampled_peak_db(work, ffmpeg=ffmpeg, channels=work_channels, trim=bounds)
        source_peak = pre_peak
        if normalize:
            # 两遍 loudnorm 已经把电平定死；后面的定增益段只收残差，所以峰值要量归一之后的。
            source_peak = oversampled_peak_db(temporary, ffmpeg=ffmpeg, channels=1)
        desired = target_lufs - baseline['lufs_i']
        if baseline['true_peak_dbtp'] + desired <= peak_ceiling:
            gain, ceiling = desired, None
        else:
            ceiling = limiter_ceiling
            gain = min(desired, ceiling - source_peak + max_limiter_reduction_db)
        attempts = []
        for _ in range(6):
            measured = encode_voice(work, temporary, ffmpeg=ffmpeg, channels=work_channels,
                                    gain_db=gain, limiter_ceiling_db=ceiling,
                                    trim=bounds, loudnorm=normalize)
            attempts.append(dict(gain_db=gain, limiter_ceiling_dbfs=ceiling, **measured))
            if measured['true_peak_dbtp'] <= peak_ceiling:
                break
            # MP3 编码后的真峰会越过限幅天花板：先压天花板保住响度，限幅量触到上界才降增益。
            adjustment = peak_ceiling - 0.1 - measured['true_peak_dbtp']
            if ceiling is None:
                ceiling = min(limiter_ceiling, source_peak + gain + adjustment)
            else:
                ceiling += adjustment
            excess = source_peak + gain - ceiling - max_limiter_reduction_db
            if excess > 0:
                gain -= excess
        else:
            raise ValueError('final MP3 true peak did not reach the ceiling')
        reduction = 0.0 if ceiling is None else max(0.0, source_peak + gain - ceiling)
        if reduction > max_limiter_reduction_db + 1e-6:
            raise ValueError('limiter reduction exceeds the approved bound')
        return dict(stage=stage, loud=loud, normalize=normalize, baseline=baseline,
                    pre_peak=pre_peak, source_peak=source_peak, desired=desired, gain=gain,
                    ceiling=ceiling, attempts=attempts, reduction=reduction, final=attempts[-1],
                    standard=temporary.read_bytes(),
                    mastered=amplitude(pcm(temporary, Path(ffmpeg))))

    def crest(peak_dbfs, loud) -> dict:
        lufs = None if loud is None else float(loud['input_i'])
        return dict(lufs_i=lufs, peak_dbfs=round(peak_dbfs, 3),
                    crest_db=None if lufs is None else round(peak_dbfs - lufs, 3))

    try:
        results = [render(None)]
        base_peak = results[0]['pre_peak']
        if use_density:
            for stage in DENSITY_STAGES:
                if loudness_verdict(results[-1]['final']['lufs_i']) != 'under_target':
                    break
                try:
                    results.append(render(stage))
                except (ValueError, RuntimeError):
                    # 密度级是加法：某一档收不了口就停在上一档，不能把本来能出的条目拖成失败。
                    break
        # 带内的永远优先；都不在带内时取最接近目标的那一遍（= 压得最实的那一档）。
        chosen = max(results, key=lambda r: (loudness_verdict(r['final']['lufs_i']) == 'ok',
                                             -abs(r['final']['lufs_i'] - target_lufs)))
        standard = chosen['standard']
        stored = wf_assets.mp3_encode(standard)
        if wf_assets.mp3_decode(stored) != standard:
            raise ValueError('native MP3 storage roundtrip failed')
        codec = gate.probe(stored)
        container = [asdict(x) for x in gate.check_container(gate.VoiceFile(code, slot, stored), codec)]
        if container or not codec['xing'] or codec['tail'] != 0:
            raise ValueError(f'native audio container validation failed: {container}')
        before, after = amplitude(pcm(source, Path(ffmpeg))), chosen['mastered']
        # 裁边时与「同样裁过的源」逐样本对照：允许的只有这一刀，变速/拼接照样会被抓住。
        # 密度级是逐样本增益，不改样本数，所以对照的仍然是**原始源**。
        reference = before if bounds is None else amplitude(decoded_pcm(source, ffmpeg=ffmpeg, trim=bounds))
        delta = after['samples'] - reference['samples']
        if abs(delta) > SAMPLE_DELTA_LIMIT:
            raise ValueError(f'mastering changed performance length by {delta} samples')
        if after['clipped_fraction'] > 0 or after['peak'] >= 0.999:
            raise ValueError('mastered performance clips')
        final = chosen['final']
        loudness = loudness_verdict(final['lufs_i'])
        fam = family(slot)
        _n, low, p50, p90, _p95, _p99, high = gate.OFFICIAL_DURATION[fam]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(standard)
    finally:
        for scratch in (temporary, dense_path):
            if scratch.exists():
                scratch.unlink()
    density_report = None
    if use_density:
        stage = chosen['stage']
        density_report = dict(
            enabled=True, applied=stage is not None,
            stage=None if stage is None else stage['name'],
            settings=None if stage is None else dict(stage),
            filter=None if stage is None else density_filter(stage),
            normalize_peak_dbfs=DENSITY_NORMALIZE_PEAK_DBFS,
            ladder=[s['name'] for s in DENSITY_STAGES],
            stages_tried=[None if r['stage'] is None else r['stage']['name'] for r in results],
            before=crest(results[0]['pre_peak'], results[0]['loud']),
            after=crest(chosen['pre_peak'], chosen['loud']),
            mastered_lufs_by_stage=[[None if r['stage'] is None else r['stage']['name'],
                                     r['final']['lufs_i']] for r in results])
    from wf_voice_selection_timing import acoustic_timing
    delivery_timing = acoustic_timing(pcm(target, Path(ffmpeg)))
    return stored, dict(
        slot=slot, code=code, family=fam,
        params=master_params(mode=mode, trim=bool(bounds), density=use_density,
                             max_limiter_reduction_db=max_limiter_reduction_db),
        source=str(source), source_sha256=sha(source_raw), source_metadata=info,
        standard=str(target), standard_sha256=sha(standard), storage_sha256=sha(stored),
        storage_roundtrip_equal=True, codec=codec, seconds=codec['duration'],
        official_seconds=dict(min=low, p50=p50, p90=p90, max=high),
        baseline_encoded=chosen['baseline'], source_oversampled_peak_dbfs=chosen['source_peak'],
        raw_lufs_i=float(source_loud['input_i']) if source_loud else chosen['baseline']['lufs_i'],
        desired_gain_db=chosen['desired'], gain_db=chosen['gain'],
        limiter_ceiling_dbfs=chosen['ceiling'],
        limiter_reduction_bound_db=chosen['reduction'], attempts=chosen['attempts'], final=final,
        loudness_status=loudness, loudness_band=list(MASTER_LOUDNESS_BAND), density=density_report,
        source_pcm=before, mastered_pcm=after, delivery_timing=delivery_timing,
        sample_delta=delta, sample_delta_limit=SAMPLE_DELTA_LIMIT,
        findings=duration_findings(code, slot, codec['duration']),
        mastering_mode=mode, loudnorm=chosen['normalize'],
        trim=None if bounds is None else dict(start_seconds=bounds[0], end_seconds=bounds[1],
                                              removed_seconds=round(before['seconds'] - (bounds[1] - bounds[0]), 3),
                                              head_pad=TRIM_HEAD_SECONDS, tail_pad=TRIM_TAIL_SECONDS,
                                              threshold_dbfs=TRIM_ACTIVE_DBFS),
        no_trim_no_speed_no_concatenation=bounds is None,
        no_speed_no_concatenation=True)


def master_policy(slot: str, version: int) -> dict:
    """按槽的后处理策略：v1 保持定增益、不裁剪；v2 两遍 loudnorm + 战斗槽边缘裁剪 + 密度级。"""
    if version < 2:
        return dict(mode='fixed_gain', trim=False)
    return dict(mode='two_pass', trim=family(slot) in TRIM_FAMILIES, density=True)


def process_run(lines: list[dict], run_dir, *, ffmpeg, ffprobe, version: int | None = None,
                remaster: bool = False) -> dict:
    """对已生成且回执校验通过的条目做后处理；qc 已存在且哈希一致即跳过（续跑）。

    `remaster=True`（CLI 的 `--remaster`）= 允许用**新策略**覆盖旧的 qc/standard。
    不给这个开关时策略变了仍然抛 QC drift —— 默认绝不悄悄盖掉旧产物。
    两种情况都只读 raw 与 receipts，一个字节不改，也不会触发任何重新生成。
    """
    run_dir = Path(run_dir)
    items = []
    for line in lines:
        role, slot = line['role'], line['slot']
        mode = version if version is not None else int(line.get('prompt_version') or 1)
        base = run_dir / role
        source = base / 'raw' / (slot + '.' + api.audio_format(line))
        receipt = base / 'receipts' / (slot + '.json')
        if not (source.is_file() and receipt.is_file()):
            items.append(dict(role=role, slot=slot, status='missing'))
            continue
        generated = json.loads(receipt.read_bytes())
        source_sha = sha(source.read_bytes())
        if generated.get('status') != 'generated' or generated.get('sha256') != source_sha:
            raise ValueError(f'unverified source recording: {role}:{slot}')
        if generated.get('request_fingerprint') != request_fingerprint(line):
            items.append(dict(role=role, slot=slot, status='stale_plan',
                              error='design changed after generation; regenerate in a new run'))
            continue
        policy = master_policy(slot, mode)
        # 期望参数与 master_voice 写进报告的那份必须逐字相同（限幅上界的钳位在
        # `limiter_bound` 一处，两边都走它），否则第二遍 process 会假报 QC 漂移。
        expected = master_params(**policy) if mode >= 2 else MASTER_PARAMS
        target, qc = base / 'standard' / (slot + '.mp3'), base / 'qc' / (slot + '.json')
        report, status = None, None
        if qc.is_file() and target.is_file():
            cached = json.loads(qc.read_bytes())
            if (cached.get('source_sha256') == source_sha
                    and cached.get('standard_sha256') == sha(target.read_bytes())
                    and cached.get('params') == expected):
                report, status = cached, 'cached'
            elif not remaster:
                raise ValueError(f'QC drift for {role}:{slot}; use a new run directory')
            else:
                # 旧 take 的 qc/standard 是旧策略的产物；只有显式 --remaster 才许重做。
                status = 'remastered'
        if report is None:
            try:
                _stored, report = master_voice(source, target, slot=slot, code=line['code'],
                                               ffmpeg=ffmpeg, ffprobe=ffprobe,
                                               slots=role_slots(role), **policy)
            except (ValueError, RuntimeError) as exc:
                items.append(dict(role=role, slot=slot, status='rejected', error=str(exc)[:500]))
                continue
            _write_json(qc, report)
            status = status or 'mastered'
        items.append(dict(role=role, slot=slot, status=status, seconds=round(report['seconds'], 3),
                          lufs_i=report['final']['lufs_i'], true_peak_dbtp=report['final']['true_peak_dbtp'],
                          limiter=report['limiter_ceiling_dbfs'] is not None,
                          trimmed=bool(report.get('trim')),
                          density=((report.get('density') or {}).get('stage')),
                          loudness_status=report['loudness_status'], findings=report['findings']))
    over_max = [x for x in items if any(f['level'] == 'error' for f in x.get('findings', []))]
    retake = [x for x in items if x['status'] in ('rejected', 'stale_plan') or x in over_max
              or x.get('loudness_status') not in (None, 'ok')]
    # 没显式传 --prompt-version 时，实际生效的版本来自每条 line；摘要里的 params 必须跟着它走，
    # 否则 lines 自带 v2（逐条两遍 loudnorm）时摘要会写成 v1 的 MASTER_PARAMS，与逐条报告不符。
    effective = version if version is not None else max(
        (int(line.get('prompt_version') or 1) for line in lines), default=1)
    summary = dict(finished_at=_now(), prompt_version=version, effective_prompt_version=effective,
                   params=MASTER_PARAMS if effective < 2 else 'per-slot; see each qc report',
                   items=items,
                   over_official_max=[f'{x["role"]}:{x["slot"]}' for x in over_max],
                   over_official_p90=[f'{x["role"]}:{x["slot"]}' for x in items
                                      if any(f['rule'] == 'over_official_p90' for f in x.get('findings', []))],
                   retake_candidates=[f'{x["role"]}:{x["slot"]}' for x in retake])
    _write_json(run_dir / 'qc-summary.json', summary)
    return summary


# ---------------------------------------------------------------- 装包

def claim(logical: str, keys, codec: str = 'flat', root: str = 'common', inner=None) -> dict:
    """与 wf_campus_nephtim_tables.claim / manifest tables 条目同格式。"""
    return {'codec_id': codec, 'inner_keys': inner or [], 'logical_path': logical,
            'outer_keys': sorted(keys), 'root': root, 'semantic_claims': []}


def encode_flat_rows(rows: list[list[str]]) -> bytes:
    return zlib.compress(core.write_csv_lines(rows).encode('utf-8'))


def decode_flat_rows(raw: bytes) -> list[list[str]]:
    # 整段文本交给 csv.reader（引号内换行不能按物理行拆，U0000 事故）。
    return core.read_csv_lines(zlib.decompress(raw).decode('utf-8'))


def validate_voice_plan(role: str, lines: list[dict]) -> dict[str, dict]:
    slots = role_slots(role)
    by_slot = {}
    for line in lines:
        if line.get('role') != role:
            raise ValueError('voice plan mixes roles')
        slot = normalize_slot(line.get('slot'), slots)
        if slot in by_slot:
            raise ValueError(f'duplicate voice slot {slot}')
        if not line.get('ja') or not line.get('zh'):
            raise ValueError(f'{slot} requires ja and zh')
        by_slot[slot] = line
    if set(by_slot) != set(slots):
        raise ValueError(f'pack requires the full {len(slots)}-slot set; missing ' +
                         ', '.join(s for s in slots if s not in by_slot))
    if any(gate.engine_reachable(list(slots)).values()):
        raise AssertionError('slot table contains unreachable numbered voices')
    return by_slot


def speech_rows(lines: list[dict]) -> list[list[str]]:
    """character_speech 8 行：home_N（kind0 constraint 2）+ join（kind2）+ evolution（kind1 evo 1）。"""
    by_slot = {line['slot']: line for line in lines}
    home_slots = [s for s in ALL_SLOTS if s.startswith('home/') and s in by_slot] or list(HOME_SLOTS)
    rows = [['0', '2', '', by_slot[slot]['zh'], slot] for slot in home_slots]
    rows.append(['2', '', '', by_slot['ally/join']['zh'], 'ally/join'])
    rows.append(['1', '', '1', by_slot['ally/evolution']['zh'], 'ally/evolution'])
    for row in rows:
        check_subtitle(row[3])
        if '\r' in row[3]:
            raise ValueError('subtitle contains carriage return')
    home = [row[1] for row in rows if row[0] == '0']
    # ClientError 2265：每个进化档可见 home ≥1，且 join 与 evo_level=1 的 evolution 各一行。
    if not any(c in ('0', '2') for c in home) or not any(c in ('1', '2') for c in home):
        raise AssertionError('speech rows would raise ClientError 2265')
    return rows


def route_character_row(row: list[str], route_cols: list[str], code: str) -> list[str]:
    if len(row) < 17 or row[0] != code or row[8] != code:
        raise ValueError('character/action identity mismatch')
    if row[9] != '(None)':
        if row[9:17] != route_cols:
            raise ValueError('refuse to replace an existing unrelated skill switch')
    elif any(row[10:17]):
        raise ValueError('unreviewed residual skill switch columns')
    output = deepcopy(row)
    output[9:17] = route_cols
    return output


def switched_rows(action_rows: dict) -> dict[str, list[str]]:
    """SwitchedActionSkillValues = ActionSkillValues 第 7–23 列（程序路径 + 自动放技能条件）。"""
    if set(action_rows) != {'1', '2'}:
        raise ValueError('expected both native evolution levels 1 and 2')
    output = {}
    for level in ('1', '2'):
        row = action_rows[level]
        if len(row) != 24:
            raise ValueError('unreviewed ActionSkillValues schema')
        output[level] = list(row[7:24])
    return output


def _package_dir(package, cid: str, code: str) -> Path:
    package = Path(package).resolve()
    if 'character_packs' not in package.parts:
        raise ValueError('voice packing requires a candidate under work/character_packs')
    for item in (package, *package.parents):
        if item.is_symlink() or getattr(item, 'is_junction', lambda: False)():
            raise ValueError('candidate package has a reparse component')
    for marker in (package / 'manifest.json', package.parent / 'workspace.json'):
        if marker.is_file():
            data = json.loads(marker.read_bytes())
            if (str(data.get('character_id')), data.get('code_name')) != (cid, code):
                raise ValueError(f'package identity differs from {cid}/{code}: {marker}')
    return package


def _safe_path(package: Path, root: str, logical: str) -> Path:
    if root not in ('common', 'server'):
        raise ValueError('unsupported candidate root')
    parts = logical.split('/')
    if '\\' in logical or ':' in logical or any(p in ('', '.', '..') for p in parts):
        raise ValueError(f'unsafe logical path: {logical!r}')
    base = (package / 'roots' / root).resolve()
    path = (base / Path(*parts)).resolve()
    if not path.is_relative_to(base):
        raise ValueError('candidate path escapes package root')
    return path


def _package_table(package: Path, logical: str) -> dict[str, bytes]:
    raw = _safe_path(package, 'common', logical).read_bytes()
    table = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
    return dict(zip(table.keys, table.rows))


def read_package_character_row(package, cid: str) -> list[str]:
    rows = decode_flat_rows(_package_table(Path(package), CHARACTER_TABLE)[cid])
    if len(rows) != 1:
        raise ValueError('unreviewed CharacterValues row count')
    return rows[0]


def read_package_action_rows(package, code: str) -> dict[str, list[str]]:
    return dict(core.decode_action_skill_row(_package_table(Path(package), ACTION_TABLE)[code]))


def _standard_bytes(standard, slot: str) -> bytes:
    if callable(standard):
        return standard(slot)
    if isinstance(standard, dict):
        return standard[slot]
    return (Path(standard) / (slot + '.mp3')).read_bytes()


DURATION_RULES = frozenset({'over_official_max', 'over_official_p90', 'below_official_min'})


def pack_voice(package, role: str, lines: list[dict], standard, *, route, character_row=None,
               action_rows=None, mirror_row=None, exclude_rules: str | None = None,
               replace: bool = False, write: bool = True) -> dict:
    """写 roots/common/character/<code>/voice/<slot>.mp3（存储态）并返回表行与 claims。

    standard：标准态 MP3 目录、{slot: bytes} 或 callable(slot)->bytes。
    character_row/action_rows 缺省时读 package 内候选表（由表构建步骤先写好）。
    表文件不在这里改；需要落表时调用 apply_package_tables。
    """
    if role not in ROLES:
        raise ValueError(f'unknown role {role!r}')
    cid, code = ROLES[role]['cid'], ROLES[role]['code']
    slots = role_slots(role)
    by_slot = validate_voice_plan(role, lines)
    package = _package_dir(package, cid, code)
    if exclude_rules is not None:
        if any(not token for token in exclude_rules.split('|')):
            raise ValueError('empty character_voice_exclude token silences every voice')
        blocked = [s for s in slots if native_excluded(f'character/{code}/voice/{s}', exclude_rules)]
        if blocked:
            raise ValueError(f'character_voice_exclude blocks {code}: {blocked[:3]}')
    route_cols = normalize_route(route, code)
    if character_row is None:
        character_row = read_package_character_row(package, cid)
    if action_rows is None:
        action_rows = read_package_action_rows(package, code)

    voices, findings = [], []
    for slot in slots:
        standard_raw = _standard_bytes(standard, slot)
        stored = wf_assets.mp3_encode(standard_raw)
        if wf_assets.mp3_decode(stored) != standard_raw:
            raise ValueError(f'native MP3 storage roundtrip failed: {slot}')
        voices.append(gate.VoiceFile(code, slot, stored))
        findings += duration_findings(code, slot, gate.probe(stored)['duration'])
    findings += [asdict(f) for f in gate.check_voice_set(voices) if f.rule not in DURATION_RULES]
    errors = [f for f in findings if f['level'] == 'error']
    if errors:
        raise ValueError(f'voice gate failed: {errors}')

    assets, pending = [], []
    for voice in voices:
        logical = f'character/{code}/voice/{voice.slot}.mp3'
        path = _safe_path(package, 'common', logical)
        state = 'new'
        if path.is_file():
            if path.read_bytes() == voice.data:
                state = 'unchanged'
            elif not replace:
                raise ValueError(f'existing candidate voice differs (pass replace=True): {logical}')
            else:
                state = 'replaced'
        assets.append(dict(root='common', logical_path=logical, sha256=sha(voice.data),
                           size=len(voice.data), state=state))
        if state != 'unchanged':
            pending.append((path, voice.data))
    voice_root = _safe_path(package, 'common', f'character/{code}/voice')
    planned = {f'character/{code}/voice/{s}.mp3' for s in slots}
    foreign = sorted(p.relative_to(package / 'roots' / 'common').as_posix() for p in voice_root.rglob('*')
                     if p.is_file()) if voice_root.is_dir() else []
    foreign = [p for p in foreign if p not in planned]
    if write:
        for path, data in pending:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if path.read_bytes() != data:
                raise OSError(f'candidate voice readback failed: {path}')

    speech = speech_rows([by_slot[s] for s in slots])
    character = route_character_row(character_row, route_cols, code)
    switched = switched_rows(action_rows)
    key = switch_key(code)
    table_rows = {
        CHARACTER_TABLE: {cid: encode_flat_rows([character])},
        SPEECH_TABLE: {cid: encode_flat_rows(speech)},
        SWITCH_TABLE: {key: core.encode_action_skill_row([(level, switched[level]) for level in ('1', '2')])},
    }
    claims = [claim(CHARACTER_TABLE, [cid]), claim(SPEECH_TABLE, [cid]),
              claim(SWITCH_TABLE, [key], codec='switched_nested', inner=[dict(keys=['1', '2'], outer_key=key)])]
    server_rows = {}
    if mirror_row is not None:
        mirror = deepcopy(mirror_row)
        if len(mirror) != 1 or mirror[0][0] != code:
            raise ValueError('server character mirror identity mismatch')
        mirror[0] = route_character_row(mirror[0], route_cols, code)
        server_rows = {SERVER_CHARACTER: {cid: mirror}}
        claims.append(claim(SERVER_CHARACTER, [cid], codec='json_object', root='server'))
    return dict(role=role, character_id=cid, code=code, written=write, writes_live=False,
                assets=assets, foreign_voice_files=foreign, findings=findings,
                rows=dict(speech=speech, character=[character], route=route_cols, switched=switched),
                table_rows=table_rows, server_rows=server_rows, claims=claims,
                metadata=dict(voice_count=len(voices), language='ja', home_ally_subtitles='zh-CN',
                              battle_subtitles='delivery manifest only', switched_key=key,
                              route_kind={'0': 'HpHigh', '1': 'ConditionExist', '3': 'ChangeSkillFlag'}[route_cols[0]],
                              suggested_voice_actor=VOICE_ACTOR, new_client_capabilities=[]))


def splice_table(raw: bytes, logical: str, rows: dict[str, bytes]) -> bytes:
    """只替换/追加自有外层键；其他键字节不变。"""
    table = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
    prior = dict(zip(table.keys, table.rows))
    for key, value in rows.items():
        if key in prior:
            table.rows[table.keys.index(key)] = value
        else:
            table.keys.append(key)
            table.rows.append(value)
    output = core.build_orderedmap_raw_rows(table)
    check = core.read_orderedmap_raw_rows_from_bytes(output, logical)
    after = dict(zip(check.keys, check.rows))
    if any(after.get(k) != v for k, v in prior.items() if k not in rows) or \
            any(after.get(k) != v for k, v in rows.items()):
        raise AssertionError(f'foreign table row changed: {logical}')
    return output


def apply_package_tables(package, result: dict) -> list[dict]:
    """把 pack_voice 的表行拼进候选包已有表文件（不从 live 新建表）。"""
    from wf_content_revision_patch import merge_json
    package = _package_dir(package, result['character_id'], result['code'])
    report = []
    for logical, rows in result['table_rows'].items():
        path = _safe_path(package, 'common', logical)
        if not path.is_file():
            raise FileNotFoundError(f'candidate table missing; build tables first: {logical}')
        before = path.read_bytes()
        after = splice_table(before, logical, rows)
        report.append(dict(root='common', logical_path=logical, before_sha256=sha(before),
                           after_sha256=sha(after), size=len(after), changed=after != before))
        if after != before:
            path.write_bytes(after)
    for logical, rows in result['server_rows'].items():
        path = _safe_path(package, 'server', logical)
        before = path.read_bytes()
        target = json.loads(before)
        target.update(rows)
        after = merge_json(before, json.dumps(target, ensure_ascii=False).encode('utf-8'), set(rows))[0]
        report.append(dict(root='server', logical_path=logical, before_sha256=sha(before),
                           after_sha256=sha(after), size=len(after), changed=after != before))
        if after != before:
            path.write_bytes(after)
    return report


# ---------------------------------------------------------------- 参考音频

def choose_reference(candidates, render, low: float, high: float):
    """render(code, slot) -> (temp_path, info)；返回 (选中项, info, rejected)。"""
    rejected = []
    for code, slot in candidates:
        path, info = render(code, slot)
        seconds = info['duration_seconds']
        if low <= seconds <= high:
            return (code, slot), path, info, rejected
        rejected.append(dict(source_logical=f'character/{code}/voice/{slot}.mp3', clean_seconds=seconds,
                             reason=f'cleaned duration outside {low}-{high}s'))
        Path(path).unlink(missing_ok=True)
    raise ValueError('no reference candidate within the duration range')


def official_voice(baseline, code: str, slot: str) -> dict:
    logical = f'character/{code}/voice/{slot}.mp3'
    digest = core.sha1_path(logical)
    rel = digest[:2] + '/' + digest[2:]
    roots = [r for r in ('common', 'medium', 'android') if baseline.identity(r, rel) is not None]
    if len(roots) != 1:
        raise ValueError(f'official voice must have one authoritative root: {logical}: {roots}')
    stored = baseline.get(roots[0], rel)
    return dict(logical=logical, root=roots[0], stored=stored, standard=wf_assets.mp3_decode(stored))


def clean_reference(standard: bytes, target: Path, *, ffmpeg) -> dict:
    target.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg(ffmpeg, ['-v', 'error', '-y', '-f', 'mp3', '-i', 'pipe:0', '-map_metadata', '-1', '-af', REF_FILTERS,
                     '-ac', '1', '-ar', '48000', '-c:a', 'pcm_s16le', str(target)], input=standard)
    with wave.open(str(target), 'rb') as handle:
        info = dict(channels=handle.getnchannels(), sample_rate=handle.getframerate(),
                    sample_width=handle.getsampwidth(), frames=handle.getnframes())
    info['duration_seconds'] = round(info['frames'] / info['sample_rate'], 3)
    if (info['channels'], info['sample_rate'], info['sample_width']) != (1, 48000, 2):
        raise ValueError('reference is not 48 kHz mono 16-bit PCM')
    return info


def build_references(roles, *, out_dir=REFS_DIR, ffmpeg=None, baseline=None) -> dict:
    """官方归档（.cdn/cn OfficialBaseline）取母本原声 → 清洗 WAV → refs.json。"""
    from wf_enhancement_policy import OfficialBaseline
    ffmpeg = ffmpeg or find_tool('ffmpeg')
    out_dir = Path(out_dir)
    baseline = baseline or OfficialBaseline(ROOT / '.cdn' / 'cn',
                                            cache_dir=ROOT / 'mod-tools' / 'work' / 'official-baseline',
                                            write_cache=False)
    index_path = out_dir / 'refs.json'
    index = json.loads(index_path.read_bytes()) if index_path.is_file() else dict(schema=1, roles={})
    for role in roles:
        info = ROLES[role]
        entries = []
        for kind in ('battle', 'home'):
            low, high = REF_RANGES[kind]
            sources = {}

            def render(code, slot, kind=kind):
                voice = official_voice(baseline, code, slot)
                sources[(code, slot)] = voice
                temp = out_dir / role / f'{kind}.candidate.wav'
                return temp, clean_reference(voice['standard'], temp, ffmpeg=ffmpeg)

            (code, slot), temp, wav, rejected = choose_reference(REF_CANDIDATES[role][kind], render, low, high)
            final = out_dir / role / f'{kind}.wav'
            Path(temp).replace(final)
            voice = sources[(code, slot)]
            loudness = measure(final, Path(ffmpeg))
            entries.append(dict(kind=kind, path=str(final), sha256=sha(final.read_bytes()),
                                source_logical=voice['logical'], source_root=voice['root'],
                                source_code=code, source_slot=slot,
                                source_stored_sha256=sha(voice['stored']),
                                source_standard_sha256=sha(voice['standard']),
                                source_seconds=round(gate.probe(voice['stored'])['duration'], 3),
                                cleaning=REF_FILTERS, clean_lufs_i=loudness['lufs_i'], clean_lra_lu=loudness['lra_lu'],
                                range_seconds=[low, high], rejected=rejected, **wav))
        index['roles'][role] = dict(character_id=info['cid'], code=info['code'],
                                    template_id=info['template_id'], template_code=info['template_code'],
                                    references=entries, note=REF_NOTES.get(role, ''))
    index.update(schema=1, updated_at=_now(), source='OfficialBaseline .cdn/cn official archive',
                 official_tail=getattr(baseline, 'official_tail', None),
                 usage='官方声优原声做音色参考 = 克隆真人声纹；仅限本机自用，对外分发前须作者另行拍板（mech_voice.md §3.4）')
    _write_json(index_path, index)
    return index


def clean_reference_file(source, target: Path, *, ffmpeg, filters: str = REF_FILTERS_V2,
                         trim=None) -> dict:
    """本地任意音频 → 48 kHz 单声道 16-bit PCM 参考音。

    `凯尔声音参考1.mp3` 实测是 **AAC 套着 .mp3 后缀**；`resolve_references` 只看后缀、
    payload 直接 base64 原字节 ⇒ 必须先转码，不能直接当参考音送出去。
    """
    source, target = Path(source), Path(target)
    if not source.is_file():
        raise ValueError(f'reference source missing: {source}')
    target.parent.mkdir(parents=True, exist_ok=True)
    chain = ','.join(_trim_filters(trim) + ['aformat=channel_layouts=mono', 'aresample=48000', filters])
    _ffmpeg(ffmpeg, ['-v', 'error', '-y', '-i', str(source), '-map', '0:a:0', '-map_metadata', '-1',
                     '-af', chain, '-ac', '1', '-ar', '48000', '-c:a', 'pcm_s16le', str(target)])
    with wave.open(str(target), 'rb') as handle:
        info = dict(channels=handle.getnchannels(), sample_rate=handle.getframerate(),
                    sample_width=handle.getsampwidth(), frames=handle.getnframes())
    info['duration_seconds'] = round(info['frames'] / info['sample_rate'], 3)
    if (info['channels'], info['sample_rate'], info['sample_width']) != (1, 48000, 2):
        raise ValueError('reference is not 48 kHz mono 16-bit PCM')
    return info


def strip_loudnorm(filters: str) -> str:
    """把滤镜链里的 `loudnorm=...` 摘掉（RMS 归一路径自己定增益）。"""
    text = _LOUDNORM_COMPONENT.sub('', filters or '')
    return ','.join(p for p in text.split(',') if p.strip())


def pcm_levels(path, *, ffmpeg, rate: int = 48000) -> dict:
    """解码后的 RMS / 峰值（dBFS）—— 极短片段唯一靠得住的电平尺。"""
    values = decoded_pcm(Path(path), ffmpeg=ffmpeg, rate=rate).astype(np.float64)
    if not len(values):
        raise ValueError('empty decoded audio')
    rms = float(np.sqrt(np.mean(values ** 2)))
    peak = float(np.max(np.abs(values)))
    return dict(rms_dbfs=round(20 * math.log10(max(rms, 1e-12)), 2),
                peak_dbfs=round(20 * math.log10(max(peak, 1e-12)), 2))


def rms_normalize_reference(source, target: Path, *, ffmpeg, filters: str, trim=None,
                            target_rms_dbfs: float = REFERENCE_TARGET_RMS_DBFS,
                            peak_ceiling_dbfs: float = REFERENCE_PEAK_CEILING_DBFS) -> dict:
    """整合响度测不出的极短片段：去掉 loudnorm，改按 RMS 定增益（峰值封顶）。

    目标 RMS 取的是「整合响度可测」那批参考音的实测 RMS 中位数，所以两条路子出来的
    参考音等响；峰值天花板与 loudnorm 的 TP 对齐，不会因为定增益把短喊声推到削波。
    """
    bare = strip_loudnorm(filters)
    info = clean_reference_file(source, target, ffmpeg=ffmpeg, filters=bare, trim=trim)
    before = pcm_levels(target, ffmpeg=ffmpeg)
    gain = min(target_rms_dbfs - before['rms_dbfs'], peak_ceiling_dbfs - before['peak_dbfs'])
    chain = f'{bare},volume={gain:.4f}dB' if bare else f'volume={gain:.4f}dB'
    info = clean_reference_file(source, target, ffmpeg=ffmpeg, filters=chain, trim=trim)
    after = pcm_levels(target, ffmpeg=ffmpeg)
    return dict(info=info, filters=chain, gain_db=round(gain, 3),
                target_rms_dbfs=target_rms_dbfs, peak_ceiling_dbfs=peak_ceiling_dbfs,
                before=before, levels=after)


def build_references_v2(specs: dict, *, out_dir, ffmpeg=None, index_path=None) -> dict:
    """逐角色逐 group 从显式源文件造参考音，写 `refs-v2.json`。

    specs = {role: {'note', 'filters', 'slot_to_group': {...}, 'exemptions': {group: 理由},
                    'groups': {name: {'source', 'filters'?, 'range'?, 'trim'?, 'second': {...}?}}}}
    产物只写 out_dir 下；源文件只读，一个字节都不动。

    电平：清洗后先按常规配方（loudnorm=I=-16）量一次整合响度；测不出（-70）或片段短于
    `SHORT_REFERENCE_SECONDS` 时改走 RMS 归一，并在记录里如实写 `loudness_method`。
    区间/电平不合格的 group 会进 `violations`；`group_references` 据此拦，
    除非角色策略的 `exemptions` 里写了理由。
    """
    ffmpeg = ffmpeg or find_tool('ffmpeg')
    out_dir = Path(out_dir)
    index_path = Path(index_path) if index_path else out_dir / 'refs-v2.json'
    index = json.loads(index_path.read_bytes()) if index_path.is_file() else dict(schema=2, roles={})
    for role, spec in specs.items():
        groups, warnings, violations = {}, [], []
        default_filters = spec.get('filters') or REF_FILTERS_V2
        exemptions = {k: str(v).strip() for k, v in (spec.get('exemptions') or {}).items() if str(v).strip()}
        for name, item in (spec.get('groups') or {}).items():
            entry = {}
            for label, source_spec in (('', item), ('second', item.get('second'))):
                if not source_spec:
                    continue
                suffix = name if not label else f'{name}.2'
                final = out_dir / role / f'{suffix}.wav'
                filters = source_spec.get('filters') or default_filters
                wav = clean_reference_file(source_spec['source'], final, ffmpeg=ffmpeg,
                                           filters=filters, trim=source_spec.get('trim'))
                loudness = measure(final, Path(ffmpeg))
                levels = pcm_levels(final, ffmpeg=ffmpeg)
                method, normalized = 'ebu_r128', None
                if (loudness['lufs_i'] <= LOUDNESS_UNMEASURABLE_LUFS
                        or wav['duration_seconds'] < SHORT_REFERENCE_SECONDS):
                    normalized = rms_normalize_reference(source_spec['source'], final, ffmpeg=ffmpeg,
                                                         filters=filters, trim=source_spec.get('trim'))
                    wav, levels = normalized['info'], normalized['levels']
                    loudness = measure(final, Path(ffmpeg))
                    method = 'rms'
                low, high = item.get('range') or REF_RANGES_V2.get(name, (0.3, 20.0))
                measurable = loudness['lufs_i'] > LOUDNESS_UNMEASURABLE_LUFS
                record = dict(path=str(final), sha256=sha(final.read_bytes()),
                              source=str(source_spec['source']), filters=filters,
                              seconds=wav['duration_seconds'],
                              # 测不出时不写 -70 这个假数；真实电平看 rms_dbfs。
                              lufs_i=loudness['lufs_i'] if measurable else None,
                              lufs_i_raw=loudness['lufs_i'], loudness_measurable=measurable,
                              loudness_method=method, lra_lu=loudness['lra_lu'],
                              rms_dbfs=levels['rms_dbfs'], peak_dbfs=levels['peak_dbfs'],
                              range_seconds=[low, high],
                              range_ok=low <= wav['duration_seconds'] <= high, **wav)
                if normalized:
                    record.update(filters=normalized['filters'], rms_gain_db=normalized['gain_db'],
                                  rms_target_dbfs=normalized['target_rms_dbfs'],
                                  rms_before=normalized['before'],
                                  loudness_note='整合响度在这个长度上测不出（EBU R128 400ms 窗）；'
                                                '电平按 RMS 归一，与其它参考音的实测 RMS 中位对齐')
                if exemptions.get(name):
                    record['exempt_reason'] = exemptions[name]
                defects = reference_defects(record)
                if not record['range_ok']:
                    warnings.append(dict(group=name, slot_role=label or 'primary',
                                         seconds=wav['duration_seconds'], range_seconds=[low, high],
                                         rule='outside_group_duration_range'))
                if defects:
                    violations.append(dict(group=name, slot_role=label or 'primary', defects=defects,
                                           seconds=wav['duration_seconds'], range_seconds=[low, high],
                                           loudness_method=method, rms_dbfs=levels['rms_dbfs'],
                                           exempt_reason=exemptions.get(name) or None,
                                           exempted=bool(exemptions.get(name))))
                if label:
                    entry['second'] = record
                else:
                    entry.update(record, name=name)
            groups[name] = entry
        mapping = dict(spec.get('slot_to_group') or {})
        missing = sorted({g for g in mapping.values() if g not in groups})
        if missing:
            raise ValueError(f'{role}: slot_to_group references unknown groups {missing}')
        unused = sorted(set(exemptions) - set(groups))
        if unused:
            raise ValueError(f'{role}: reference exemptions name unknown groups {unused}')
        index['roles'][role] = dict(kind=spec.get('kind', ''), note=spec.get('note', ''),
                                    groups=groups, slot_to_group=mapping, warnings=warnings,
                                    exemptions=exemptions, violations=violations,
                                    blocking=[v for v in violations if not v['exempted']])
    index.update(schema=2, updated_at=_now(),
                 usage='官方声优原声做音色参考 = 克隆真人声纹；仅限本机自用，对外分发前须作者另行拍板')
    _write_json(index_path, index)
    return index


# ---------------------------------------------------------------- 多 take 与自动选优

def take_dir(run_dir, take: int) -> Path:
    if not isinstance(take, int) or not 1 <= take <= 99:
        raise ValueError('take index must be between 1 and 99')
    return Path(run_dir) / 'takes' / f'{take:02d}'


def take_numbers(run_dir) -> list[int]:
    folder = Path(run_dir) / 'takes'
    return sorted(int(p.name) for p in folder.glob('[0-9][0-9]') if p.is_dir()) if folder.is_dir() else []


_KANA_DROP = '、。，．,.!！?？…‥・「」『』“”"\'（）()〜~—―– 　\n\r\t'


def normalize_spoken(text: str) -> str:
    """片假名→平假名、去标点空格：subtitle 与请求台词的可比形态。"""
    out = []
    for ch in text or '':
        if ch in _KANA_DROP:
            continue
        code = ord(ch)
        out.append(chr(code - 0x60) if 0x30A1 <= code <= 0x30F6 else ch)
    return ''.join(out)


def subtitle_metrics(receipt: dict, spoken: str) -> dict:
    """接口回执的逐字时间戳 → 句首/句尾静音、句内最大间隔、文本一致性。"""
    response = receipt.get('response') or {}
    subtitle = response.get('subtitle') or {}
    text = str(subtitle.get('text') or '').strip()
    words = [w for s in (subtitle.get('sentences') or []) for w in (s.get('words') or [])]
    duration = float(response.get('duration') or 0.0)
    said, want = normalize_spoken(text), normalize_spoken(spoken)
    metrics = dict(subtitle_text=text, subtitle_present=bool(text), duration=duration,
                   text_exact=bool(text) and said == want,
                   text_superset=bool(text) and want and want in said and said != want,
                   words=len(words))
    if words:
        lead = float(words[0].get('start_time') or 0) / 1000.0
        tail = max(0.0, duration - float(words[-1].get('end_time') or 0) / 1000.0)
        gaps = [max(0.0, (float(b.get('start_time') or 0) - float(a.get('end_time') or 0)) / 1000.0)
                for a, b in zip(words, words[1:])]
        metrics.update(lead_in_seconds=round(lead, 3), tail_seconds=round(tail, 3),
                       max_inner_gap_seconds=round(max(gaps) if gaps else 0.0, 3),
                       dead_air_share=round((lead + tail) / duration, 4) if duration > 0 else None)
    else:
        metrics.update(lead_in_seconds=None, tail_seconds=None, max_inner_gap_seconds=None,
                       dead_air_share=None)
    return metrics


def pcm_edges(qc: dict) -> tuple[float | None, float | None]:
    """没有 subtitle 时的替代量：源 PCM 的首尾静音（与逐字时间戳同义）。"""
    source = qc.get('source_pcm') or {}
    lead, tail = source.get('leading_quiet_seconds'), source.get('trailing_quiet_seconds')
    return (None if lead is None else round(float(lead), 3),
            None if tail is None else round(float(tail), 3))


# 句内最长停顿的上限 = 官方同长度短战斗语音的 p90（rework2/voice/scratch/official_inner_gap.py，
# 160 角色 skill_0..3 / battle_start / power_flip 共 944 条，-38dB 相对静音）：
#   语音段 <1.6s p90=0.30 · 1.6–2.4s p90=0.45 · 2.4–3.6s p90=0.59（其中 35% 的官方条 >0.35s）。
# 原先一刀切 0.35s：两句话的技能台词（「近寄るな。焦げても知らんぞ。」）四次抽卡全灭，而官方同长度
# 的条有三分之一过不了这道门 —— 门比官方还严，不是音频的毛病。
INNER_GAP_LIMITS = ((1.6, 0.35), (2.4, 0.45), (math.inf, 0.60))
INNER_GAP_ELLIPSIS_LIMIT = 0.90


def inner_gap_limit(seconds: float, spoken: str) -> float:
    if '…' in spoken or '—' in spoken:                    # 稿子里写明的停顿（省略号、破折号急刹）
        return INNER_GAP_ELLIPSIS_LIMIT
    return next(limit for upper, limit in INNER_GAP_LIMITS if seconds < upper)


def take_gates(line: dict, metrics: dict, qc: dict) -> list[str]:
    """recipe.auto_select_metrics.hard_gates：任一不过即丢弃这一 take。

    与 recipe 的两处偏差（都有本轮实测证据，见 pipeline-v2.md）：
    1. subtitle 为空时不直接丢弃 —— 首尾静音改用源 PCM 量，只有「文本一致」这一项
       变成不可验证（记 `text_unverified`，选优时排在可验证的 take 之后）。
       实测：fluffy 的 skill_ready / battle_start_0 换成 mp3 返回同样空 subtitle
       ⇒ 空 subtitle 是这几条台词的稳定属性，硬丢会让这两个槽的所有 take 全灭。
    2. 完整 two_pass QC 的源响度仅作诊断；成品响度、真峰、削波、样本数及限幅量仍为硬门。
       旧报告仍保留 -26 LUFS 源下限；不能仅因源文件的整体增益不同丢弃同样合格的成品。
    """
    fam = family(line['slot'])
    spoken = line.get('tts_text') or line['ja']
    target = SLOT_TARGETS[fam]
    failed = []
    if metrics['subtitle_present'] and not metrics['text_exact']:
        failed.append('text_superset' if metrics['text_superset'] else 'text_exact')
    from wf_voice_selection_timing import delivery_edges, delivery_gap, raw_level_is_blocking
    lead, tail = delivery_edges(metrics, qc)
    if lead is None or lead > 0.60:
        failed.append('lead_in')
    if tail is None or tail > 0.50:
        failed.append('tail')
    gap, span = delivery_gap(metrics, qc)
    if fam in SHORT_BATTLE_FAMILIES and gap is not None:
        limit = inner_gap_limit(span, spoken)
        if gap > limit:
            failed.append('inner_gap')
    if raw_level_is_blocking(qc, RAW_LUFS_FLOOR):
        failed.append('raw_loudness')
    seconds = float(qc.get('seconds') or 0.0)
    if seconds > target['official_max']:
        failed.append('over_official_max')
    elif not target['p10'] <= seconds <= target['p90']:
        failed.append('duration_band')
    final = qc.get('final') or {}
    if loudness_verdict(final.get('lufs_i')) != 'ok':
        failed.append('master_loudness')
    # 限幅仍然只是安全网：判据取这份报告**自己**是按哪个上界做出来的
    # （two_pass = SAFETY_LIMITER_REDUCTION_DB，v1 定增益 = MAX_LIMITER_REDUCTION_DB），
    # 不再对两种策略的报告套同一个数。密度级不放宽这一条。
    bound = float((qc.get('params') or {}).get('max_limiter_reduction_db')
                  or SAFETY_LIMITER_REDUCTION_DB)
    if float(qc.get('limiter_reduction_bound_db') or 0.0) > bound + 1e-6:
        failed.append('limiter_reduction')
    if float(final.get('true_peak_dbtp', 0)) > PEAK_CEILING:
        failed.append('true_peak')
    if float((qc.get('mastered_pcm') or {}).get('clipped_fraction') or 0.0) > 0:
        failed.append('clipping')
    return failed


def take_score(line: dict, metrics: dict, qc: dict) -> float:
    """越小越好：时长偏差 + 空气占比 + 限幅 + 语速偏差 + 句内停顿。"""
    fam = family(line['slot'])
    target = SLOT_TARGETS[fam]
    seconds = float(qc.get('seconds') or 0.0)
    spoken = line.get('tts_text') or line['ja']
    chars = spoken_chars(spoken)
    cps_mid = chars_per_second(fam)
    cps = chars / seconds if seconds > 0 else cps_mid
    from wf_voice_selection_timing import delivery_dead_air, delivery_gap
    dead = delivery_dead_air(metrics, qc)
    gap = delivery_gap(metrics, qc)[0] or 0.0
    return round(1.0 * abs(seconds - target['p50']) / target['p50']
                 + 1.5 * dead
                 + 1.0 * max(0.0, float(qc.get('limiter_reduction_bound_db') or 0.0) - 0.5)
                 + 0.5 * abs(cps - cps_mid) / cps_mid
                 + 0.5 * max(0.0, gap - 0.30), 4)


def select_takes(lines: list[dict], run_dir, *, takes=None) -> dict:
    """扫全部 take，按硬门 + 打分选优，写 selected.json。不联网、不改音频。"""
    run_dir = Path(run_dir)
    numbers = sorted(takes) if takes else take_numbers(run_dir)
    if not numbers:
        raise ValueError(f'no take directories under {run_dir / "takes"}')
    roles, queue = {}, []
    for line in lines:
        role, slot = line['role'], line['slot']
        spoken = line.get('tts_text') or line['ja']
        candidates, rejected = [], []
        for take in numbers:
            base = take_dir(run_dir, take) / role
            receipt_path = base / 'receipts' / (slot + '.json')
            qc_path = base / 'qc' / (slot + '.json')
            standard = base / 'standard' / (slot + '.mp3')
            if not (receipt_path.is_file() and qc_path.is_file() and standard.is_file()):
                rejected.append(dict(take=take, failed=['missing']))
                continue
            receipt = json.loads(receipt_path.read_bytes())
            qc = json.loads(qc_path.read_bytes())
            if qc.get('standard_sha256') != sha(standard.read_bytes()):
                rejected.append(dict(take=take, failed=['standard_drift']))
                continue
            metrics = subtitle_metrics(receipt, spoken)
            failed = take_gates(line, metrics, qc)
            record = dict(take=take, score=take_score(line, metrics, qc), failed=failed,
                          text_unverified=not metrics['subtitle_present'],
                          standard=str(standard), qc=str(qc_path), receipt=str(receipt_path),
                          seconds=qc.get('seconds'), lufs_i=(qc.get('final') or {}).get('lufs_i'),
                          raw_lufs_i=qc.get('raw_lufs_i'), metrics=metrics)
            (candidates if not failed else rejected).append(record)
        if candidates:
            # 文本可验证的 take 永远优先；同类里才比分数。
            best = min(candidates, key=lambda r: (r['text_unverified'], r['score'], r['take']))
            roles.setdefault(role, {})[slot] = dict(
                best, alternatives=len(candidates) - 1,
                # 落选原因留档：否则「为什么第 3 次没被选」只能靠重跑。
                # 补抽轮（--only）只含被补抽的槽位：其余槽位在该 take 下是 missing，记录里没有分数。
                rejected=[{k: r.get(k) for k in ('take', 'failed', 'score', 'seconds', 'raw_lufs_i')}
                          for r in rejected],
                runners_up=[{k: r[k] for k in ('take', 'score', 'seconds')}
                            for r in candidates if r['take'] != best['take']])
        else:
            reasons = sorted({f for r in rejected for f in r['failed']})
            if len(reasons) > 1:                              # 「该 take 没抽这个槽」不是音频的毛病
                reasons = [f for f in reasons if f != 'missing']
            remedy = ('换参考音' if 'raw_loudness' in reasons else
                      '改台词（插词/超长）' if {'text_exact', 'text_superset', 'over_official_max'} & set(reasons)
                      else '加抽一次')
            queue.append(dict(role=role, slot=slot, ja=line['ja'], reasons=reasons,
                              action=remedy, takes=rejected))
    summary = dict(schema=1, generated_at=_now(), run=str(run_dir), takes=numbers,
                   selected=sum(len(v) for v in roles.values()), retake=len(queue),
                   text_unverified=[f'{r}:{s}' for r, items in roles.items()
                                    for s, v in items.items() if v['text_unverified']],
                   roles=roles, retake_queue=queue)
    _write_json(run_dir / 'selected.json', summary)
    return summary


def selected_standard(run_dir, role: str, slots) -> dict[str, bytes]:
    """selected.json → {slot: 标准态 MP3 字节}，供 pack 使用。"""
    data = json.loads((Path(run_dir) / 'selected.json').read_bytes())
    chosen = (data.get('roles') or {}).get(role) or {}
    missing = [s for s in slots if s not in chosen]
    if missing:
        raise ValueError(f'{role}: selected.json lacks {len(missing)} slot(s): ' + ', '.join(missing))
    out = {}
    for slot in slots:
        path = Path(chosen[slot]['standard'])
        qc = json.loads(Path(chosen[slot]['qc']).read_bytes())
        raw = path.read_bytes()
        if qc.get('standard_sha256') != sha(raw):
            raise ValueError(f'{role}:{slot} selected recording drifted from its QC report')
        out[slot] = raw
    return out


# ---------------------------------------------------------------- 冒烟

class _CapturingResponse:
    def __init__(self, response, sink):
        self._response, self._sink = response, sink
        self.status = response.status

    def __enter__(self):
        self._response.__enter__()
        return self

    def __exit__(self, *exc):
        return self._response.__exit__(*exc)

    def read(self, *args):
        data = self._response.read(*args)
        self._sink['http_status'] = self.status
        self._sink['headers'] = {h: self._response.headers.get(h) for h in ('Content-Type', 'X-Tt-Logid')}
        self._sink['response_bytes'] = len(data)
        try:
            body = json.loads(data)
        except ValueError:
            self._sink['fields'] = 'non-json body'
            return data
        self._sink['fields'] = {k: _describe(v) for k, v in body.items()} if isinstance(body, dict) else type(body).__name__
        return data


def _describe(value):
    if isinstance(value, str):
        return dict(type='str', length=len(value))
    if isinstance(value, dict):
        return dict(type='dict', keys=sorted(value)[:20],
                    sentences=len(value['sentences']) if isinstance(value.get('sentences'), list) else None)
    if isinstance(value, list):
        return dict(type='list', length=len(value))
    return dict(type=type(value).__name__, value=value if isinstance(value, (int, float, bool)) or value is None else None)


def capturing_opener(sink: dict, opener=urllib.request.urlopen):
    def open_request(request, **kwargs):
        return _CapturingResponse(opener(request, **kwargs), sink)
    return open_request


def run_smoke(key: str, *, out_dir=SMOKE_DIR, refs_index=None, opener=urllib.request.urlopen) -> dict:
    """只发 1 个请求（不自动重试）：生成 → 后处理 → mp3_encode/voice_gate 全链路。

    **只冒烟 prompt 模板 v1**：`SMOKE_LINE` 走 `request_lines(..., version=None)` = v1，
    raw 写死 `raw/<slot>.mp3`，后处理也是定增益。v2 的冒烟（逐槽参考音、wav、两遍
    loudnorm）本轮是另写脚本做的，产物在 `rework2/voice/smoke/v2`；CLI 这条 `smoke`
    子命令没有 v2 路径，帮助文本里已写明，别拿它当 v2 的验证手段。
    """
    out_dir = Path(out_dir)
    ffmpeg, ffprobe = find_tool('ffmpeg'), find_tool('ffprobe')
    voice = dict(persona=SMOKE_LINE['persona'], references=None,
                 lines=[{k: SMOKE_LINE[k] for k in ('slot', 'ja', 'zh', 'direction')}])
    line = request_lines(SMOKE_LINE['role'], voice, refs_index=refs_index, allow_partial=True)[0]
    report_path = out_dir / 'report.json'
    previous = json.loads(report_path.read_bytes()) if report_path.is_file() else {}
    sink = {}
    started = time.monotonic()
    result = generate_line(line, out_dir, key, opener=capturing_opener(sink, opener), max_retries=0)
    elapsed = round(time.monotonic() - started, 2)
    report = dict(started_at=_now(), endpoint=api.ENDPOINT, model=api.MODEL, request=dict(
        role=line['role'], slot=line['slot'], ja=line['ja'], zh=line['zh'], direction=line['direction'],
        references=[dict(path=r['path'], sha256=r['sha256']) for r in line['references']]),
        generation=result, wall_seconds=elapsed, response=sink)
    if result['status'] == 'cached' and previous.get('response'):
        # 续跑不再联网：保留首个真实请求的耗时与返回字段形状。
        report.update(first_request=previous.get('first_request') or dict(
            started_at=previous.get('started_at'), wall_seconds=previous.get('wall_seconds'),
            generation=previous.get('generation'), response=previous.get('response')))
    base = out_dir / line['role']
    if result['status'] in ('generated', 'cached'):
        receipt = json.loads((base / 'receipts' / (line['slot'] + '.json')).read_bytes())
        report['receipt'] = {k: receipt.get(k) for k in ('request_id', 'http_status', 'elapsed_seconds',
                                                         'bytes', 'sha256', 'response')}
        raw = base / 'raw' / (line['slot'] + '.mp3')
        report['raw_metadata'] = metadata(raw, ffprobe)
        target = base / 'standard' / (line['slot'] + '.mp3')
        if target.exists():
            target.unlink()
        stored, qc = master_voice(raw, target, slot=line['slot'], code=line['code'], ffmpeg=ffmpeg, ffprobe=ffprobe)
        _write_json(base / 'qc' / (line['slot'] + '.json'), qc)
        gate_findings = [asdict(f) for f in gate.check_voice_set([gate.VoiceFile(line['code'], line['slot'], stored)])]
        report['postprocess'] = dict(
            seconds=qc['seconds'], final=qc['final'], loudness_status=qc['loudness_status'],
            limiter_used=qc['limiter_ceiling_dbfs'] is not None, gain_db=round(qc['gain_db'], 3),
            codec={k: qc['codec'][k] for k in ('srate', 'channels', 'bitrate', 'cbr', 'xing', 'tail', 'obfuscated')},
            mp3_encode_strict=True, storage_roundtrip_equal=qc['storage_roundtrip_equal'],
            storage_sha256=qc['storage_sha256'], sample_delta=qc['sample_delta'],
            duration_findings=qc['findings'], voice_gate=gate_findings,
            leading_quiet_seconds=round(qc['mastered_pcm']['leading_quiet_seconds'], 3),
            trailing_quiet_seconds=round(qc['mastered_pcm']['trailing_quiet_seconds'], 3))
    _write_json(report_path, report)
    leaked = scrub_secret(out_dir, key)
    if leaked:
        raise RuntimeError('credential text was found and redacted in smoke output')
    return report


# ---------------------------------------------------------------- CLI

def _output_dir(path) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(VOICE_DIR.resolve()):
        raise SystemExit('output outside the seasonal7 voice workspace')
    return resolved


def _child_argv(argv: list[str]) -> list[str]:
    output, skip = [], False
    for token in argv:
        if skip:
            skip = False
            continue
        if token == '--key-file':
            skip = True
            continue
        if token.startswith('--key-file='):
            continue
        output.append(token)
    return output


def child_env(key_file) -> dict:
    """读密钥文件，返回注入了 WF_SEED_AUDIO_KEY 的子进程环境（调用方不得打印）。"""
    key = Path(key_file).read_text(encoding='utf-8').strip()
    if not key or any(c.isspace() for c in key):
        raise SystemExit('credential file is empty or malformed')
    env = dict(os.environ)
    env[KEY_ENV] = key
    return env


def _take_key() -> str:
    key = os.environ.pop(KEY_ENV, '')
    if not key:
        raise SystemExit(f'missing process credential; pass --key-file (injected as {KEY_ENV})')
    return key


def _roles(values) -> list[str]:
    roles = values or list(ROLES)
    unknown = [r for r in roles if r not in ROLES]
    if unknown:
        raise SystemExit(f'unknown roles: {unknown}')
    return roles


def _plans(args) -> list[dict]:
    plans = []
    version = getattr(args, 'prompt_version', None)
    for role in _roles(args.roles):
        design = Path(args.design) if getattr(args, 'design', None) else None
        plans.append(plan_role(role, design, version=version))
    return plans


def _take_dirs(run_dir: Path, args) -> list[Path]:
    """`--take N`/`--takes N` → takes/NN 目录；都不给时用旧的扁平布局。"""
    picked = getattr(args, 'take', None)
    count = getattr(args, 'takes', None)
    if picked:
        return [take_dir(run_dir, int(picked))]
    if count:
        return [take_dir(run_dir, i) for i in range(1, int(count) + 1)]
    existing = take_numbers(run_dir)
    return [take_dir(run_dir, i) for i in existing] if existing else [run_dir]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('refs', help='准备 7 个母本的清洗参考 WAV 与 refs.json')
    p.add_argument('--roles', nargs='*')

    for name, text in (('plan', '校验 design 并写请求快照（不联网）'), ('generate', '调用 Seed Audio 生成'),
                       ('process', '后处理到 -14 LUFS 标准 MP3 与 QC'),
                       ('select', '多 take 按硬门+打分选优，写 selected.json（不联网）'),
                       ('pack', '装包（默认 dry-run）')):
        p = sub.add_parser(name, help=text)
        p.add_argument('--roles', nargs='*')
        p.add_argument('--design', help='单角色时覆盖 design json 路径')
        p.add_argument('--run', default='take1', help='generation/<run> 目录；重录换新 run')
        p.add_argument('--prompt-version', type=int, choices=(1, 2), default=None,
                       help='2 = 本轮配方（逐槽参考音、引号封边、wav、两遍 loudnorm）')
        p.add_argument('--take', type=int, default=None, help='只作用于 takes/NN 这一次抽卡')
        p.add_argument('--takes', type=int, default=None, help='抽卡次数：takes/01..NN')
        if name == 'process':
            p.add_argument('--remaster', action='store_true',
                           help='允许用新策略覆盖旧的 qc/standard（不给就照旧抛 QC drift）；'
                                'raw 与 receipts 一个字节不动，也不会重新生成')
        if name == 'generate':
            p.add_argument('--only', action='append', default=[], help='role:slot，可重复')
            p.add_argument('--workers', type=int, choices=(1, 2), default=2)
            p.add_argument('--no-retry', action='store_true', help='本次不自动重试')
            p.add_argument('--key-file', help='读取后注入子进程环境变量')
            p.add_argument('--role-lock', action=argparse.BooleanOptionalAction, default=True,
                           help='角色级跨进程锁，默认开（防同一角色被两个进程重复计费）；'
                                '--no-role-lock 是逃生口')
            p.add_argument('--lock-timeout', type=float, default=0.0)
            p.add_argument('--quota-slots', type=int, choices=(0, 1, 2), default=MAX_WORKERS,
                           help='全局并发生成槽（与 --workers 同语义，本机所有语音进程共用）；0=关')
        if name == 'pack':
            p.add_argument('--selected', action='store_true', help='标准态取自 selected.json')
            p.add_argument('--package', required=True, help='work/character_packs/<pkg>/package')
            p.add_argument('--write', action='store_true', help='写存储态 MP3')
            p.add_argument('--apply-tables', action='store_true', help='同时把表行拼进候选包已有表')
            p.add_argument('--replace', action='store_true')

    p = sub.add_parser('smoke', help='单请求冒烟：生成 → 后处理 → mp3_encode（**只支持模板 v1**；'
                                     'v2 的冒烟另走脚本，见 pipeline-v2.md）')
    p.add_argument('--key-file', help='读取后注入子进程环境变量')
    args = parser.parse_args(argv)

    if getattr(args, 'key_file', None):
        env = child_env(args.key_file)
        return subprocess.run([sys.executable, str(Path(__file__).resolve()), *_child_argv(argv)], env=env).returncode

    if args.command == 'refs':
        index = build_references(_roles(args.roles))
        print(json.dumps({role: [(e['kind'], e['source_logical'], e['duration_seconds']) for e in item['references']]
                          for role, item in index['roles'].items()}, ensure_ascii=False, indent=1))
        return 0
    if args.command == 'smoke':
        key = _take_key()
        report = run_smoke(key)
        print(json.dumps(dict(status=report['generation']['status'], wall_seconds=report['wall_seconds'],
                              fields=report['response'].get('fields'), postprocess=report.get('postprocess')),
                         ensure_ascii=False, indent=1))
        return 0 if report['generation']['status'] in ('generated', 'cached') else 1

    run_dir = _output_dir(GENERATION_DIR / args.run)
    if args.command == 'plan':
        # plan 是改稿的人唯一的反馈面：逐角色报到底，一条稿子的问题列全，不要撞上第一条就退出。
        # 台词硬规则的 error 会让这个角色不写 plan 文件、整体 rc≠0（生成路径照样 strict）。
        failed = 0
        for role in _roles(args.roles):
            design = Path(args.design) if getattr(args, 'design', None) else None
            try:
                plan = plan_role(role, design, version=getattr(args, 'prompt_version', None),
                                 strict_text=False)
            except (ValueError, KeyError, OSError) as exc:
                failed += 1
                print(json.dumps(dict(role=role, status='blocked', problem=str(exc)),
                                 ensure_ascii=False), flush=True)
                continue
            errors, warnings = plan['text_errors'], plan['text_warnings']
            if not errors:
                for line in plan['lines']:
                    api.payload(line)   # 引用哈希与 payload 可构造
                _write_json(run_dir / 'plan' / f'{plan["role"]}.json',
                            dict(plan, planned_at=_now(),
                                 fingerprints={l['slot']: request_fingerprint(l) for l in plan['lines']}))
            failed += bool(errors)
            print(json.dumps(dict(role=plan['role'], status='ok' if not errors else 'text_rules_failed',
                                  lines=len(plan['lines']), slots=len(plan['slots']),
                                  prompt_version=plan['prompt_version'], route=plan['route'],
                                  text_errors=len(errors), text_warnings=len(warnings),
                                  plan_written=not errors), ensure_ascii=False), flush=True)
            for finding in errors + warnings:
                print(json.dumps(dict(role=plan['role'], **finding), ensure_ascii=False), flush=True)
        return 1 if failed else 0
    plans = _plans(args)
    if args.command == 'generate':
        key = _take_key()
        lines = [line for plan in plans for line in plan['lines']]
        if args.only:
            lines = [x for x in lines if f'{x["role"]}:{x["slot"]}' in args.only]
        if not lines:
            raise SystemExit('empty generation selection')
        for plan in plans:
            _write_json(run_dir / 'plan' / f'{plan["role"]}.json', dict(plan, planned_at=_now()))
        failed = 0
        for output in _take_dirs(run_dir, args):
            summary = run_generation(lines, output, key, workers=args.workers,
                                     max_retries=0 if args.no_retry else MAX_AUTO_RETRIES,
                                     role_locks=args.role_lock, lock_timeout=args.lock_timeout,
                                     quota_slots=args.quota_slots,
                                     on_result=lambda r: print(json.dumps(r, ensure_ascii=False), flush=True))
            print(json.dumps(dict(take=output.name, counts=summary['counts'],
                                  rewrite_queue=summary['rewrite_queue'],
                                  needs_new_reference=summary['needs_new_reference']), ensure_ascii=False))
            # 「不是 {generated, cached} 的子集」才叫失败。写成真超集（`>`）会让
            # {'generated':3,'fatal':1}、{'needs_rewrite':22} 全部 rc=0 —— 分波次驱动脚本据
            # 退出码判断就全错，第一轮 charlene 22/22 全 45001127 正是这种形状。
            failed += not (set(summary['counts']) <= {'generated', 'cached'})
        return 1 if failed else 0
    if args.command == 'process':
        lines = [line for plan in plans for line in plan['lines']]
        version = getattr(args, 'prompt_version', None)
        worst = 0
        for output in _take_dirs(run_dir, args):
            summary = process_run(lines, output, ffmpeg=find_tool('ffmpeg'), ffprobe=find_tool('ffprobe'),
                                  version=version, remaster=getattr(args, 'remaster', False))
            broken = sorted({f'{x["role"]}:{x["slot"]}' for x in summary['items']
                             if x['status'] in ('rejected', 'stale_plan', 'missing')})
            print(json.dumps(dict(take=output.name, failed_items=broken,
                                  **{k: summary[k] for k in
                                     ('over_official_max', 'over_official_p90', 'retake_candidates')}),
                             ensure_ascii=False, indent=1))
            worst += bool(summary['over_official_max']) + bool(broken)
        return 1 if worst else 0
    if args.command == 'select':
        lines = [line for plan in plans for line in plan['lines']]
        takes = [int(args.take)] if args.take else (list(range(1, int(args.takes) + 1)) if args.takes else None)
        summary = select_takes(lines, run_dir, takes=takes)
        print(json.dumps(dict(takes=summary['takes'], selected=summary['selected'], retake=summary['retake'],
                              # 空 subtitle 的槽只能记 text_unverified（接口对短战斗槽常返回空字幕），
                              # 这一批没有任何文本校验，必须在收口摘要里看得见条数。
                              text_unverified=len(summary['text_unverified']),
                              text_unverified_slots=summary['text_unverified'],
                              retake_queue=[f'{x["role"]}:{x["slot"]}({",".join(x["reasons"])})'
                                            for x in summary['retake_queue']]), ensure_ascii=False, indent=1))
        return 0 if not summary['retake_queue'] else 1
    if args.command == 'pack':
        if len(plans) != 1:
            raise SystemExit('pack one role at a time')
        plan = plans[0]
        role = plan['role']
        slots = role_slots(role)
        if args.selected:
            standard_dir = selected_standard(run_dir, role, slots)
        else:
            standard_dir = run_dir / role / 'standard'
            for slot in slots:
                qc = json.loads((run_dir / role / 'qc' / (slot + '.json')).read_bytes())
                if qc['standard_sha256'] != sha((standard_dir / (slot + '.mp3')).read_bytes()):
                    raise SystemExit(f'standard recording drifted from QC: {slot}')
        package = Path(args.package)
        mirror_path = package / 'roots' / 'server' / SERVER_CHARACTER
        mirror = json.loads(mirror_path.read_bytes()).get(ROLES[role]['cid']) if mirror_path.is_file() else None
        result = pack_voice(package, role, plan['lines'], standard_dir, route=plan['route'],
                            mirror_row=mirror, replace=args.replace, write=args.write)
        tables = apply_package_tables(package, result) if args.apply_tables and args.write else []
        record = {k: v for k, v in result.items() if k != 'table_rows'}
        record['table_rows_sha256'] = {logical: {key: sha(raw) for key, raw in rows.items()}
                                       for logical, rows in result['table_rows'].items()}
        record['applied_tables'] = tables
        _write_json(run_dir / role / 'pack-result.json', record)
        print(json.dumps(dict(role=role, written=args.write, assets=len(result['assets']),
                              foreign_voice_files=result['foreign_voice_files'], claims=result['claims'],
                              applied_tables=tables), ensure_ascii=False, indent=1))
        return 0
    return 2


if __name__ == '__main__':
    sys.exit(main())
