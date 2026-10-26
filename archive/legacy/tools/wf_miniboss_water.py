"""五位水属性小Boss：主动资源保持，六能力各走不同机制。"""
from wf_miniboss_rows import event as e, ongoing as o


def ghost(k):
    slots = [
        [k.i(211, 75), k.gain(2, trigger=e(23)), k.gain(trigger=e(65))],
        [k.d(2, 20), k.i(205, 20)],
        [*(k.helper(f"hitodama_lv{n}", trigger=e(62 + n)) for n in (1, 2, 3)),
         k.team(694, 15)],
        [k.i(35, 5), k.i(211, 5, trigger=e(2, ct=15)),
         k.i(211, 5, trigger=e(23, ct=15))],
        [k.d(258, 10, o(136, limit=5)), k.team(119, 70)],
        [k.team(36, 10), k.team(206, 5, trigger=e(23, ct=5)),
         k.d(3, 5, o(134, uid=k.uid, count=8, limit=1), target=0)],
    ]
    leader = [k.team(32, 100), k.team(34, 120), k.team(211, 30), k.team(119, 30)]
    return k.finish(slots, leader)


def clione(k):
    slots = [
        [k.i(462, 30, target=1), k.gain(3, trigger=e(23)), k.team(195, 20)],
        [k.team(206, 4, trigger=e(21, every=3, ct=2)),
         k.team(0, 60, trigger=e(23), duration=12)],
        [k.d(1, 50), k.d(0, 20), k.team(202, 0)],
        [k.i(211, 60), k.i(35, 5), k.i(211, 5, trigger=e(19, ct=15))],
        [k.i(205, 30), k.team(36, 15), k.team(227, 5, trigger=e(23, ct=5))],
        [k.team(693, 15), k.team(206, 5, trigger=e(23, ct=5))],
    ]
    leader = [k.team(32, 80), k.team(33, 120), k.team(195, 15), k.team(205, 20)]
    return k.finish(slots, leader)


def armor(k):
    slots = [
        [k.i(211, 70), k.gain(trigger=e(21, every=3)), k.i(462, 30, target=1)],
        [k.d(0, 10), k.i(211, 5, trigger=e(21, every=3, ct=15))],
        [k.i(252, 800, trigger=e(21, every=5, ct=5), extra={"time": "(None)"}),
         k.d(154, 80, o(134, uid=k.uid, count=12, limit=1))],
        [k.team(37, 25), k.i(205, 35), k.i(206, 5, trigger=e(21, every=5, ct=5))],
        [k.team(388, 80), k.team(211, 5, pre=k.has(12), trigger=e(2, ct=15))],
        [k.team(695, 15), k.i(211, 5, trigger=e(23, ct=15))],
    ]
    leader = [k.team(32, 80), k.team(34, 80), k.team(37, 20), k.team(205, 20)]
    return k.finish(slots, leader)


def blue(k):
    buffs = o(38, puller=5, group=k.group, limit=6)
    slots = [
        [k.i(211, 75), k.gain(2, trigger=e(23))],
        [k.team(157, 25), k.i(211, 5, target=7, trigger=e(30, puller=5, group=k.group, ct=15))],
        [k.d(0, 20, buffs, target=7), k.d(1, 25, buffs, target=7)],
        [k.team(205, 20), k.team(206, 5, trigger=e(23, ct=5)),
         k.team(227, 5, trigger=e(23, ct=5))],
        [k.d(3, 5, o(134, uid=k.uid, count=5, limit=1)), k.gain(trigger=e(2, ct=3))],
        [k.team(693, 15), k.i(211, 5, trigger=e(23, ct=15))],
    ]
    leader = [k.team(32, 80), k.team(33, 100), k.team(157, 20), k.team(211, 30)]
    return k.finish(slots, leader)


def whale(k):
    slots = [
        [k.d(0, 10, o(64, limit=5)), k.i(211, 70)],
        [k.d(3, 3), k.i(211, 5, trigger=e(20, every=30, puller=7, group=k.group, ct=15))],
        [k.team(538, 150), k.team(694, 15),
         k.i(226, 1500, trigger=e(23)), k.gain(2, trigger=e(23))],
        [k.team(288, 15), k.team(195, 15), k.team(206, 3, trigger=e(2, ct=4))],
        [k.team(119, 75), k.gain(trigger=e(2, ct=3))],
        [k.i(211, 5, trigger=e(23, ct=15)), k.i(205, 25)],
    ]
    leader = [k.team(32, 80), k.team(34, 100), k.team(119, 30), k.team(211, 30)]
    return k.finish(slots, leader)


BUILDERS = {"129998": ghost, "129996": clione, "129995": armor,
            "129994": blue, "129993": whale}
