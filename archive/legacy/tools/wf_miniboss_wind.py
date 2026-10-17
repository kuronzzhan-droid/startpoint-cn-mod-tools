"""四位风属性小Boss：贯穿、浮游、防护、怒攻互不复制。"""
from wf_miniboss_rows import event as e, ongoing as o


def rabbit(k):
    pierce = o(30)
    slots = [
        [k.i(211, 75), k.i(26, duration=8, trigger=e(65)),
         k.gain(2, trigger=e(23)), k.gain(trigger=e(65))],
        [k.d(0, 80, pierce), k.d(1, 80, pierce)],
        [*(k.helper(f"claw_lv{n}", trigger=e(62 + n)) for n in (1, 2, 3)),
         k.d(410, 15, pierce), k.d(23, 100, pierce)],
        [k.i(190, 25), k.d(3, 2.5, target=0)],
        [k.team(53, 25), k.i(51, 50), k.i(205, 20)],
        [k.i(211, 5, pre=k.has(8), trigger=e(2, ct=15)),
         k.i(211, 5, trigger=e(20, every=20, ct=15, puller=7, group=k.group))],
    ]
    leader = [k.team(32, 100), k.team(33, 140), k.i(190, 20), k.team(211, 30)]
    return k.finish(slots, leader)


def green(k):
    slots = [
        [k.i(211, 70), k.gain(2, trigger=e(23))],
        [k.gain(trigger=e(197, every=4, ct=1)),
         k.team(227, 3, trigger=e(197, every=4, ct=3))],
        [k.d(2, 30), k.d(0, 15), k.team(694, 15)],
        [k.team(36, 20), k.team(205, 20)],
        [k.team(211, 5, trigger=e(197, every=8, ct=15)),
         k.team(206, 5, trigger=e(23, ct=5))],
        [k.d(3, 5, o(134, uid=k.uid, count=6, limit=1)), k.i(35, 5)],
    ]
    leader = [k.team(32, 80), k.team(34, 100), k.team(205, 25), k.team(36, 10)]
    return k.finish(slots, leader)


def armor(k):
    flying = o(31)
    slots = [
        [k.i(211, 75), k.gain(2, trigger=e(23)),
         k.gain(trigger=e(52, ct=6))],
        [k.d(1, 18.5), k.team(39, 20)],
        [k.d(0, 100, flying), k.d(410, 15, flying), k.team(201, 0)],
        [k.i(191, 30), k.team(206, 3, trigger=e(236, held_seconds=5))],
        [k.d(3, 5, flying), k.team(211, 5, trigger=e(52, ct=15))],
        [k.i(205, 25), k.i(211, 5, trigger=e(23, ct=15))],
    ]
    leader = [k.team(32, 80), k.d(1, 140, flying), k.i(191, 20), k.team(211, 30)]
    return k.finish(slots, leader)


def bear(k):
    slots = [
        [k.gain(3), k.gain(2, trigger=e(23)),
         k.gain(trigger=e(21, every=3, ct=1))],
        [k.i(211, 75), k.i(211, 5, trigger=e(23, ct=15)), k.i(205, 30)],
        [k.d(0, 20, target=0), k.d(1, 20, target=0)],
        [k.d(45, 0, o(134, uid=k.uid, count=7, limit=1), target=0), k.i(35, 5)],
        [k.d(410, 15, o(134, uid=k.uid, count=7, limit=1), target=0),
         k.i(206, 5, trigger=e(21, every=5, ct=3))],
        [k.i(36, 20), k.i(206, 10, trigger=e(23, ct=5))],
    ]
    leader = [k.team(32, 100), k.team(33, 100), k.team(157, 20), k.team(205, 15)]
    return k.finish(slots, leader)


BUILDERS = {"149994": rabbit, "149993": green, "149992": armor, "149991": bear}
