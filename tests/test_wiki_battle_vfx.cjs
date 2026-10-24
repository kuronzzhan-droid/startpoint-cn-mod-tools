const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const Vfx=require('../wiki/battle-vfx.js');
const content={characters:{a:{element:'fire',role:'melee',stats:{range:1.1}},b:{element:'water',role:'ranged',stats:{range:3}}}};
function state(tick=0){return {tick,status:'running',units:[{id:1,characterId:'a',x:2.5,y:4.5,hp:10},{id:2,characterId:'b',x:.5,y:5.5,hp:10}],enemies:[{id:10,characterId:'a',x:2.5,y:2,hp:10}]};}
function ctx(){const calls=[],styles={};return new Proxy({calls,styles},{get:(o,k)=>k in o?o[k]:(...args)=>calls.push([k,...args]),set:(o,k,v)=>{styles[k]=v;calls.push(['style',k,v]);return true;}});}
function draw(v,s,selection){const c=ctx();v.draw(c,s,{width:300,height:420,dpr:2,selection});return c.calls;}
const event=(id,type,extra={})=>({id,tick:0,type,entityId:1,position:{x:2.5,y:4.5},...extra});
function freeze(value){Object.freeze(value);for(const item of Object.values(value))if(item&&typeof item==='object'&&!Object.isFrozen(item))freeze(item);return value;}

test('simulation tick freezes exact drawing, then expires visual and text queues',()=>{
 const v=Vfx.create({content}),s=state();v.ingest(s,[event(1,'damage',{value:17})]);const first=draw(v,s);
 s.status='paused';assert.deepEqual(draw(v,s),first);assert.deepEqual(draw(v,s),first);
 s.tick=3;assert.notDeepEqual(draw(v,s),first);s.tick=100;draw(v,s);
 assert.equal(v.stats().visuals,0);assert.equal(v.stats().texts,0);
});
test('repeated and unsorted same-batch event IDs never replay or multiply effects',()=>{
 const v=Vfx.create({content}),s=state();const events=[event(2,'heal',{value:2}),event(1,'damage',{value:3}),event(2,'heal',{value:2})];
 v.ingest(s,events);assert.equal(v.stats().visuals,2);assert.equal(v.stats().texts,2);const before=v.stats();
 v.ingest(s,events);assert.deepEqual(v.stats(),before);s.tick=100;draw(v,s);v.ingest(s,events);
 assert.equal(v.stats().visuals,0);assert.equal(v.stats().lastEventId,2);
});
test('particle and text budgets stay bounded while fire warning survives damage bursts',()=>{
 const v=Vfx.create({content}),s=state();v.ingest(s,[event(1,'warning',{value:'fire',entityId:10})]);
 v.ingest(s,Array.from({length:300},(_,i)=>event(i+2,'damage',{value:i})));
 assert.ok(v.stats().visuals<=48);assert.ok(v.stats().texts<=12);
 assert.ok(draw(v,s).some(c=>c[0]==='arc'&&c[3]===60),'one-grid-cell fire telegraph retained');
});
test('reduced motion reduces particle drawing without removing warnings or numbers',()=>{
 const full=Vfx.create({content}),reduced=Vfx.create({content,reducedMotion:true}),s=state();
 const events=[event(1,'warning',{value:'fire',entityId:10}),event(2,'damage',{value:15}),event(3,'heal',{value:8})];
 full.ingest(s,events);reduced.ingest(s,events);s.tick=3;const a=draw(full,s),b=draw(reduced,s);
 assert.ok(b.filter(c=>c[0]==='fillRect').length<a.filter(c=>c[0]==='fillRect').length);
 assert.ok(b.some(c=>c[0]==='arc'&&c[3]===60));assert.equal(b.filter(c=>c[0]==='fillText').length,2);
});
test('changing motion preference preserves already queued danger and deduplication state',()=>{
 const v=Vfx.create({content}),s=state();v.ingest(s,[event(1,'warning',{value:'fire',entityId:10}),event(2,'damage',{value:15})]);
 const before=v.stats(),full=draw(v,s);v.setReducedMotion(true);assert.deepEqual(v.stats(),before);
 const reduced=draw(v,s);assert.ok(reduced.some(c=>c[0]==='arc'&&c[3]===60));assert.notDeepEqual(reduced,full);
 v.setReducedMotion(false);assert.deepEqual(draw(v,s),full);assert.deepEqual(v.stats(),before);
});
test('frozen inputs remain byte-identical and queued event positions are detached',()=>{
 const v=Vfx.create({content:freeze(structuredClone(content))}),s=freeze(state()),events=freeze([event(1,'attack',{sourcePosition:{x:1,y:1}}),event(2,'damage',{value:4})]);
 const before=JSON.stringify({s,events});v.ingest(s,events);draw(v,s,freeze({unitId:1}));assert.equal(JSON.stringify({s,events}),before);
 const mutable=event(3,'heal',{value:5});v.ingest(s,[mutable]);const first=draw(v,s);mutable.position.x=100;assert.deepEqual(draw(v,s),first);
});
test('legacy missing positions resolve known entities and unknown entries are ignored safely',()=>{
 const v=Vfx.create({content}),s=state();v.ingest(s,[{id:1,type:'cast',entityId:1},{id:2,type:'heal',entityId:1,targetId:2,value:2},
  {id:3,type:'recall',entityId:404},{id:4,type:'damage',position:{x:NaN,y:Infinity},value:5},{id:5,type:'unknown'}]);
 assert.equal(v.stats().visuals,2);assert.equal(v.stats().texts,1);assert.doesNotThrow(()=>draw(v,s));
});
test('attack range overlay uses only the selected living unit or valid deployment preview',()=>{
 const v=Vfx.create({content}),s=state();let calls=draw(v,s,{unitId:1});assert.ok(calls.some(c=>c[0]==='arc'&&c[3]===66));
 calls=draw(v,s,{characterId:'b',cell:{col:2,row:4}});assert.ok(calls.some(c=>c[0]==='arc'&&c[3]===180));
 assert.equal(draw(v,s,{characterId:'b'}).filter(c=>c[0]==='arc').length,0);
 assert.equal(draw(v,s,{unitId:404}).filter(c=>c[0]==='arc').length,0);
 assert.equal(draw(v,s,{characterId:'b',cell:{col:-1,row:4}}).filter(c=>c[0]==='arc').length,0);
});
test('all requested cues draw with elemental palettes and absorbed shield text',()=>{
 const v=Vfx.create({content}),s=state();const kinds=['attack','damage','heal','buff','deploy','recall','death','ready','cast','warning'];
 v.ingest(s,kinds.map((kind,i)=>event(i+1,kind,{value:kind==='buff'?'shield':kind==='warning'?'attack':12,absorbed:3,sourcePosition:{x:.5,y:4.5}})));
 const calls=draw(v,s);assert.equal(v.stats().visuals,10);assert.ok(calls.some(c=>c[0]==='fillText'&&String(c[1]).includes('3')));
 assert.ok(calls.some(c=>c[0]==='style'&&c[1]==='fillStyle'&&String(c[2]).startsWith('#')));
});
test('absorbed hits show shield feedback without fake zero damage, including tiny real hits',()=>{
 const v=Vfx.create({content}),s=state();v.ingest(s,[event(1,'damage',{value:0,absorbed:20,targetId:11}),event(2,'damage',{value:0}),event(3,'damage',{value:.01,targetId:12})]);
 const labels=draw(v,s).filter(c=>c[0]==='fillText').map(c=>c[1]);assert.deepEqual(labels,['护盾 20','−<0.1']);
 assert.ok(labels.every(label=>label!=='−0'));assert.equal(v.stats().texts,2);
});
test('same-tick same-target multihits aggregate damage heal and absorption totals separately',()=>{
 const v=Vfx.create({content}),s=state();v.ingest(s,Array.from({length:100},(_,i)=>event(i+1,'damage',{targetId:10,value:5,absorbed:2})));
 v.ingest(s,[event(101,'heal',{targetId:10,value:3}),event(102,'heal',{targetId:10,value:4}),event(103,'damage',{targetId:11,value:9})]);
 const labels=draw(v,s).filter(c=>c[0]==='fillText').map(c=>c[1]);assert.deepEqual(labels,['−500 · 盾200','+7','−9']);assert.equal(v.stats().texts,3);
 s.tick=1;v.ingest(s,[event(104,'damage',{tick:1,targetId:10,value:5})]);assert.equal(v.stats().texts,4);
});
test('different targets retain the twelve-text cap and danger paints after decorative effects',()=>{
 const v=Vfx.create({content}),s=state();v.ingest(s,[event(1,'warning',{value:'fire',entityId:10}),
  ...Array.from({length:40},(_,i)=>event(i+2,'damage',{targetId:i+100,value:5}))]);
 assert.equal(v.stats().texts,12);const calls=draw(v,s),lastParticle=calls.findLastIndex(c=>c[0]==='fillRect'),warning=calls.findIndex(c=>c[0]==='arc'&&c[3]===60);
 assert.ok(warning>lastParticle);
});
test('source event coordinates remain correct after actors move or leave, and warning ends on its due tick',()=>{
 const v=Vfx.create({content}),s=state();v.ingest(s,[event(1,'attack',{characterId:'b',position:{x:2,y:2},sourcePosition:{x:1,y:1}}),
  event(2,'warning',{value:'fire',entityId:10})]);s.tick=3;const first=draw(v,s);s.units=[];assert.deepEqual(draw(v,s),first);
 s.tick=15;assert.ok(draw(v,s).some(c=>c[0]==='arc'&&c[3]===60));s.tick=16;assert.ok(!draw(v,s).some(c=>c[0]==='arc'&&c[3]===60));
});
test('a warning from a defeated source disappears instead of displaying a canceled attack',()=>{
 const v=Vfx.create({content}),s=state();v.ingest(s,[event(1,'warning',{value:'fire',entityId:10})]);assert.equal(v.stats().visuals,1);
 s.enemies=[];draw(v,s);assert.equal(v.stats().visuals,0);
});
test('clear releases all state and supports a fresh fight beginning at event ID one',()=>{
 const v=Vfx.create({content}),s=state();v.ingest(s,[event(90,'heal',{value:1})]);v.clear();
 assert.deepEqual(v.stats(),{visuals:0,texts:0,lastEventId:0});v.ingest(s,[event(1,'deploy')]);assert.equal(v.stats().visuals,1);
});
test('no timing, network, animation-frame or randomness dependencies exist',()=>{
 const source=fs.readFileSync(path.join(__dirname,'../wiki/battle-vfx.js'),'utf8');
 assert.doesNotMatch(source,/\b(?:requestAnimationFrame|setTimeout|setInterval|fetch)\s*\(|Math\.random\s*\(|Date\.now\s*\(/);
});
