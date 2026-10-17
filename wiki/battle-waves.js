/* Enemy simulation and finite wave progression, in fixed 50 ms steps. */
((root)=>{
 'use strict';
 const E=typeof module!=='undefined'&&module.exports?require('./battle-effects.js'):root.WFBattleEffects;
 const dist=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
 const emit=(s,type,extra={})=>({id:s.nextEventId++,tick:s.tick,type,...extra});
 const intervals={fire:240,water:360,thunder:Infinity,wind:240,light:400,dark:360};
 function spawn(s){
  const stage=s.mode==='campaign'?s.content.stages.find(t=>t.id===s.stageId):s.content.stages[(s.wave-1)%s.content.stages.length];
  const endless=s.mode==='endless',b=s.content.endless,factor=endless?1+.18*(s.wave-1):stage.difficulty;
  const attackFactor=endless?1+.1*(s.wave-1):stage.difficulty;
  const boss=endless||s.wave===3,count=endless?Math.min(3,Math.ceil(s.wave/3)):s.wave===1?2:s.wave===2?3:2;
  const specs=[...(boss?[{rank:'boss',x:2.5,hp:endless?b.hpBase:3600,attack:endless?b.attackBase:100}]:[]),
   ...Array.from({length:count},(_,i)=>({rank:'vanguard',x:count===1?1.5:count===2?1+i*3:.5+i*2,
    hp:endless?b.vanguardHp:s.wave===1?750:s.wave===2?800:450,attack:endless?b.vanguardAttack:s.wave===2?45:35}))];
  s.enemies=specs.map(d=>({...d,id:s.nextEntityId++,characterId:stage.bossId,themeId:stage.theme,
   hp:Math.min(1e9,d.hp*factor),maxHp:Math.min(1e9,d.hp*factor),attack:Math.min(1e9,d.attack*attackFactor),
   y:d.rank==='boss'?.15:.45,speed:Math.min(.4,.22+(endless?.005*(s.wave-1):0)),range:1.1,interval:1.5,
   siege:false,statuses:[],spawnTick:s.tick,nextActionTick:s.tick+30,specialAtTick:s.tick+(intervals[stage.theme]||360),
   enhanced:!endless||s.wave%3===0,attacks:0}));
  s.waveStartedTick=s.tick;s.nextWaveTick=null;s.rageWarned=false;
  return [emit(s,'wave',{value:s.wave,characterId:stage.bossId})];
 }
 function finish(s,won){
  s.status=won?'won':'lost';s.baseHp=Math.max(0,s.baseHp);
  s.result={mode:s.mode,stageId:s.stageId,won,wave:s.wave,kills:s.kills,time:s.time};
  return [emit(s,'result',{value:s.result})];
 }
 function progress(s){
  if(s.status!=='running')return [];
  if(s.baseHp<=0)return finish(s,false);
  if(s.enemies.some(e=>e.hp>0))return [];
  if(s.mode==='campaign'&&s.wave>=3)return finish(s,true);
  if(s.nextWaveTick==null){s.nextWaveTick=s.tick+100;return [emit(s,'intermission')];}
  if(s.tick<s.nextWaveTick)return [];
  s.wave=Math.min(1e6,s.wave+1);return spawn(s);
 }
 const nearest=(s,e)=>s.units.filter(u=>u.hp>0&&dist(e,u)<=e.range).sort((a,b)=>dist(e,a)-dist(e,b)||a.id-b.id)[0];
 function resolve(s,e,p,events){
  const target=s.units.find(u=>u.id===p.targetId&&u.hp>0)||(p.kind==='attack'?nearest(s,e):null);
  const elapsed=s.tick-(s.waveStartedTick||0),rage=1+Math.min(1,Math.max(0,Math.floor((elapsed-1800)/200)+1)*.1);
  const damage=e.attack*rage;
  if(p.kind==='siege'){s.baseHp=Math.max(0,s.baseHp-(e.rank==='boss'?20:5));events.push(emit(s,'siege',{entityId:e.id,value:s.baseHp}));return;}
  if(p.kind==='attack'){
   if(target&&dist(e,target)<=e.range+.05){E.hurt(s,target,damage,e.id,events);if(p.extra)E.hurt(s,target,damage*.5,e.id,events);}return;
  }
  if(p.kind==='fire'&&p.position)for(const u of s.units.filter(u=>u.hp>0&&dist(u,p.position)<=1))E.hurt(s,u,damage,e.id,events);
  if(p.kind==='water')E.apply(s,e,{type:'heal',ratio:.08},{casterId:e.id},events);
  if(p.kind==='light')E.apply(s,e,{type:'shield',ratio:.15,duration:8},{casterId:e.id},events);
  if(p.kind==='dark'&&target)E.apply(s,target,{type:'healReduction',ratio:.35,duration:8},{casterId:e.id},events);
  if(p.kind==='wind')e.x=Math.max(.5,Math.min(4.5,e.x+(Math.floor(e.x)>=4?-1:1)));
 }
 function advance(s){
  const events=[];if(!s.rageWarned&&s.tick-(s.waveStartedTick||0)>=1740){s.rageWarned=true;events.push(emit(s,'rage-warning'));}
  for(const e of s.enemies){
   if(e.hp<=0)continue;e.statuses=(e.statuses||[]).filter(b=>b.until>s.tick&&(!b.requiresCasterAlive||s.units.some(u=>u.id===b.sourceId&&u.hp>0)));
   if(e.pending){if(e.pending.due<=s.tick){resolve(s,e,e.pending,events);e.pending=null;}else continue;}
   if(e.hp<=0)continue;
   const target=nearest(s,e);
   if(e.y>=7){e.y=7;e.siege=true;}
   let kind=null;
   if(!e.siege&&e.rank==='boss'&&e.enhanced&&s.tick>=e.specialAtTick){
    e.specialAtTick=s.tick+(intervals[e.themeId]||360);
    if(!['fire','dark'].includes(e.themeId)||target)kind=e.themeId;
   }
   if(!kind&&s.tick>=e.nextActionTick&&(e.siege||target)){kind=e.siege?'siege':'attack';e.attacks=(e.attacks||0)+1;e.nextActionTick=s.tick+Math.round(e.interval*20);}
   if(kind){e.pending={kind,due:s.tick+16,targetId:target?.id,position:target?{x:target.x,y:target.y}:null,
    extra:kind==='attack'&&e.themeId==='thunder'&&e.enhanced&&e.attacks%3===0};
    events.push(emit(s,'warning',{entityId:e.id,targetId:target?.id,position:e.pending.position||{x:e.x,y:e.y},value:kind}));
   }else if(!target&&!e.siege)e.y=Math.min(7,e.y+e.speed*(1-Math.min(.8,E.modifier(e,'slow',s.tick)))/20);
  }
  return events;
 }
 const api={spawn,advance,progress};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WFBattleWaves=api;
})(typeof window==='undefined'?globalThis:window);
