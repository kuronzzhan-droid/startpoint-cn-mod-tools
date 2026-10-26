"""火属性三套：连击、敌方减益、追加直击。"""
from wf_miniboss_rows import event as e, ongoing as o


def soldier(k):
    slots = [
        [k.i(226, 300, trigger=e(26)), k.gain(2, trigger=e(23)),
         k.gain(trigger=e(65))],
        [k.i(211, 70), k.team(32, 80)],
        [k.d(23, 40), k.i(696, 15), k.i(226, 2000, trigger=e(23))],
        [k.i(35, 5), k.i(227, 15)],
        [k.team(211, 5, trigger=e(12, every=30, ct=15))],
        [k.i(205, 25), k.i(211, 5, trigger=e(23, ct=15))],
    ]
    leader = [k.team(32, 100), k.i(55, 120), k.team(205, 20),
              k.i(226, 500, trigger=e(23))]
    return k.finish(slots, leader)


def cobra(k):
    debuff = o(136, limit=6)
    slots = [
        [k.i(211, 75), k.gain(2, trigger=e(23)), k.team(35, 5)],
        [k.d(258, 15, debuff)],
        [k.team(199, 150), k.team(559, 40)],
        [k.i(391, -15, trigger=e(2, ct=10), duration=9),
         k.i(393, -5, trigger=e(2, ct=10), duration=9),
         k.gain(trigger=e(2, ct=5))],
        [k.d(3, 3), k.team(37, 20),
         k.i(211, 5, trigger=e(20, every=25, puller=7, group=k.group, ct=15))],
        [k.team(694, 15), k.i(211, 5, trigger=e(23, ct=15))],
    ]
    leader = [k.team(32, 80), k.team(491, 60), k.team(34, 100), k.team(205, 15)]
    return k.finish(slots, leader)


def red(k):
    slots = [
        [k.i(211, 70), k.i(211, 5, trigger=e(20, every=30, puller=7, group=k.group, ct=15)),
         k.gain(2, trigger=e(23))],
        [k.d(0, 80, o(73)),
         k.gain(trigger=e(20, every=30, puller=7, group=k.group, ct=2))],
        [k.team(202, 0), k.d(1, 40)],
        [k.i(35, 5), k.i(211, 5, trigger=e(74, ct=15))],
        [k.team(205, 20), k.team(37, 20), k.i(227, 10, trigger=e(23, ct=5))],
        [k.team(693, 15), k.team(206, 3, trigger=e(2, ct=4))],
    ]
    leader = [k.team(32, 80), k.team(33, 140), k.i(55, 80), k.team(205, 15)]
    return k.finish(slots, leader)


BUILDERS = {"119995": soldier, "119993": cobra, "119994": red}
