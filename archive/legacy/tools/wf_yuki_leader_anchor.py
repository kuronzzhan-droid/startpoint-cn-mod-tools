"""夏勇希的中心屏障与六向旋转结界使用同一个队伍球锚点。"""
from copy import deepcopy
from wf_seasonal7_kit_philia import cmds, dsl_gates, dsl_gate_failures


def revise_skill(source):
    tree = deepcopy(source)
    effects = [c for c in cmds(tree, 'ShowEffect')
               if c[2] == ['SpecifyEffectDirectly',
                           'battle/effect/skill_unique/psychic_yuki_swim_barrier/psychic_yuki_barrier']]
    if len(effects) != 1 or effects[0][3] not in (-17, -18):
        raise ValueError('center barrier source drift')
    effects[0][3] = -18
    if any(c[3] == -17 for c in cmds(tree, 'ShowEffect')):
        raise ValueError('remaining caster-anchored skill effect')
    # Yuki also uses FindCharactersBySkillTarget; its scoped validator knows
    # that command's two bound IDs (the Philia-specific walker does not).
    from wf_seasonal7_kit_yuki import scope_problems
    gates = dsl_gates(tree, element=1)
    gates['scope_strict'] = scope_problems(tree)
    if failures := dsl_gate_failures(gates):
        raise ValueError(failures)
    return tree
