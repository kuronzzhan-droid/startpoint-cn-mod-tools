const test=require('node:test'),assert=require('node:assert/strict'),M=require('../wiki/battle-model.js'),E=require('../wiki/battle-effects.js'),F=require('./wiki_battle_fixture.cjs');
function setup(phases){const o=F.options();if(phases)o.content.characters.c0.skill.phases=phases;const s=M.create(o);M.dispatch(s,{id:1,type:'deploy',characterId:'c0',col:2,row:5});s.units[0].readyAtTick=0;s.units[0].nextActionTick=1e9;return s;}
const p=(type,extra={})=>({offset:0,selector:{team:type==='damage'||type==='dot'?'enemy':'ally',kind:'nearest',range:4},geometry:{kind:'single',center:'target'},effects:[{type,...extra}]});
test('cast needs a valid branch, consumes personal readiness and never charges deployment energy',()=>{
  const s=setup();assert.equal(M.dispatch(s,{id:2,type:'cast',unitId:s.units[0].id}).ok,false);assert.equal(s.energy,40);
  s.enemies=[F.enemy()];s.energy=0;assert.ok(M.dispatch(s,{id:3,type:'cast',unitId:s.units[0].id}).ok);assert.equal(s.energy,0);
  assert.equal(M.dispatch(s,{id:4,type:'cast',unitId:s.units[0].id}).ok,false);assert.equal(s.energy,0);M.advance(s);assert.equal(s.enemies[0].hp,9700);
});
test('a full-health mixed shield can cast but pure heal cannot',()=>{
  const s=setup([p('heal',{ratio:.2})]);assert.equal(E.planCast(s,s.units[0].id),null);
  s.content.characters.c0.skill.phases.push(p('shield',{ratio:.1,duration:8}));assert.ok(E.planCast(s,s.units[0].id));
});
test('visual hit and heal origins are value snapshots and expose shield absorption without changing damage',()=>{
 const s=setup(),u=s.units[0],enemy=F.enemy();s.enemies=[enemy];u.statuses=[{type:'shield',remaining:50,until:20}];const events=[];
 E.hurt(s,u,30,enemy.id,events);assert.equal(u.hp,900);assert.equal(u.statuses[0].remaining,20);
 assert.equal(events[0].value,0);assert.equal(events[0].absorbed,30);assert.deepEqual(events[0].sourcePosition,{x:2.5,y:3.5});
 enemy.x=4;u.x=1;assert.deepEqual(events[0].sourcePosition,{x:2.5,y:3.5});assert.deepEqual(events[0].position,{x:2.5,y:5.5});
 u.hp=800;E.apply(s,u,{type:'heal',amount:40},{casterId:enemy.id},events);assert.equal(u.hp,840);assert.deepEqual(events[1].sourcePosition,{x:4,y:3.5});
 const cast=E.startCast(s,{casterId:u.id,characterId:u.characterId,phases:[]})[0];assert.deepEqual(cast.position,{x:1,y:5.5});u.y=0;assert.equal(cast.position.y,5.5);
});
test('eight-second DoT applies exactly eight parts; death does not cancel emitted ground effect',()=>{
  const s=setup([p('dot',{amount:80,duration:8,interval:1})]);s.enemies=[F.enemy()];M.dispatch(s,{id:2,type:'cast',unitId:s.units[0].id});
  M.advance(s);s.units[0].hp=0;for(let i=0;i<160;i++)M.advance(s);assert.equal(s.enemies[0].hp,9920);
});
test('maintained aura ends on death and strongest buff falls back without extending',()=>{
  const s=setup([p('dot',{amount:80,duration:8,requiresCasterAlive:true})]);s.enemies=[F.enemy()];M.dispatch(s,{id:2,type:'cast',unitId:s.units[0].id});M.advance(s);s.units[0].hp=0;
  for(let i=0;i<160;i++)M.advance(s);assert.equal(s.enemies[0].hp,10000);
  const u={statuses:[{type:'attackUp',ratio:.5,until:10},{type:'attackUp',ratio:.2,until:30}]};
  assert.equal(E.modifier(u,'attackUp',9),.5);assert.equal(E.modifier(u,'attackUp',10),.2);assert.equal(E.modifier(u,'attackUp',30),0);
});
test('healing over time splits total amount and never heals a corpse',()=>{
  const s=setup([p('heal',{amount:80,duration:8})]);s.units[0].hp=500;M.dispatch(s,{id:2,type:'cast',unitId:s.units[0].id});
  for(let i=0;i<161;i++)M.advance(s);assert.equal(s.units[0].hp,580);
});
test('hit-dependent buff cannot be cast for free on an empty board',()=>{
  const dmg=p('damage',{amount:50}),buff=p('attackUp',{ratio:.2,duration:5});buff.requiresHit=0;
  const s=setup([dmg,buff]);assert.equal(E.planCast(s,s.units[0].id),null);s.enemies=[F.enemy()];assert.ok(E.planCast(s,s.units[0].id));
});
test('impact areas use actual hit points once and farthest picks the distant struck enemy',()=>{
  const hit=p('damage',{amount:10});hit.selector.kind='all';hit.geometry.kind='all';
  const follow=p('damage',{amount:100});follow.offset=.1;follow.impactFrom=[0];follow.impactMode='farthest';follow.geometry={kind:'circle',radius:.7,center:'target'};
  const s=setup([hit,follow]);s.enemies=[F.enemy(10,2.5,4.5),F.enemy(11,2.5,2.5)];M.dispatch(s,{id:2,type:'cast',unitId:s.units[0].id});
  for(let i=0;i<3;i++)M.advance(s);assert.equal(s.enemies[0].hp,9990);assert.equal(s.enemies[1].hp,9890);
});
test('ground DoT hits entrants at its fixed point and never double-hits overlapping impact areas',()=>{
  const dot=p('dot',{amount:80,duration:2});dot.geometry={kind:'circle',radius:1,center:'target'};
  const s=setup([dot]);s.enemies=[F.enemy(10,2.5,3.5),F.enemy(11,.5,3.5)];M.dispatch(s,{id:2,type:'cast',unitId:s.units[0].id});M.advance(s);
  s.enemies[0].x=.5;s.enemies[1].x=2.5;for(let i=0;i<40;i++)M.advance(s);assert.equal(s.enemies[0].hp,10000);assert.equal(s.enemies[1].hp,9920);
});
test('attached poison follows only the enemies actually hit, never a later entrant',()=>{
 const dot=p('dot',{amount:80,duration:2,targetMode:'attached'});dot.geometry={kind:'circle',radius:1,center:'target'};
 const s=setup([dot]);s.enemies=[F.enemy(10,2.5,3.5),F.enemy(11,.5,3.5)];M.dispatch(s,{id:2,type:'cast',unitId:s.units[0].id});M.advance(s);
 s.enemies[0].x=.5;s.enemies[1].x=2.5;for(let i=0;i<40;i++)M.advance(s);assert.equal(s.enemies[0].hp,9920);assert.equal(s.enemies[1].hp,10000);
});
test('delayed attached poison uses prior hit identities, deduplicates hits and excludes later entrants',()=>{
 const hit=p('damage',{amount:10});hit.geometry={kind:'line',center:'self',width:1,length:3,direction:'up',offsetX:-2};
 const second={...hit,offset:.2},dot=p('dot',{amount:80,duration:2,targetMode:'attached'});
 dot.offset=1;dot.geometry={kind:'rect',center:'self',width:5,length:3,direction:'up'};dot.hitTargetsFrom=[0,1];
 const s=setup([hit,second,dot]);s.enemies=[F.enemy(10,.5,4.5),F.enemy(11,.5,6.5)];M.dispatch(s,{id:2,type:'cast',unitId:s.units[0].id});
 for(let i=0;i<5;i++)M.advance(s);assert.equal(s.enemies[0].hp,9980);
 s.enemies[0].y=6.5;s.enemies[1].y=4.5;for(let i=0;i<55;i++)M.advance(s);
 assert.equal(s.enemies[0].hp,9900);assert.equal(s.enemies[1].hp,10000);
});
test('hit-bound poison cannot create a valid cast from an unhit enemy in its own area',()=>{
 const hit=p('damage',{amount:10});hit.geometry={kind:'line',center:'self',width:1,length:3,direction:'up',offsetX:-2};
 const dot=p('dot',{amount:80,duration:2,targetMode:'attached'});dot.geometry={kind:'circle',center:'target',radius:2};dot.hitTargetsFrom=[0];dot.offset=1;
 const s=setup([hit,dot]);s.enemies=[F.enemy(10,3.5,4.5)];assert.equal(E.planCast(s,s.units[0].id),null);
});
test('a dead hit target never transfers attached poison to a replacement entity',()=>{
 const hit=p('damage',{amount:10}),dot=p('dot',{amount:80,duration:2,targetMode:'attached'});dot.offset=1;dot.hitTargetsFrom=[0];
 const s=setup([hit,dot]);s.enemies=[F.enemy(10,2.5,4.5)];M.dispatch(s,{id:2,type:'cast',unitId:s.units[0].id});M.advance(s);
 s.enemies[0].hp=0;s.enemies.push(F.enemy(11,2.5,4.5));for(let i=0;i<60;i++)M.advance(s);assert.equal(s.enemies[0].id,11);assert.equal(s.enemies[0].hp,10000);
});
function compiledCharacter(file,id){
 const fs=require('node:fs'),path=require('node:path'),{execFileSync}=require('node:child_process'),tools=path.resolve(__dirname,'..');
 const row=JSON.parse(fs.readFileSync(path.join(tools,'wiki-battle',file),'utf8')).characters.find(c=>c.id===id);
 const code="import json,sys;sys.path.insert(0,sys.argv[1]);import wf_wiki_battle_content as c;r=json.loads(sys.stdin.read());s={**c.STATS[r['role']],**r.get('stats',{})};print(json.dumps({**r,'stats':s,'skill':c._compile_skill(r['skill'],s)}))";
 return JSON.parse(execFileSync(process.env.PYTHON||'python',['-c',code,tools],{input:JSON.stringify(row),encoding:'utf8'}));
}
test('actual ninja poison follows the five sword hits instead of the later rectangle',()=>{
 const c=compiledCharacter('characters-dark.json','c633b80b6a710'),s=setup(c.skill.phases);s.content.characters.c0={...c,id:'c0'};
 s.enemies=[F.enemy(10,.5,4.5),F.enemy(11,.5,6.5)];M.dispatch(s,{id:2,type:'cast',unitId:s.units[0].id});M.advance(s);
 const struck=s.enemies[0].hp;s.enemies[0].y=6.5;s.enemies[1].y=4.5;for(let i=0;i<180;i++)M.advance(s);
 const poison=c.skill.phases[5].effects[0].amount;assert.ok(Math.abs(s.enemies[0].hp-(struck-poison))<1e-6);assert.equal(s.enemies[1].hp,10000);
});
test('actual viper refresh keeps one full poison budget per enemy across both sprays',()=>{
 const c=compiledCharacter('characters-fire.json','cbebf6c04269f'),s=setup(c.skill.phases);s.content.characters.c0={...c,id:'c0'};
 s.enemies=[F.enemy(10,2.5,4.5),F.enemy(11,.5,4.5),F.enemy(12,3.5,3.5)];M.dispatch(s,{id:2,type:'cast',unitId:s.units[0].id});
 for(let i=0;i<9;i++)M.advance(s);s.enemies[0].x=.5;s.enemies[0].y=6.5;s.enemies[1].x=2.5;
 for(let i=0;i<191;i++)M.advance(s);
 const damage=c.skill.phases[0].effects[0].amount,poison=c.skill.phases[1].effects[0].amount;
 for(let i=0;i<3;i++)assert.ok(Math.abs(s.enemies[i].hp-(10000-poison-damage*(i===2?2:1)))<1e-6,`enemy ${i}`);
});
