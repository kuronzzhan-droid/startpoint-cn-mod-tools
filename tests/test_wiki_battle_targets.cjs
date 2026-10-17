const test=require('node:test'),assert=require('node:assert/strict'),T=require('../wiki/battle-targets.js');
test('front rectangles exclude the caster row but retain both adjacent front rows',()=>{const g={kind:'rect',center:'self',width:3,length:2,direction:'up'},o=T.origin(g,{x:2.5,y:4.5});assert.equal(T.contains(g,o,{x:3.5,y:4.5}),false);assert.equal(T.contains(g,o,{x:3.5,y:3.5}),true);assert.equal(T.contains(g,o,{x:3.5,y:2.5}),true);});
test('nearest and lowest-health ties are stable across input order',()=>{
  const origin={x:2,y:2,id:1},a={id:3,x:1,y:2,hp:5,maxHp:10},b={id:2,x:3,y:2,hp:5,maxHp:10};
  const s={units:[a,b],enemies:[a,b],squad:[]};assert.equal(T.select(s,origin,{team:'enemy',kind:'nearest',range:3})[0].id,2);
  assert.equal(T.select(s,origin,{team:'ally',kind:'lowestHp',range:3})[0].id,2);a.x=2;
  assert.equal(T.select(s,origin,{team:'ally',kind:'lowestHp',range:3})[0].id,3);
});
test('geometry includes boundaries, offsets and backward lines without square-circle confusion',()=>{
  assert.ok(T.contains({kind:'circle',radius:1},{x:2,y:2},{x:3,y:2}));
  assert.equal(T.contains({kind:'circle',radius:1},{x:2,y:2},{x:3,y:3}),false);
  assert.ok(T.contains({kind:'circle',radius:1.5},{x:2,y:2},{x:3,y:3}));
  assert.ok(T.contains({kind:'line',width:1,length:3,direction:'down'},{x:2,y:2},{x:2,y:4}));
  assert.equal(T.contains({kind:'line',width:1,length:3},{x:2,y:2},{x:2,y:4}),false);
  assert.ok(T.contains({kind:'circle',radius:.2,offsetX:1},{x:2,y:2},{x:3,y:2}));
});
test('captain never transfers, boss preference and emergency threshold are explicit',()=>{
  const s={squad:['captain'],units:[{id:1,characterId:'other',hp:4,maxHp:10,x:0,y:0}],enemies:[{id:2,rank:'vanguard',hp:5,x:0,y:1},{id:3,rank:'boss',hp:5,x:0,y:2}]};
  assert.deepEqual(T.select(s,{x:0,y:0},{team:'ally',kind:'leader',range:9}),[]);
  assert.equal(T.select(s,{x:0,y:0},{team:'enemy',kind:'nearest',range:9,preferBoss:true})[0].id,3);
  assert.deepEqual(T.select(s,{x:0,y:0},{team:'ally',kind:'lowestHp',range:9,hpBelow:.4}),[]);
});
