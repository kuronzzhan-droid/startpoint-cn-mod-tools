const test=require('node:test'),assert=require('node:assert/strict');
const M=require('../wiki/battle-model.js'),F=require('./wiki_battle_fixture.cjs');
const create=()=>M.create(F.options());
const deploy=(s,id=1,c='c0',col=2,row=5)=>M.dispatch(s,{id,type:'deploy',characterId:c,col,row});
test('deployment charges exactly once and duplicate command cannot occupy another cell',()=>{
  const s=create();assert.equal(s.energy,60);assert.ok(deploy(s).ok);assert.equal(s.energy,40);
  assert.equal(deploy(s).ok,false);assert.equal(s.energy,40);assert.equal(s.units.length,1);
});
test('invalid coordinates, ids, occupied cells and enemy collision never charge',()=>{
  const s=create();for(const [i,c,x,y]of [[1,'c0',-1,0],[2,'c0',5,0],[3,'c0',1,Infinity],[4,'unknown',1,1]])assert.equal(deploy(s,i,c,x,y).ok,false);
  assert.equal(s.energy,60);deploy(s,5);assert.equal(deploy(s,6,'c1').ok,false);
  s.enemies=[F.enemy(99,1.5,1.5)];assert.equal(deploy(s,7,'c1',1,1).ok,false);assert.equal(s.energy,40);
});
test('six unique eligible IDs are required but different versions can coexist',()=>{
  const o=F.options();o.content.characters.c1.name=o.content.characters.c0.name;assert.equal(M.create(o).squad.length,6);
  assert.throws(()=>M.create({...o,squad:['c0','c0']}));assert.throws(()=>M.create({...o,squad:['x',...o.squad.slice(1)]}));
});
test('energy regenerates at three per second and is capped without drift',()=>{
  const s=create();for(let i=0;i<20;i++)M.advance(s);assert.equal(s.energy,63);
  for(let i=0;i<1000;i++)M.advance(s);assert.equal(s.energy,120);
});
test('death creates one coffin for exactly 400 active ticks and cannot be healed or redeployed',()=>{
  const s=create();deploy(s);s.units[0].hp=0;const ev=M.advance(s);assert.equal(ev.filter(e=>e.type==='death').length,1);
  assert.equal(s.coffins.length,1);assert.equal(s.units.length,0);assert.equal(deploy(s,2).ok,false);
  for(let i=0;i<399;i++)M.advance(s);assert.equal(s.coffins.length,1);
  assert.equal(M.advance(s).filter(e=>e.type==='returned').length,1);assert.equal(s.coffins.length,0);
  assert.ok(deploy(s,3).ok);assert.equal(s.units[0].hp,900);assert.equal(s.units[0].readyAtTick-s.tick,400);
});
test('paused ticks do not regenerate energy or advance coffin cooldown',()=>{
  const s=create();deploy(s);s.units[0].hp=0;M.advance(s);M.setPaused(s,true);const before=JSON.stringify(s);
  for(let i=0;i<1200;i++)assert.deepEqual(M.advance(s),[]);assert.equal(JSON.stringify(s),before);
  assert.equal(deploy(s,3,'c1',0,0).ok,false);M.setPaused(s,false);assert.equal(s.status,'running');
});
test('skill ready event occurs only once for the deployed lifetime',()=>{
  const s=create();deploy(s);let count=0;for(let i=0;i<450;i++)count+=M.advance(s).filter(e=>e.type==='ready').length;
  assert.equal(count,1);
});
test('dead enemy rewards only once and a simultaneous base death takes precedence',()=>{
  const s=create();s.enemies=[F.enemy(100,0,0,0)];s.baseHp=0;const events=M.advance(s);
  assert.equal(s.status,'lost');assert.equal(events.filter(e=>e.type==='result').length,1);
  const energy=s.energy;M.advance(s);assert.equal(s.energy,energy);
});
test('recall pays ten energy once, frees the cell and preserves HP and remaining charge off-field',()=>{
 const s=create();deploy(s);const u=s.units[0];u.hp=321;u.readyAtTick=s.tick+137;const id=u.id;
 const result=M.dispatch(s,{id:2,type:'recall',unitId:id});assert.equal(result.ok,true);assert.equal(s.energy,30);assert.equal(s.units.length,0);assert.equal(s.coffins.length,0);assert.equal(result.events[0].type,'recall');
 assert.equal(M.dispatch(s,{id:2,type:'recall',unitId:id}).ok,false);assert.equal(s.energy,30);
 for(let i=0;i<30;i++)M.advance(s);assert.equal(s.reserves.c0.remainingTicks,137);assert.equal(s.reserves.c0.hp,321);
 assert.equal(deploy(s,3).ok,true);assert.equal(s.units[0].hp,321);assert.equal(s.units[0].readyAtTick-s.tick,137);assert.equal(s.energy,14.5);assert.equal(s.reserves.c0,undefined);
});
test('recall rejects insufficient energy, paused battles and dead or unknown units without changing state',()=>{
 const s=create();deploy(s);const id=s.units[0].id;s.energy=9;assert.equal(M.dispatch(s,{id:2,type:'recall',unitId:id}).ok,false);assert.equal(s.units.length,1);assert.equal(s.energy,9);
 s.energy=20;M.setPaused(s,true);assert.equal(M.dispatch(s,{id:3,type:'recall',unitId:id}).ok,false);M.setPaused(s,false);
 s.units[0].hp=0;assert.equal(M.dispatch(s,{id:4,type:'recall',unitId:id}).ok,false);assert.equal(M.dispatch(s,{id:5,type:'recall',unitId:999}).ok,false);assert.equal(s.energy,20);
});
test('ready unit remains ready after recall without repeated ready speech or carried temporary buffs',()=>{
 const s=create();deploy(s);const u=s.units[0];u.readyAtTick=0;u.readyAnnounced=true;u.statuses=[{type:'attackUp',ratio:.5,until:1000}];
 assert.ok(M.dispatch(s,{id:2,type:'recall',unitId:u.id}).ok);assert.ok(deploy(s,3).ok);assert.equal(s.units[0].readyAtTick,s.tick);assert.deepEqual(s.units[0].statuses,[]);assert.equal(M.advance(s).some(e=>e.type==='ready'),false);
});
test('native-derived full charge lengths differ and initial gauge is granted only on first deployment',()=>{
 const o=F.options();o.content.characters.c0.skill.cooldown=75;o.content.characters.c0.skill.initial=.5;o.content.characters.c1.skill.cooldown=22.5;
 const s=M.create(o);deploy(s);assert.equal(s.units[0].readyAtTick,750);deploy(s,2,'c1',3,5);assert.equal(s.units[1].readyAtTick,450);
 s.units[0].hp=0;M.advance(s);for(let i=0;i<400;i++)M.advance(s);s.energy=120;assert.ok(deploy(s,3).ok);const u=s.units.find(u=>u.characterId==='c0');assert.equal(u.readyAtTick-s.tick,1500);
});
test('source cast refunds obey CT and count across recall and redeployment',()=>{
 const o=F.options();o.content.characters.c0.skill.refund={ratio:.2,ct:15,limit:2};const s=M.create(o);deploy(s);s.enemies=[F.enemy()];let command=2;
 function cast(){const u=s.units[0];u.readyAtTick=s.tick;return M.dispatch(s,{id:command++,type:'cast',unitId:u.id});}
 assert.ok(cast().ok);assert.equal(s.units[0].readyAtTick-s.tick,320);assert.ok(cast().ok);assert.equal(s.units[0].readyAtTick-s.tick,400);
 s.energy=120;assert.ok(M.dispatch(s,{id:command++,type:'recall',unitId:s.units[0].id}).ok);assert.ok(deploy(s,command++).ok);assert.ok(cast().ok);assert.equal(s.units[0].readyAtTick-s.tick,400);
 s.tick+=300;assert.ok(cast().ok);assert.equal(s.units[0].readyAtTick-s.tick,320);s.tick+=300;assert.ok(cast().ok);assert.equal(s.units[0].readyAtTick-s.tick,400);
});
