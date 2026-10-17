/* Exercise actual checked-in definitions through the production compiler and engine. */
const test=require('node:test'),assert=require('node:assert/strict'),path=require('node:path'),{execFileSync}=require('node:child_process');
const M=require('../wiki/battle-model.js'),E=require('../wiki/battle-effects.js'),F=require('./wiki_battle_fixture.cjs');
const code=`import sys,json,pathlib
sys.path.insert(0,sys.argv[1])
import wf_wiki_battle_content as c
out={}
for theme in c.THEMES:
 for row in json.loads((pathlib.Path(sys.argv[1])/'wiki-battle'/('characters-'+theme+'.json')).read_text(encoding='utf-8'))['characters']:
  stats={**c.STATS[row['role']],**row.get('stats',{})}
  out[row['id']]={**row,'element':theme,'stats':stats,'skill':c._compile_skill(row['skill'],stats)}
print(json.dumps(out))`;
const characters=JSON.parse(execFileSync(process.env.PYTHON||'python',['-c',code,path.resolve(__dirname,'..')],{encoding:'utf8',maxBuffer:2e6}));
const ids=Object.keys(characters),stages=require('../wiki-battle/stages.json').stages;
function create(id){const content={...F.content(),characters,stages};const squad=[id,...ids.filter(v=>v!==id).slice(0,5)];const s=M.create({content,squad,stageId:stages[0].id});s.energy=120;
 squad.forEach((id,i)=>M.dispatch(s,{id:i+1,type:'deploy',characterId:id,col:i===0?2:(i-1)%5,row:i===0?4:5}));
 for(const u of s.units){u.hp=u.maxHp*.3;u.readyAtTick=0;u.nextActionTick=1e9;}
 s.enemies=[F.enemy(100,2.5,3.5),F.enemy(101,1.5,3.5),F.enemy(102,3.5,3.5),F.enemy(103,2.5,5.5)];s.enemies[0].rank='boss';s.energy=120;return s;}
test('all 92 character definitions can cast and remain finite through all skill phases',()=>{
 assert.equal(ids.length,92);
 for(const id of ids){const s=create(id);assert.equal(s.units.length,6,id);const result=M.dispatch(s,{id:7,type:'cast',unitId:s.units[0].id});assert.equal(result.ok,true,`${id}: ${result.reason}`);
  for(let tick=0;tick<400;tick++)M.advance(s);
  for(const u of [...s.units,...s.enemies]){assert.ok(Number.isFinite(u.hp)&&u.hp>=0&&u.hp<=u.maxHp,id);for(const buff of u.statuses)assert.ok(Number.isFinite(buff.until),id);}
  assert.ok(s.effects.length<=32,id);assert.ok(s.energy>=0&&s.energy<=120,id);
 }
});
test('emergency healing affects only allies below forty percent',()=>{
 const id=ids.find(id=>characters[id].skill.phases.some(p=>p.selector.hpBelow===.4));assert.ok(id);const s=create(id),caster=s.units[0];s.units[1].hp=s.units[1].maxHp*.4;
 const untouched=s.units[1].hp;M.dispatch(s,{id:7,type:'cast',unitId:caster.id});for(let i=0;i<40;i++)M.advance(s);assert.equal(s.units[1].hp,untouched);
});
test('each character personal charge is consumed once without spending shared energy',()=>{
 for(const id of ids){const s=create(id),u=s.units[0];s.energy=0;
  assert.equal(M.dispatch(s,{id:7,type:'cast',unitId:u.id}).ok,true);assert.equal(s.energy,0);
  assert.equal(M.dispatch(s,{id:7,type:'cast',unitId:u.id}).ok,false);assert.equal(M.dispatch(s,{id:8,type:'cast',unitId:u.id}).ok,false);assert.equal(s.energy,0);
 }
});
