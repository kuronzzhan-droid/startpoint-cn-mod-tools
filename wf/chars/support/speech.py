"""Production primitives extracted from wf_seasonal7_voice.py (C baseline)."""
from __future__ import annotations
HOME_SLOTS = tuple(f'home/home_{i}' for i in range(6))


ALL_SLOTS = ('ally/join', 'ally/evolution',
             *(f'home/home_{i}' for i in range(10)),
             *(f'battle/battle_start_{i}' for i in range(4)),
             'battle/skill_ready', 'battle/matched_skill_ready',
             *(f'battle/skill_{i}' for i in range(8)),
             *(f'battle/matched_skill_{i}' for i in range(4)),
             'battle/power_flip_0', 'battle/power_flip_1',
             'battle/outhole_0', 'battle/outhole_1',
             'battle/win_0', 'battle/win_1')


SUBTITLE_MAX = 82          # 官方 home 字幕最长 82 字；气泡不缩字、不截断


SUBTITLE_MAX_LINES = 4


def check_subtitle(text: str) -> None:
    visible = text.replace('\n', '')
    if not visible:
        raise ValueError('empty subtitle')
    if len(visible) > SUBTITLE_MAX:
        raise ValueError(f'subtitle exceeds {SUBTITLE_MAX} characters ({len(visible)}): {visible[:20]}…')
    if text.count('\n') + 1 > SUBTITLE_MAX_LINES:
        raise ValueError(f'subtitle exceeds {SUBTITLE_MAX_LINES} lines')


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
