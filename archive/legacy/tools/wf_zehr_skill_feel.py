"""泽赫尔出手短顿：保留15帧停球，后续攻击不锁住弹射队伍。"""
from copy import deepcopy


def revise_skill(tree):
    from wf_seasonal7_kit_philia import cmds
    out = deepcopy(tree)
    stops = cmds(out, 'StopBall')
    if len(stops) != 1 or stops[0][1:3] not in ([-18, 60], [-18, 15]):
        raise ValueError('Zehr skill stop drift')
    stops[0][2] = 15
    return out
