"""泽赫尔回旋斩：33%转速与重击，回旋伤害为原版202.5%，保留破弱点/fever总量。"""
from copy import deepcopy
from wf_zantetsu_fever_revision import nodes

TOTAL_DAMAGE_RATIO = 2.025


def stretched(frame):
    return frame*100//33


def slow_parts(parts):
    result=deepcopy(parts)
    if result.get('m'):
        raise ValueError('spin source unexpectedly contains independent movie clips')
    groups=result['g']; original=deepcopy(groups[0]); frames=int(original['t'])
    if not 1 <= frames <= 300:raise ValueError('unexpected spin duration')
    # GraphicsLoopKindTools: r top bits 0 = freeze at low-30-bit frame.
    # Cumulative integer boundaries implement 33% speed without timing drift.
    # Nested graphics retain their original time offsets and tween bitfields.
    for group in groups:
        for strip in group['s']:
            if (int(strip['s']) & 0xffffffff)>>30==2 and strip['i']==0:
                raise ValueError('source references root recursively')
    identity={'a':4096,'b':0,'c':0,'d':4096,'x':0,'y':0}
    if identity not in result['t']:result['t'].append(identity)
    matrix=result['t'].index(identity)
    groups[0]={'t':stretched(frames),'s':[{'s':-2147483648,'i':len(groups),
        'l':[{'m':(matrix<<12)|255,'t':stretched(f+1)-stretched(f),'r':f} for f in range(frames)]}]}
    groups.append(original)
    return result


def slow_timeline(timeline):
    result=deepcopy(timeline)
    if any(result.get(k) for k in ('points','circles','rectangles','matrices')):
        raise ValueError('unexpected collision or attachment timeline')
    for seq in result['sequences']:
        seq['begin']=stretched(seq['begin']-1)+1;seq['end']=stretched(seq['end'])
    for sound in result['sounds']:
        sound['begin']=stretched(sound['begin']-1)+1
        if sound['end']>=0:sound['end']=stretched(sound['end'])
    return result


def slow_attack(tree):
    result=deepcopy(tree)
    areas=nodes(result,'CreateHitArea')
    if not areas or areas[0][2]!=-18:raise ValueError('missing sword spin hit area')
    area=areas[0]
    if area[13][0]!='SpecifyHitAreaLifetimeDirectly' or area[14][0]!='CalculatedUsingMaxNumOfHits':
        raise ValueError('unexpected spin timing model')
    old=area[14][1]
    if old not in (9,12,15):raise ValueError('unexpected spin hit budget')
    new=old//3;area[14][1]=new
    radius_ratio={9:1.0,12:1.2,15:1.1}[old]
    if area[9][0]!='Circle':raise ValueError('unexpected spin hit shape')
    for value in area[9][1]:
        for key in ('min','max'):value[key]=round(value[key]*radius_ratio,6)
    effects=nodes(area[20],'ShowEffect')
    if len(effects)!=2:raise ValueError('expected blaze and spin effects')
    for effect in effects:
        if effect[12][0]!='Some':raise ValueError('missing effect scale')
        for value in effect[12][1]:
            for key in ('min','max'):value[key]=round(value[key]*radius_ratio,6)
    attacks=nodes(area[23],'CreateNormalAttack')
    if len(attacks)!=1:raise ValueError('expected one sword spin damage source')
    for col in (6,13,14):
        for value in attacks[0][col]:
            if set(value)!={'min','max'}:raise ValueError('unexpected variable-scaled hit value')
            for key in ('min','max'):
                value[key]=round(value[key]*old/new*(TOTAL_DAMAGE_RATIO if col==6 else 1),6)
    return result,dict(old_hits=old,new_hits=new,per_hit_ratio=old/new*TOTAL_DAMAGE_RATIO,
                       per_hit_break_fever_ratio=old/new,
                       lifetime_frames=area[13][1],total_damage_ratio=TOTAL_DAMAGE_RATIO,
                       radius_ratio=radius_ratio,radius=area[9][1][0]['max'])
