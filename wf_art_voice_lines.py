"""本轮五角色日语重录台词与纯数据生成计划；不写游戏目录。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROLES = {
    'bianca': ('119989', 'lady_summoner_campus', '沉稳温和的成年女性声音，知性的大学教师，富有自信与亲和力，自然清晰的日语发音'),
    'celtie': ('149989', 'wind_spgirl_campus', '开朗明亮的成年女性声音，热爱摄影的大学生，礼貌率真而富有行动力，自然清晰的日语发音'),
    'nephtim': ('169989', 'ruin_girl_campus', '清澈平静的成年女性声音，喜欢咖啡店和奶茶的大学生，简洁冷静，感情细腻，自然清晰的日语发音'),
    'lion': ('119996', 'lion_swordman_reborn', '低沉浑厚的成年男性声音，阅历丰富的狮王战士，沉着坚毅，温情含蓄，自然清晰的日语发音'),
    'ginovi': ('169999', 'ginovi', '低沉清晰的成年男性声音，黑鸦护卫，冷静克制，言语简短有力，对珍视之人温柔而可靠，自然清晰的日语发音'),
}

# 第二准备音使用原生 matched_skill_ready 单独槽位；实际战斗切换条件另行接线。
ADDITIONS = {
    'bianca': [
        ('battle/matched_skill_ready', 'アプロ、出番よ。', '阿普罗，该你登场了。'),
        ('battle/skill_2', 'アプロ、空から照らして！', '阿普罗，从空中照亮大家！'),
        ('battle/skill_3', 'さあ、炎の実習よ！', '来吧，开始火焰实习！'),
    ],
    'celtie': [
        ('battle/matched_skill_ready', 'とびきりの一枚を！', '拍下最出色的一张！'),
        ('battle/skill_2', 'きらめく風よ、十字に舞え！', '闪耀的风啊，交错飞舞吧！'),
        ('battle/skill_3', 'この瞬間を、逃しません！', '我不会错过这一刻！'),
    ],
    'nephtim': [
        ('battle/matched_skill_ready', '次の一杯、用意した。', '下一杯，准备好了。'),
        ('battle/skill_2', '光と影、巡り合わせる。', '让光与影交替相逢。'),
        ('battle/skill_3', '星空のひととき、君と。', '这片星空，与你共度。'),
    ],
}

LION = [
    ('home/hokanoshishizokunado', '昔の炎は、奪うためのものだった。今は違う。この背に頼る者がいる限り、俺の火は消えん。お前も、覚えておけ。', '昔日的火焰只会夺走一切。如今不同了。只要还有人依靠这道背影，我的火就不会熄灭。你也记住。'),
    ('home/shieiron_aa', 'この白い服か。戦場には目立ちすぎると思ったが、悪くはない。……胸の薔薇？それは、俺が選んだ。文句があるか。', '这身白衣？本以为在战场上太显眼，倒也不坏。……胸前的蔷薇？那是我自己选的。你有意见？'),
    ('home/orenomiteita', '罪が消えたとは思わん。それでも、立ち止まる理由にはしない。明日を望む者のために、今日の剣を振るう。それだけだ。', '我不认为罪孽已经消失。但那不再是停步的理由。为盼望明日之人挥出今日之剑，仅此而已。'),
    ('home/teo_omaewa', 'テオには、好きな道を歩かせてやりたい。俺の背を追う必要はない。……お前もだ。迷った時だけ、ここへ戻ってくればいい。', '我想让提欧走自己喜欢的路，不必追随我的背影。……你也一样。只在迷茫的时候，回到这里就好。'),
    ('home/sakewairan', '酒より、温かい茶にしろ。長い一日のあとには、そのほうがいい。……二人分、用意してある。座れ。今は急がん。', '比起酒，还是喝杯热茶吧。漫长的一天结束后，这样更好。……准备了两人份。坐下，现在不急。'),
    ('home/honwakiraijanai', '英雄譚の終わりには、いつも平穏な朝が来る。昔は剣ばかり見ていたが……今は、その朝を守りたいと思う。', '英雄故事的结尾，总会迎来平静的清晨。过去我只在意剑……如今，却想守住那个清晨。'),
    ('battle/skill_ready', 'この剣に、集え。', '汇聚于这柄剑吧。'),
    ('battle/matched_skill_ready', '火は、消えていない。', '火，还没有熄灭。'),
    ('battle/skill_0', '燃え上がれ、獅子の炎！', '熊熊燃烧吧，雄狮之炎！'),
    ('battle/skill_1', 'この背の火は、消させん！', '我不会让身后的火熄灭！'),
    ('battle/skill_2', '道を開け、紅蓮の剣！', '开辟道路吧，红莲之剑！'),
    ('battle/skill_3', 'ここから先は、俺が守る！', '从这里开始，由我守护！'),
]

GINOVI = [
    ('ally/join', '基诺維だ。今度の契約は、俺が選んだ。お前の帰る場所を守る。それが、俺の仕事だ。', '我是基诺维。这次的契约，是我自己选的。守住你的归处，就是我的工作。'),
    ('ally/evolution', 'もう鎖はない。この翼も、この刃も、俺自身のものだ。だから、ここにいる。お前を守るためにな。', '枷锁已经不在。这双羽翼、这把刀刃，都属于我自己。所以我会留在这里，守护你。'),
    ('home/home_0', '眠れ。外は俺が見ている。この目は、かつて獲物を探すためにあった。今は、お前の帰り道を確かめるためにある。', '睡吧，外面有我。这双眼曾用来搜寻猎物，如今只是为了确认你的归路。'),
    ('home/home_1', '契約書に、守りたい理由は書かれていない。必要もないだろう。……お前が無事なら、それで十分だ。', '契约书上没有写想要守护的理由，也没那个必要。……只要你平安，就足够了。'),
    ('home/home_2', '気配を消すのは得意だ。だが、お前の隣では、どうも調子が狂う。……心配するな。嫌だとは、言っていない。', '我擅长隐匿气息，可一到你身旁就有些失常。……别担心，我没说讨厌这样。'),
    ('home/home_3', 'この黒い羽を持っていろ。不吉かどうかは、使い方次第だ。危険な時は、高く掲げろ。必ず、見つける。', '带上这根黑羽。是不是不祥，要看如何使用。遇到危险时，把它举高。我一定会找到你。'),
    ('home/home_4', '今日は、刃を休ませる日か。なら、茶を一杯。……お前も座れ。話はなくていい。こういう静けさも、悪くない。', '今天是让刀刃休息的日子吗，那就喝杯茶吧。……你也坐下，不必找话说。这样的宁静也不错。'),
    ('battle/battle_start_0', '俺の後ろにいろ。', '待在我身后。'),
    ('battle/battle_start_1', '退路は、確保した。', '退路，已经确保。'),
    ('battle/outhole_0', 'まだ、守れる。', '我还能守住。'),
    ('battle/power_flip_0', '逃がさん。', '休想逃走。'),
    ('battle/power_flip_1', 'そこだ。', '在那里。'),
    ('battle/power_flip_2', '貫け。', '贯穿。'),
    ('battle/skill_ready', 'いつでも、行ける。', '随时可以出发。'),
    ('battle/matched_skill_ready', '刃は、研ぎ澄んだ。', '刀刃，已磨砺完毕。'),
    ('battle/skill_0', '黒い翼よ、道を開け！', '黑翼啊，开辟道路！'),
    ('battle/skill_1', 'この刃は、守るために！', '这道刀锋，为守护而挥！'),
    ('battle/skill_2', '影を裂け、黒鴉！', '撕裂暗影吧，黑鸦！'),
    ('battle/skill_3', 'お前には、触れさせない！', '绝不让你碰到！'),
    ('battle/win_0', '終わった。怪我はないか。', '结束了。没受伤吧？'),
    ('battle/win_1', '帰ろう。俺も、一緒に。', '回去吧。我也一起。'),
]


def _new_rows(rows):
    return [dict(slot=slot, ja=ja, zh=zh, direction='自然克制的角色对白。',
                 reference_slot='battle/skill_ready') for slot, ja, zh in rows]


def script_rows(draft_root: Path):
    """输入已审核校园台词目录；返回全部 102 条新的、独立的槽位记录。"""
    result = []
    for role in ROLES:
        if role in ADDITIONS:
            rows = json.loads((draft_root / role / 'lines.json').read_text(encoding='utf-8'))
            rows += _new_rows(ADDITIONS[role])
        else:
            rows = _new_rows(LION if role == 'lion' else GINOVI)
        for row in rows:
            row = dict(row, role=role, persona=ROLES[role][2])
            # 特制名字用标准假名朗读；字幕保留角色正式名字。
            if role == 'ginovi':
                row['ja'] = row['ja'].replace('基诺維', 'ギノヴィ')
            if role == 'bianca' and row['slot'] == 'battle/skill_1':
                row.update(ja='小さな竜よ、炎で導いて！', zh='小龙啊，用火焰指引大家！')
            if role == 'nephtim' and row['slot'] == 'battle/skill_0':
                row.update(ja='星の光、道をひらく。', zh='星光啊，开辟道路。')
            slot = row['slot']
            if 'ready' in slot:
                timing = '准备提示，目标1.2至2.2秒，紧凑清晰，尾音自然收住。'
            elif slot.startswith('battle/skill_'):
                timing = '战斗发动，坚定有力，目标1.8至3.8秒。'
            elif slot.startswith('battle/win_'):
                timing = '完整胜利台词，自然清晰，按句子长度约2至6秒。'
            elif slot.startswith('battle/'):
                timing = '简洁战斗语音，短句紧凑清晰，目标1至3秒。'
            else:
                timing = '从容自然，句间短暂换气，不额外停顿，不拖长尾音。'
            row['direction'] += ' ' + timing
            result.append(row)
    if len(result) != 102 or len({(x['role'], x['slot']) for x in result}) != 102:
        raise ValueError('unexpected full-set voice coverage')
    return result


def make_plan(draft_root: Path, references: dict):
    rows = script_rows(draft_root)
    for row in rows:
        row['references'] = references[row['role']]
        for ref in row['references']:
            if hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest() != ref['sha256']:
                raise ValueError('reference hash drift')
    return rows
