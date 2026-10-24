const test=require('node:test'),assert=require('node:assert/strict');
const W=require('../wiki/battle-waves.js'),M=require('../wiki/battle-model.js'),F=require('./wiki_battle_fixture.cjs');
test('campaign has distinct wave entities and waits 100 active ticks between waves',()=>{
 const s=M.create(F.options());assert.equal(s.enemies.length,2);assert.equal(s.enemies[0].hp,750);
 const old=s.enemies.map(e=>e.id);s.enemies=[];W.progress(s);assert.equal(s.nextWaveTick,100);
 s.tick=99;W.progress(s);assert.equal(s.enemies.length,0);s.tick=100;W.progress(s);
 assert.equal(s.wave,2);assert.equal(s.enemies.length,3);assert.ok(s.enemies.every(e=>!old.includes(e.id)));
 s.enemies=[];W.progress(s);s.tick+=100;W.progress(s);assert.equal(s.enemies.length,3);assert.equal(s.enemies[0].hp,3600);
 s.enemies=s.enemies.slice(1);W.progress(s);assert.equal(s.status,'running');s.enemies=[];W.progress(s);assert.equal(s.status,'won');
});
test('nearest target with stable tie is attacked after warning; otherwise enemy descends',()=>{
 const s=M.create(F.options());s.enemies=[F.enemy(99,2.5,2,1000)];const e=s.enemies[0];e.nextActionTick=0;e.speed=.22;
 W.advance(s);assert.ok(e.y>2);s.units=[{id:1,x:2,y:2.5,hp:1000,maxHp:1000,statuses:[]},{id:2,x:3,y:2.5,hp:1000,maxHp:1000,statuses:[]}];
 const ev=W.advance(s);assert.equal(ev[0].type,'warning');assert.equal(e.pending.targetId,1);
 s.tick=15;W.advance(s);assert.equal(s.units[0].hp,1000);s.tick=16;W.advance(s);assert.equal(s.units[0].hp,965);
});
test('siege remains at bottom and base loss beats final wave victory',()=>{
 const s=M.create(F.options());s.wave=3;s.enemies=[F.enemy(50,2.5,7)];const e=s.enemies[0];e.nextActionTick=0;e.rank='boss';
 W.advance(s);s.tick=16;W.advance(s);assert.equal(s.baseHp,80);assert.equal(s.enemies.length,1);assert.equal(e.siege,true);
 s.baseHp=0;s.enemies=[];W.progress(s);assert.equal(s.status,'lost');assert.equal(s.result.won,false);
});
test('endless uses linear baseline scaling, bounded enemies and finite extreme wave values',()=>{
 const s=M.create({...F.options(),mode:'endless'});assert.equal(s.enemies.length,2);
 s.wave=7;W.spawn(s);assert.equal(s.enemies.length,4);assert.equal(s.enemies[0].hp,4160);assert.equal(s.enemies[0].attack,112);
 s.wave=1e6;W.spawn(s);assert.ok(s.enemies.every(e=>Number.isFinite(e.hp)&&e.hp<=1e9&&e.speed<=.4));
});
test('water heal, light shield, dark reduction and wind warning use theme schedules',()=>{
 for(const theme of ['water','light','dark','wind']){
  const s=M.create(F.options());s.enemies=[F.enemy(99,2.5,3.5,1000)];const e=s.enemies[0];Object.assign(e,{rank:'boss',themeId:theme,specialAtTick:0,enhanced:true,spawnTick:0,nextActionTick:1e9});
  e.hp=500;s.units=[{id:1,x:2.5,y:4.5,hp:500,maxHp:1000,statuses:[]}];const ev=W.advance(s);assert.ok(ev.some(v=>v.type==='warning'));
  s.tick=16;W.advance(s);if(theme==='water')assert.equal(e.hp,580);if(theme==='light')assert.equal(e.statuses[0].remaining,150);
  if(theme==='dark')assert.equal(s.units[0].statuses[0].ratio,.35);if(theme==='wind')assert.notEqual(e.x,2.5);
 }
});
test('enemy reselects a living nearest ally if the warned target dies before its attack',()=>{
 const s=M.create(F.options());s.enemies=[F.enemy(99,2.5,2.5)];s.enemies[0].nextActionTick=0;
 s.units=[{id:1,x:2.5,y:3,hp:100,maxHp:100,statuses:[]},{id:2,x:3,y:3,hp:100,maxHp:100,statuses:[]}];
 W.advance(s);s.units[0].hp=0;s.tick=16;W.advance(s);assert.equal(s.units[1].hp,65);
});
test('enemy maintained slow ends when its caster dies',()=>{const s=M.create(F.options()),enemy=s.enemies[0];enemy.statuses=[{type:'slow',ratio:.3,until:160,requiresCasterAlive:true,sourceId:999}];W.advance(s);assert.deepEqual(enemy.statuses,[]);});
