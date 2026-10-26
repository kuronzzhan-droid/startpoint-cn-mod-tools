((root)=>{
  'use strict';
  const T=typeof module!=='undefined'&&module.exports?require('./battle-targets.js'):root.WFBattleTargets;
  const emit=(s,type,extra={})=>({id:s.nextEventId++,tick:s.tick,type,...extra});
  const entity=(s,id)=>s.units.find(e=>e.id===id)||s.enemies.find(e=>e.id===id);
  const modifier=(e,type,tick)=>Math.max(0,...(e.statuses||[]).filter(b=>b.type===type&&b.until>tick).map(b=>b.ratio||0));
  function hurt(s,target,amount,sourceId,events) {
    if(!target||target.hp<=0)return false;
    amount=Math.max(0,Math.min(1e9,amount));
    const shields=(target.statuses||[]).filter(b=>b.type==='shield'&&b.until>s.tick),shield=Math.max(0,...shields.map(b=>b.remaining||0));
    const absorb=Math.min(amount,shield);for(const b of shields)b.remaining=Math.max(0,b.remaining-absorb);
    target.hp=Math.max(0,target.hp-amount+absorb);
    const source=entity(s,sourceId);
    events.push(emit(s,'damage',{entityId:sourceId,characterId:source?.characterId,targetId:target.id,value:amount-absorb,absorbed:absorb,
      sourcePosition:source?{x:source.x,y:source.y}:undefined,position:{x:target.x,y:target.y}}));return true;
  }
  function targets(s,caster,phase) {
    const chosen=T.select(s,caster,phase.selector),g=phase.geometry||{kind:'single',center:'target'};
    if(!chosen.length)return {targets:[],origin:T.origin(g,caster,caster)};
    const origin=T.origin(g,caster,chosen[0]);
    const pool=g.kind==='single'?chosen:(phase.selector.team==='ally'?s.units:s.enemies).filter(e=>e.hp>0&&T.contains(g,origin,e)
      &&(!Number.isFinite(phase.selector.hpBelow)||e.hp/e.maxHp<phase.selector.hpBelow)
      &&(!phase.selector.elements?.length||phase.selector.elements.includes(s.content.characters[e.characterId]?.element)));
    return {targets:pool,origin};
  }
  const valid=(target,effect)=>target.hp>0&&(effect.type!=='heal'||target.hp<target.maxHp);
  function planCast(s,unitId) {
    const caster=s.units.find(u=>u.id===unitId&&u.hp>0);if(!caster)return null;
    const skill=s.content.characters[caster.characterId].skill;
    const phases=skill.phases.map((phase,index)=>{const found=targets(s,caster,phase);return {...phase,index,
      targets:found.targets.map(t=>t.id),origin:found.origin,possible:found.targets.some(t=>phase.effects.some(e=>valid(t,e)))};});
    for(const phase of phases){
      if(Number.isInteger(phase.requiresHit))phase.possible=phase.possible&&Boolean(phases[phase.requiresHit]?.possible&&phases[phase.requiresHit]?.effects.some(e=>e.type==='damage'));
      if(phase.impactFrom?.length)phase.possible=phase.impactFrom.some(i=>phases[i]?.possible&&phases[i]?.effects.some(e=>e.type==='damage'));
      if(phase.hitTargetsFrom?.length)phase.possible=phase.hitTargetsFrom.some(i=>phases[i]?.possible&&phases[i]?.effects.some(e=>e.type==='damage'));
    }
    return phases.some(p=>p.possible)?{casterId:unitId,characterId:caster.characterId,skill,phases}:null;
  }
  function startCast(s,plan) {
    const castId=s.nextEventId++,hits={},hitTargets={},impacts={},caster=entity(s,plan.casterId),casterOrigin={x:caster.x,y:caster.y};
    for(const p of plan.phases)s.effects.push({kind:'phase',due:s.tick+Math.round(p.offset*20),casterId:plan.casterId,characterId:plan.characterId,castId,hits,hitTargets,impacts,casterOrigin,phase:p});
    return [emit(s,'cast',{entityId:plan.casterId,characterId:plan.characterId,position:{...casterOrigin}})];
  }
  function apply(s,target,e,owner,events) {
    if(!target||target.hp<=0)return;
    if(e.type==='damage'||e.type==='dot') {hurt(s,target,e.amount||0,owner.casterId,events);return;}
    if(e.type==='heal') {
      const amount=((e.amount||0)+(e.ratio||0)*target.maxHp)*(1-modifier(target,'healReduction',s.tick));
      const healed=Math.min(amount,target.maxHp-target.hp);target.hp+=healed;
      const source=entity(s,owner.casterId);
      if(healed>0)events.push(emit(s,'heal',{entityId:owner.casterId,characterId:source?.characterId,targetId:target.id,value:healed,
        sourcePosition:source?{x:source.x,y:source.y}:undefined,position:{x:target.x,y:target.y}}));return;
    }
    const key=`${owner.casterId}:${e.type}`;target.statuses||=[];target.statuses=target.statuses.filter(b=>b.key!==key);
    target.statuses.push({...e,key,sourceId:owner.casterId,until:s.tick+Math.round((e.duration||5)*20),
      remaining:e.type==='shield'?Math.min(1e9,(e.amount||0)+(e.ratio||0)*target.maxHp):undefined,procs:0});
    events.push(emit(s,'buff',{entityId:owner.casterId,targetId:target.id,value:e.type,position:{x:target.x,y:target.y}}));
  }
  function phaseStep(s,job,events) {
    const caster=entity(s,job.casterId),p=job.phase;
    if(p.requiresCasterAlive!==false&&(!caster||caster.hp<=0))return;
    if(Number.isInteger(p.requiresHit)&&!job.hits[p.requiresHit])return;
    let ids=p.targets,origin=p.origin;
    if(p.retarget&&caster?.hp>0){const found=targets(s,caster,p);ids=found.targets.map(t=>t.id);origin=found.origin;}
    let origins=[origin];
    if(p.geometry?.kind!=='single')ids=(p.selector.team==='ally'?s.units:s.enemies).filter(t=>t.hp>0
      &&(!p.selector.elements?.length||p.selector.elements.includes(s.content.characters[t.characterId]?.element))
      &&(!Number.isFinite(p.selector.hpBelow)||t.hp/t.maxHp<p.selector.hpBelow)
      &&T.contains(p.geometry,origin,t)).map(t=>t.id);
    if(p.impactFrom?.length){
      const points=p.impactFrom.flatMap(i=>job.impacts[i]||[]);if(!points.length)return;
      const unique=[...new Map(points.map(point=>[`${point.x},${point.y}`,point])).values()];
      origins=(p.impactMode==='farthest'?unique.sort((a,b)=>T.distance(job.casterOrigin,b)-T.distance(job.casterOrigin,a)).slice(0,1):unique).map(point=>({...point,dx:0,dy:-1}));
      const pool=p.selector.team==='ally'?s.units:s.enemies;ids=pool.filter(t=>t.hp>0
        &&(!p.selector.elements?.length||p.selector.elements.includes(s.content.characters[t.characterId]?.element))
        &&(!Number.isFinite(p.selector.hpBelow)||t.hp/t.maxHp<p.selector.hpBelow)
        &&origins.some(o=>T.contains(p.geometry,o,t))).map(t=>t.id);
    }
    if(p.hitTargetsFrom?.length){
      ids=[...new Set(p.hitTargetsFrom.flatMap(i=>job.hitTargets[i]||[]))].filter(id=>entity(s,id)?.hp>0);
      if(!ids.length)return;
    }
    for(const effect of p.effects) {
      const e={...effect};if(['damage','dot'].includes(e.type))e.amount=(e.amount||0)*(1+modifier(caster||{},'attackUp',s.tick));
      if(e.type==='dot'||(e.type==='heal'&&e.duration>0)) {
        const interval=Math.max(1,Math.round((e.interval||1)*20)),count=Math.max(1,Math.floor(e.duration*20/interval));
        if(e.type==='dot'&&e.targetMode==='attached'){
          for(const old of s.effects)if(old.kind==='periodic'&&old.castId===job.castId&&old.casterId===job.casterId&&old.effect.type==='dot'&&old.effect.targetMode==='attached')old.targets=old.targets.filter(id=>!ids.includes(id));
          s.effects=s.effects.filter(old=>old.kind!=='periodic'||old.effect.targetMode!=='attached'||old.targets.length);
        }
        s.effects.push({kind:'periodic',due:s.tick+interval,interval,left:count,casterId:job.casterId,castId:job.castId,
          targets:[...ids],geometry:p.geometry,origins,team:p.selector.team,elements:p.selector.elements,hpBelow:p.selector.hpBelow,effect:{...e,amount:(e.amount||0)/count,ratio:(e.ratio||0)/count},
          requiresCasterAlive:e.requiresCasterAlive===true});
      }else for(const id of ids) {
        const target=entity(s,id);if(!target||!valid(target,e))continue;
        apply(s,target,e,job,events);if(e.type==='damage'){job.hits[p.index]=true;(job.hitTargets[p.index]||=[]).push(id);(job.impacts[p.index]||=[]).push({x:target.x,y:target.y});}
      }
    }
  }
  function advance(s) {
    const events=[],due=s.effects.filter(e=>e.due<=s.tick);s.effects=s.effects.filter(e=>e.due>s.tick);
    for(const job of due) {
      if(job.kind==='phase'){phaseStep(s,job,events);continue;}
      if(job.requiresCasterAlive&&!s.units.some(u=>u.id===job.casterId&&u.hp>0))continue;
      const ids=job.effect.targetMode==='attached'||job.geometry?.kind==='single'?job.targets:(job.team==='ally'?s.units:s.enemies).filter(t=>t.hp>0
        &&(!Number.isFinite(job.hpBelow)||t.hp/t.maxHp<job.hpBelow)
        &&(!job.elements?.length||job.elements.includes(s.content.characters[t.characterId]?.element))
        &&job.origins.some(o=>T.contains(job.geometry,o,t))).map(t=>t.id);
      for(const id of ids)apply(s,entity(s,id),job.effect,job,events);
      if(--job.left>0){job.due+=job.interval;s.effects.push(job);}
    }
    for(const unit of s.units) {
      unit.statuses=(unit.statuses||[]).filter(b=>b.until>s.tick&&(!b.requiresCasterAlive||s.units.some(u=>u.id===b.sourceId&&u.hp>0)));
      if(unit.hp<=0||s.tick<unit.nextActionTick)continue;
      const def=s.content.characters[unit.characterId],heal=def.role==='healer';
      const target=T.select(s,unit,{team:heal?'ally':'enemy',kind:heal?'lowestHp':'nearest',range:def.stats.range})[0];
      if(!target||(heal&&target.hp>=target.maxHp))continue;
      unit.nextActionTick=s.tick+Math.max(4,Math.round(def.stats.interval*20/(1+modifier(unit,'haste',s.tick))));
      if(heal)apply(s,target,{type:'heal',amount:def.stats.basicAmount},{casterId:unit.id},events);
      else {
        const multi=unit.statuses.filter(b=>b.type==='basicHits').sort((a,b)=>(b.ratio||0)-(a.ratio||0))[0];
        const hits=Math.max(1,Math.min(6,multi?.hits||1)),amount=def.stats.basicAmount*(1+modifier(unit,'attackUp',s.tick))*(1+(multi?.ratio||0));
        for(let i=0;i<hits;i++)hurt(s,target,amount/hits,unit.id,events);
        const follow=unit.statuses.find(b=>b.type==='followup'&&b.procs<(b.maxProcs||1));
        if(follow){hurt(s,target,follow.amount||0,unit.id,events);follow.procs++;}
      }
      events.push(emit(s,'attack',{entityId:unit.id,characterId:unit.characterId,targetId:target.id,sourcePosition:{x:unit.x,y:unit.y},position:{x:target.x,y:target.y}}));
    }
    return events;
  }
  const api={planCast,startCast,advance,modifier,hurt,apply,targets};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WFBattleEffects=api;
})(typeof window==='undefined'?globalThis:window);
