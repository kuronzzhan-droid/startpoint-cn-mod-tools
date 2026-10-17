"""已安装十五位小Boss角色的固定身份；蒸汽机兵不在本批。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Character:
    cid: str
    code: str
    name: str
    group: str
    uid: int
    layers: int
    role: str

    @property
    def package_id(self):
        return "genin" if self.cid == "169993" else self.code


ROSTER = tuple(Character(*row) for row in (
    ("129998", "ghost_girl_playable", "水灵幽魂", "Blue", 1299980, 8, "人魂积蓄与强化弹射追击"),
    ("139996", "cube_boss_playable", "机枪魔块·雷", "Yellow", 1399960, 3, "火控锁定与僚机弹幕"),
    ("129996", "clione_playable", "蓝色海妖", "Blue", 1299960, 3, "承伤、治疗与水直击援护"),
    ("149994", "one_eyed_rabbit_playable", "风暴恶魔拉比", "Green", 1499940, 8, "贯穿爪击与岚痕"),
    ("159999", "security_robot_playable", "Sec-2600Li", "White", 1599990, 1, "掩护、眩晕与重整"),
    ("129995", "wander_armor_water_playable", "彷徨铠甲·水", "Blue", 129995, 12, "受击成长与装甲刻痕"),
    ("149993", "haniwa_green_playable", "哈宁绿", "Green", 1499930, 6, "碰撞筑墙与队伍防护"),
    ("119995", "dog_soldier_playable", "炎枪见习兵", "Red", 1199950, 5, "连击推进与战意"),
    ("149992", "wander_armor_wind_playable", "彷徨铠甲·风", "Green", 149992, 10, "浮游直击与乘风刻"),
    ("129994", "haniwa_blue_playable", "哈宁蓝Z", "Blue", 1299940, 5, "多重攻击强化与补时"),
    ("119993", "cobra_playable", "红蝮蛇", "Red", 1199930, 5, "减益条数与毒环"),
    ("129993", "killer_whale_playable", "冰冻虎鲸", "Blue", 1299930, 5, "冻结、多目标与涨潮"),
    ("169993", "genin_playable", "黑之下忍", "Black", 1699930, 5, "影层数与毒刃追斩"),
    ("149991", "big_bear_monster_playable", "疾风狂熊", "Green", 1499910, 7, "限层怒攻与山鸣"),
    ("119994", "haniwa_playable", "哈宁红Z", "Red", 1199940, 5, "追加直击与窑火"),
))
BY_ID = {char.cid: char for char in ROSTER}
