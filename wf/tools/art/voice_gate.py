# -*- coding: utf-8 -*-
"""角色语音门禁:容器规格、逐槽时长分位、重复投放、引擎可达性。

## 基线口径(2026-08-28 普查)

语料 = **官方 1.4.0 全量归档** `.cdn/cn/archive-common-full/pinball-1.4.0-*.zip`
∩ `弹国服/restored/_pathlist_restored.txt` 的角色语音路径,共 **9048 条 / 483 个角色**。
不用 live store —— store 里混着本仓自制角色,拿它当"官方分位"等于拿自己的偏差当标尺
(memory `wf-official-baseline-not-store`;本轮实证:`white_wolf_gerald`、
`seris_dragon_king` 在 1.4.0 归档里**根本不存在**,它们是自制角色)。

## 五条判据的由来

1. **容器规格**:9048/9048 全部是 `44100 Hz / 单声道 / 96 kbps CBR / MPEG1 Layer III
   带 Xing-Info 帧`,零例外。帧流之后的尾字节只有 0(7442 条)或 128 的 ID3v1 `TAG`
   (1606 条)。`wf_assets.mp3_encode` 的报错文案、`wf_voice.transcode_wav_to_mp3`
   的目标格式也都是这套参数 —— 这是平台规格,不是偏好。
2. **逐槽时长**:见 `OFFICIAL_DURATION`。**同一段音频在不同槽位的合法长度差好几倍**
   (`home` 最大 26.23s,`power_flip_N` 最大 3.13s),所以时长必须按槽位族判,不能一刀切。
   战斗类语音超长的后果不是"崩",是**叠播**:PF 语音 100% 触发且无冷却
   (memory `wf-pf-direction-impact-voice`),爬塔里技能几秒一发,上一条没播完下一条
   已触发 ⇒ 同一人声错位叠加(2026-08-05 作者实机反馈"电音"、2026-08-28 反馈"莫名其妙的循环")。
   ⇒ 硬红线 = 官方 max;建议线 = 官方 p90。
3. **重复投放**:官方 9048 条 → 9020 个不同 blob。**同角色内多槽位共用同一份字节:0 例**;
   跨角色共用 28 例,全部是**同一角色的不同 entry**(`alk`/`tutorial_alk`、
   `alk_serious`/`alk_shoutabattle`、`ekaki_onmyoji`/`ekaki_onmyoji_noskill`)且**同名槽位**。
   ⇒ 跨(不同)角色逐字节相同 = 硬错;同角色内共用 = 官方零先例,报 warn。
4. **引擎可达性**:`CharacterShortVoiceLogic.generateVoicePaths` 从 `<前缀>0` 顺序探,
   **一旦缺号立刻 break**(`boot` 反编译 `pinball/common/data/character/CharacterShortVoiceLogic.as`)。
   所以 `skill_0, skill_2` 而没有 `skill_1` ⇒ `skill_2` 永远播不到。
   引擎认的前缀只有七个(见 `ENGINE_BATTLE_PREFIXES`);`normal_attack_` 不在其中
   —— 官方 51 个角色也带着这对死资产,写了不会播。
5. **存储态**:客户端读的是**混淆态** mp3(帧头首字节 `0xFF`→`0x7F`)。写回时忘了混淆
   =文件在包里是标准 mp3,与官方形态不一致。

## 用法

    from wf_voice_gate import check_voice_set, VoiceFile
    findings = check_voice_set([VoiceFile(character, slot, data), ...])
    errors = [f for f in findings if f.level == 'error']
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

# ---------------------------------------------------------------- 官方基线常量

# 9048/9048 一致
OFFICIAL_SRATE = 44100
OFFICIAL_CHANNELS = 1
OFFICIAL_BITRATE_KBPS = 96
OFFICIAL_TAIL_BYTES = (0, 128)          # 0 或 128 字节的 ID3v1 TAG

# 族 -> (n, min, p50, p90, p95, p99, max),单位秒
OFFICIAL_DURATION: dict[str, tuple[int, float, float, float, float, float, float]] = {
    'home':            (2675, 2.66, 10.89, 15.77, 17.72, 21.11, 26.23),
    'battle_start_N':  (962, 0.50, 1.80, 2.59, 2.90, 3.51, 5.83),
    'skill_N':         (959, 0.81, 2.35, 3.21, 3.50, 4.26, 5.02),
    'power_flip_N':    (956, 0.29, 1.04, 1.70, 1.96, 2.49, 3.13),
    'outhole_N':       (954, 0.37, 0.99, 1.88, 2.07, 2.61, 3.37),
    'win_N':           (952, 0.97, 3.60, 5.41, 6.12, 7.63, 9.04),
    'skill_ready':     (478, 0.42, 1.46, 2.19, 2.51, 3.14, 3.81),
    'evolution':       (475, 3.84, 11.39, 15.12, 16.30, 19.97, 20.87),
    'join':            (475, 3.32, 10.00, 13.82, 15.01, 18.24, 21.66),
    'normal_attack_N': (102, 0.34, 0.68, 1.07, 1.20, 1.41, 1.78),
    'login':           (60, 0.84, 2.90, 4.23, 4.40, 4.96, 5.49),
}

# `CharacterShortVoiceLogic` 里 generateVoicePaths 用到的全部前缀
ENGINE_BATTLE_PREFIXES: tuple[str, ...] = (
    'battle_start_', 'skill_', 'power_flip_', 'outhole_', 'win_',
    'matched_skill_', 'exchange_power_flip_',
)
# 单文件槽(不走序号扫描)
ENGINE_SINGLE_SLOTS: tuple[str, ...] = ('skill_ready', 'matched_skill_ready')

_BITRATES: dict[tuple[int, int], list[int | None]] = {
    (3, 3): [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, None],
    (3, 2): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, None],
    (3, 1): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, None],
    (2, 3): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, None],
    (2, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, None],
    (2, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, None],
}
_SRATES: dict[int, list[int | None]] = {
    3: [44100, 48000, 32000, None],
    2: [22050, 24000, 16000, None],
    0: [11025, 12000, 8000, None],
}
_SAMPLES: dict[tuple[int, int], int] = {
    (3, 3): 384, (3, 2): 1152, (3, 1): 1152,
    (2, 3): 384, (2, 2): 1152, (2, 1): 576,
    (0, 3): 384, (0, 2): 1152, (0, 1): 576,
}


# ---------------------------------------------------------------- mp3 容器解析

def id3_len(data: bytes) -> int:
    """开头 ID3v2 标签总长(含 10 字节头);没有返回 0。"""
    if len(data) < 10 or data[:3] != b'ID3':
        return 0
    size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
    return 10 + size + (10 if data[5] & 0x10 else 0)


def parse_header(hdr: bytes) -> dict | None:
    """4 字节帧头;首字节允许 0xFF(标准)或 0x7F(WF 存储态)。"""
    if len(hdr) < 4 or (hdr[0] & 0x7F) != 0x7F or (hdr[1] & 0xE0) != 0xE0:
        return None
    ver = (hdr[1] >> 3) & 0x03
    layer = (hdr[1] >> 1) & 0x03
    if ver == 1 or layer == 0:
        return None
    bi, si, pad = (hdr[2] >> 4) & 0x0F, (hdr[2] >> 2) & 0x03, (hdr[2] >> 1) & 0x01
    if bi in (0, 15) or si == 3:
        return None
    bitrate = _BITRATES[(3 if ver == 3 else 2, layer)][bi]
    srate = _SRATES[ver][si]
    if bitrate is None or srate is None:
        return None
    samples = _SAMPLES[(ver, layer)]
    size = ((12 * bitrate * 1000 // srate + pad) * 4 if layer == 3
            else samples // 8 * bitrate * 1000 // srate + pad)
    mode = (hdr[3] >> 6) & 3
    return dict(bitrate=bitrate, srate=srate, samples=samples, size=size,
                channels=1 if mode == 3 else 2, obfuscated=hdr[0] == 0x7F)


def walk_frames(data: bytes) -> Iterator[tuple[int, dict]]:
    off = id3_len(data)
    while off + 4 <= len(data):
        h = parse_header(data[off:off + 4])
        if h is None:
            return
        yield off, h
        off += h['size']


def probe(data: bytes) -> dict:
    """容器级体检(不需要 ffmpeg)。`duration` 已扣掉不含音频的 Xing/Info 帧。"""
    frames = list(walk_frames(data))
    if not frames:
        return dict(ok=False, frames=0, audio_frames=0, duration=0.0, bitrate=[],
                    srate=[], channels=[], xing=False, cbr=False,
                    tail=len(data), obfuscated=False, id3=id3_len(data))
    brs = sorted({h['bitrate'] for _, h in frames})
    srs = sorted({h['srate'] for _, h in frames})
    chs = sorted({h['channels'] for _, h in frames})
    first_off, first_h = frames[0]
    head = data[first_off:first_off + first_h['size']]
    xing = (b'Xing' in head[:64]) or (b'Info' in head[:64])
    audio = len(frames) - (1 if xing else 0)
    last_off, last_h = frames[-1]
    return dict(ok=True, frames=len(frames), audio_frames=audio,
                duration=audio * first_h['samples'] / max(srs),
                bitrate=brs, srate=srs, channels=chs, xing=xing, cbr=len(brs) == 1,
                tail=len(data) - (last_off + last_h['size']),
                obfuscated=all(h['obfuscated'] for _, h in frames),
                id3=id3_len(data))


# ---------------------------------------------------------------- 槽位归族

def slot_family(slot: str) -> str | None:
    """`battle/skill_1` -> `skill_N`;`home/home_3` -> `home`;`ally/join` -> `join`。

    认不出来的返回 None(调用方按未知槽处理,不参与时长判据)。
    """
    if '/' not in slot:
        return None
    group, stem = slot.split('/', 1)
    if group == 'home':
        return 'home'
    if group == 'login':
        return 'login'
    if group == 'ally':
        return stem if stem in ('join', 'evolution') else None
    if group != 'battle':
        return None
    if stem in ENGINE_SINGLE_SLOTS:
        return 'skill_ready' if stem == 'skill_ready' else None
    m = re.fullmatch(r'(.+_)(\d+)', stem)
    if not m:
        return None
    fam = m.group(1) + 'N'
    return fam if fam in OFFICIAL_DURATION else None


def engine_reachable(slots: Sequence[str]) -> dict[str, list[str]]:
    """按 `generateVoicePaths` 的"遇缺即停"语义算出哪些 battle 文件永远播不到。

    返回 {'unreachable': [...], 'dead_prefix': [...]}。
    """
    battle = {s.split('/', 1)[1] for s in slots if s.startswith('battle/')}
    unreachable: list[str] = []
    dead: list[str] = []
    covered: set[str] = set(s for s in battle if s in ENGINE_SINGLE_SLOTS)
    for pref in ENGINE_BATTLE_PREFIXES:
        have = {}
        for stem in battle:
            m = re.fullmatch(re.escape(pref) + r'(\d+)', stem)
            if m:
                have[int(m.group(1))] = stem
        if not have:
            continue
        i = 0
        while i in have:
            covered.add(have[i])
            i += 1
        for k in sorted(have):
            if k >= i:
                unreachable.append('battle/' + have[k])
                covered.add(have[k])
    for stem in sorted(battle - covered):
        dead.append('battle/' + stem)
    return dict(unreachable=sorted(unreachable), dead_prefix=dead)


# ---------------------------------------------------------------- 门禁

@dataclass(frozen=True)
class VoiceFile:
    character: str          # code_name
    slot: str               # 相对 voice/ 的路径,不带 .mp3,如 `battle/skill_1`
    data: bytes


@dataclass(frozen=True)
class Finding:
    level: str              # 'error' | 'warn'
    rule: str
    character: str
    slot: str
    detail: str


def _fmt(v: float) -> str:
    return f'{v:.2f}s'


def check_container(vf: VoiceFile, info: dict) -> list[Finding]:
    out: list[Finding] = []
    mk = lambda lvl, rule, detail: Finding(lvl, rule, vf.character, vf.slot, detail)  # noqa: E731
    if not info['ok']:
        return [mk('error', 'unparsable', '走不出任何 mp3 帧(文件损坏或非 MPEG Layer3)')]
    if not info['obfuscated']:
        out.append(mk('error', 'not_obfuscated',
                      '帧头首字节不是 0x7F —— 客户端读的是混淆态,写回前必须 wf_assets.mp3_encode'))
    if info['srate'] != [OFFICIAL_SRATE]:
        out.append(mk('error', 'bad_srate', f"采样率 {info['srate']} ≠ 官方 {OFFICIAL_SRATE}(9048/9048)"))
    if info['channels'] != [OFFICIAL_CHANNELS]:
        out.append(mk('error', 'bad_channels', f"声道 {info['channels']} ≠ 官方单声道(9048/9048)"))
    if not info['cbr']:
        out.append(mk('error', 'not_cbr', f"帧码率不恒定 {info['bitrate']};客户端只支持 CBR"))
    elif info['bitrate'] != [OFFICIAL_BITRATE_KBPS]:
        out.append(mk('error', 'bad_bitrate',
                      f"{info['bitrate'][0]} kbps ≠ 官方 {OFFICIAL_BITRATE_KBPS} kbps(9048/9048)"))
    if info['tail'] not in OFFICIAL_TAIL_BYTES:
        out.append(mk('error', 'bad_tail',
                      f"帧流之后有 {info['tail']} 个杂字节;官方只有 0 或 128(ID3v1 TAG)"))
    return out


def check_duration(vf: VoiceFile, info: dict) -> list[Finding]:
    fam = slot_family(vf.slot)
    if fam is None or not info['ok']:
        return []
    _n, lo, _p50, p90, _p95, _p99, mx = OFFICIAL_DURATION[fam]
    dur = info['duration']
    if dur > mx:
        return [Finding('error', 'over_official_max', vf.character, vf.slot,
                        f'{_fmt(dur)} > 官方 {fam} 最大值 {_fmt(mx)}(×{dur / mx:.1f})')]
    if dur > p90:
        return [Finding('warn', 'over_official_p90', vf.character, vf.slot,
                        f'{_fmt(dur)} > 官方 {fam} p90 {_fmt(p90)}(最大值 {_fmt(mx)})')]
    if dur < lo:
        # 太短的一头也要报:听感就是"被切掉了"。只报 warn —— 短不会叠播,补不回来只能重录。
        return [Finding('warn', 'below_official_min', vf.character, vf.slot,
                        f'{_fmt(dur)} < 官方 {fam} 最小值 {_fmt(lo)}(中位 {_fmt(_p50)})')]
    return []


def check_duplicates(files: Sequence[VoiceFile]) -> list[Finding]:
    """跨角色逐字节相同 = error;同角色内多槽位共用 = warn(官方 9048 条零先例)。

    额外单列 `same_family_duplicate`:同一个序号族(`skill_N`/`win_N`/…)里出现逐字节
    相同的两条 —— 客户端是 `Std.random(list.length)` 随机抽
    (`MemberImpl.as` 播 `playSoundEffect(..., list[Std.random(list.length)])`),
    同族重复直接等于"同一个情境永远听到同一条",这正是作者说的"莫名其妙的循环"。
    """
    by_hash: dict[str, list[VoiceFile]] = {}
    for vf in files:
        by_hash.setdefault(hashlib.sha256(vf.data).hexdigest(), []).append(vf)
    out: list[Finding] = []
    for digest, group in sorted(by_hash.items()):
        if len(group) < 2:
            continue
        chars = {vf.character for vf in group}
        where = ', '.join(f'{vf.character}:{vf.slot}' for vf in sorted(
            group, key=lambda v: (v.character, v.slot)))
        if len(chars) > 1:
            out.append(Finding('error', 'cross_character_duplicate', sorted(chars)[0], '-',
                               f'{len(group)} 个槽位跨角色共用同一份字节({digest[:12]}): {where}'))
            continue
        head = sorted(group, key=lambda v: v.slot)[0]
        out.append(Finding('warn', 'intra_character_duplicate', head.character, head.slot,
                           f'{len(group)} 个槽位共用同一份字节({digest[:12]}): {where}'))
        fams: dict[str, list[str]] = {}
        for vf in group:
            fam = slot_family(vf.slot)
            if fam and fam.endswith('_N'):
                fams.setdefault(fam, []).append(vf.slot)
        for fam, slots in sorted(fams.items()):
            if len(slots) > 1:
                out.append(Finding('warn', 'same_family_duplicate', head.character,
                                   sorted(slots)[0],
                                   f'{fam} 族内 {len(slots)} 条逐字节相同({", ".join(sorted(slots))})'
                                   f' —— 客户端 Std.random 随机抽,等于该情境零变化'))
    return out


def check_reachability(files: Sequence[VoiceFile]) -> list[Finding]:
    out: list[Finding] = []
    by_char: dict[str, list[str]] = {}
    for vf in files:
        by_char.setdefault(vf.character, []).append(vf.slot)
    for char, slots in sorted(by_char.items()):
        r = engine_reachable(slots)
        for s in r['unreachable']:
            out.append(Finding('error', 'index_gap_unreachable', char, s,
                               'generateVoicePaths 遇缺号即 break,该文件永远播不到'))
        for s in r['dead_prefix']:
            out.append(Finding('warn', 'dead_prefix', char, s,
                               '不在引擎七前缀内(CharacterShortVoiceLogic),写了不会播'))
    return out


def check_voice_set(files: Iterable[VoiceFile]) -> list[Finding]:
    """一次跑完全部判据。返回按 (level, rule, character, slot) 排序的结论。"""
    files = list(files)
    out: list[Finding] = []
    for vf in files:
        info = probe(vf.data)
        out += check_container(vf, info)
        out += check_duration(vf, info)
    out += check_duplicates(files)
    out += check_reachability(files)
    order = {'error': 0, 'warn': 1}
    return sorted(out, key=lambda f: (order.get(f.level, 9), f.rule, f.character, f.slot))
