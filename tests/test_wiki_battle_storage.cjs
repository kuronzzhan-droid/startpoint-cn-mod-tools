const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const file = path.join(__dirname, '../wiki/battle-storage.js');
const api = fs.existsSync(file) ? require(file) : {};
const key = 'wf-wiki-battle-v1', characterIds = ['a','b','c','d','e','f','g'], stageIds = ['fire','water'];
function memory() {
  const values = new Map([['wf-wiki-teams-v1','untouched']]);
  let writes = 0, denied = false, full = false;
  return {values, writes:()=>writes, deny:value=>{denied=value;}, fill:value=>{full=value;},
    getItem(k) {if(denied)throw Error('denied');return values.get(k) ?? null;},
    setItem(k,value) {if(full)throw Error('quota');writes++;values.set(k,value);}};
}
function create(storage = memory()) {
  assert.equal(typeof api.create, 'function', 'the battle storage adapter must exist');
  return api.create({storage,characterIds,stageIds});
}
const won = (time=100,stageId='fire') => ({mode:'campaign',stageId,won:true,time,wave:3,kills:8});
const endless = (wave=5,kills=10) => ({mode:'endless',stageId:'fire',won:false,time:150,wave,kills});
const saved = store => JSON.parse(store.values.get(key));

test('empty storage is playable and repeated reads never write another Wiki namespace', () => {
  const disk=memory(),s=create(disk),result=s.read();
  assert.equal(result.ok,true);assert.deepEqual(result.value.squad,[]);
  assert.deepEqual(result.value.settings,{muted:false,volume:.65});
  assert.deepEqual(result.value.campaign,{});
  assert.deepEqual(result.value.endless,{bestWave:0,bestKills:0});
  for(let tick=0;tick<1000;tick++)s.read();
  assert.equal(disk.writes(),0);assert.equal(disk.values.get('wf-wiki-teams-v1'),'untouched');
});

test('ordered draft squads can grow to six, reject duplicates or unknowns, and do not alias caller data', () => {
  const disk=memory(),s=create(disk),squad=['a','b'];
  assert.equal(s.writeSquad(squad).ok,true);squad.reverse();
  assert.deepEqual(s.read().value.squad,['a','b']);
  assert.equal(s.writeSquad(['a','b','c','d','e','f']).ok,true);
  const before=disk.writes();
  for(const bad of [['a','a'],['missing'],characterIds,null,'a'])assert.equal(s.writeSquad(bad).ok,false);
  assert.equal(disk.writes(),before);assert.deepEqual(s.read().value.squad,['a','b','c','d','e','f']);
  const copy=s.read().value;copy.squad[0]='g';assert.equal(s.read().value.squad[0],'a');
});

test('partial settings updates validate finite volume and skip unchanged writes', () => {
  const disk=memory(),s=create(disk);
  assert.equal(s.writeSettings({muted:true}).ok,true);
  assert.equal(s.writeSettings({volume:0}).ok,true);
  assert.deepEqual(s.read().value.settings,{muted:true,volume:0});
  const before=disk.writes();s.writeSettings({volume:0});
  for(const bad of [{volume:-.1},{volume:1.1},{volume:NaN},{volume:Infinity},{muted:1},null,[]]) {
    assert.equal(s.writeSettings(bad).ok,false);
  }
  assert.equal(disk.writes(),before);assert.equal(s.writeSettings({volume:1}).ok,true);
});

test('corrupt, future, unknown-id and invalid finite saves return safe defaults without overwriting raw data', () => {
  const disk=memory(),s=create(disk);s.writeSquad(['a']);s.record(won());
  const good=saved(disk);
  const invalid=[null,{}, {...good,schema:2}, {...good,squad:['missing']}, {...good,squad:['a','a']},
    {...good,settings:{muted:false,volume:2}}, {...good,endless:{bestWave:1e7,bestKills:0}},
    {...good,modified:{settings:-1,squad:0}}, {...good,modified:{settings:Infinity,squad:0}},
    {...good,campaign:{unknown:{completed:true,bestTime:1}}}];
  for(const raw of ['{','',' '.repeat(65537),JSON.stringify('saved'),...invalid.map(JSON.stringify)]) {
    disk.values.set(key,raw);const next=create(disk),before=disk.writes(),result=next.read();
    assert.equal(result.ok,false);assert.ok(result.error);assert.deepEqual(result.value.squad,[]);
    assert.equal(next.writeSquad(['b']).ok,false);
    assert.equal(disk.values.get(key),raw);assert.equal(disk.writes(),before);
  }
});

test('blocked reads and quota failures retain usable session values and can recover without data loss', () => {
  const disk=memory(),s=create(disk);s.writeSquad(['a']);disk.deny(true);
  assert.equal(s.read().ok,false);const failed=s.writeSquad(['b']);
  assert.equal(failed.ok,false);assert.deepEqual(failed.value.squad,['b']);
  disk.deny(false);disk.fill(true);
  assert.equal(s.record(won(90)).ok,false);assert.equal(s.read().value.campaign.fire.bestTime,90);
  disk.fill(false);assert.equal(s.writeSettings({muted:true}).ok,true);
  assert.deepEqual(saved(disk).squad,['b']);assert.equal(saved(disk).campaign.fire.bestTime,90);
  assert.equal(saved(disk).settings.muted,true);
});

test('browser localStorage getter denial does not throw or prevent in-memory squad selection', () => {
  assert.ok(fs.existsSync(file),'battle storage source is required');
  const window={};Object.defineProperty(window,'localStorage',{get(){throw Error('SecurityError');}});
  vm.runInNewContext(fs.readFileSync(file,'utf8'),{window});
  const s=window.WFBattleStorage.create({characterIds,stageIds});
  assert.equal(s.read().ok,false);const result=s.writeSquad(['a']);
  assert.equal(result.ok,false);assert.deepEqual(Array.from(result.value.squad),['a']);
});

test('campaign records only completed runs and keeps the shortest time across late stale tabs', () => {
  const disk=memory(),one=create(disk),two=create(disk);one.read();two.read();
  assert.equal(one.record(won(100)).ok,true);
  assert.equal(two.record(won(120)).value.campaign.fire.bestTime,100);
  assert.equal(disk.writes(),1);
  assert.equal(two.record(won(80)).ok,true);
  one.writeSettings({volume:.4});assert.equal(saved(disk).campaign.fire.bestTime,80);
  const before=disk.writes();one.record({...won(30),won:false});one.record(won(120));
  assert.equal(disk.writes(),before);assert.equal(saved(disk).campaign.fire.bestTime,80);
  one.record(won(90,'water'));assert.equal(saved(disk).campaign.water.completed,true);
});

test('endless best wave and kills merge independently without persisting live battle objects', () => {
  const disk=memory(),one=create(disk),two=create(disk);one.record(endless(8,20));
  two.record({...endless(6,25),units:[{hp:999}],effects:[{}],secret:'not saved'});
  assert.deepEqual(saved(disk).endless,{bestWave:8,bestKills:25});
  const raw=disk.values.get(key);assert.ok(!raw.includes('units'));assert.ok(!raw.includes('secret'));
  assert.equal(disk.writes(),2);two.record(endless(6,25));assert.equal(disk.writes(),2);
});

test('non-finite, unbounded and invalid results never change or write best records', () => {
  const disk=memory(),s=create(disk);s.record(won());const before=disk.values.get(key),writes=disk.writes();
  for(const bad of [null,{}, {...won(),mode:'online'}, {...won(),stageId:'unknown'}, {...won(),won:1},
    {...won(),time:NaN}, {...won(),time:Infinity}, {...won(),time:-1}, {...won(),time:1e9+1},
    {...won(),wave:0}, {...won(),wave:2.5}, {...won(),wave:1e6+1}, {...won(),kills:-1}, {...won(),kills:1e6+1}]) {
    assert.equal(s.record(bad).ok,false);
  }
  assert.equal(disk.values.get(key),before);assert.equal(disk.writes(),writes);
  assert.equal(s.record({...endless(1e6,1e6),time:1e9}).ok,true);
});

test('a record operation rereads fresh settings and squad instead of restoring its stale snapshot', () => {
  const disk=memory(),one=create(disk),two=create(disk);one.read();two.read();
  one.writeSettings({muted:true,volume:.2});one.writeSquad(['b','a']);
  two.record(won());assert.deepEqual(saved(disk).settings,{muted:true,volume:.2});
  assert.deepEqual(saved(disk).squad,['b','a']);
  two.writeSettings({volume:.8});one.writeSquad(['c']);
  assert.deepEqual(saved(disk).settings,{muted:true,volume:.8});
});

test('external snapshots update listeners without writing and stale events cannot roll back preferences or best results', () => {
  const disk=memory(),one=create(disk),two=create(disk),updates=[];
  const unsubscribe=one.subscribe(value=>updates.push(value));
  two.writeSettings({volume:.2});two.writeSquad(['b']);two.record(won(100));const old=disk.values.get(key);
  one.mergeExternal(old);two.writeSettings({volume:.8});two.writeSquad(['c']);two.record(won(80));
  const before=disk.writes();assert.equal(one.mergeExternal(disk.values.get(key)).ok,true);
  const last=one.mergeExternal(old);
  assert.equal(last.value.settings.volume,.8);assert.deepEqual(last.value.squad,['c']);
  assert.equal(last.value.campaign.fire.bestTime,80);assert.equal(disk.writes(),before);
  assert.ok(updates.length>=2);updates.at(-1).value.squad.push('f');
  assert.deepEqual(one.read().value.squad,['c']);unsubscribe();
  const count=updates.length;one.mergeExternal(null);assert.equal(updates.length,count);
});

test('malformed external events cannot erase current state and destroy releases subscribers and blocks writes', () => {
  const disk=memory(),s=create(disk);s.writeSquad(['a']);s.record(won(70));
  assert.equal(s.mergeExternal('{').ok,false);assert.deepEqual(s.read().value.squad,['a']);
  assert.equal(s.read().value.campaign.fire.bestTime,70);
  let calls=0;s.subscribe(()=>calls++);s.destroy();s.destroy();const before=disk.writes();
  assert.equal(s.writeSquad(['b']).ok,false);assert.equal(s.record(won(40)).ok,false);
  s.mergeExternal(disk.values.get(key));assert.equal(disk.writes(),before);assert.equal(calls,0);
});

test('the next explicit settlement repairs a worse disk snapshot after a best record was merged in memory', () => {
  const disk=memory(),s=create(disk);s.record(won(100));const old=disk.values.get(key);
  s.record(won(80));const best=disk.values.get(key);
  const observer=create(disk);observer.mergeExternal(best);disk.values.set(key,old);
  const before=disk.writes();assert.equal(observer.record(won(120)).ok,true);
  assert.equal(saved(disk).campaign.fire.bestTime,80);assert.equal(disk.writes(),before+1);
});

test('subscriber failures and mutated snapshots cannot interrupt saving or corrupt later subscribers', () => {
  const disk=memory(),s=create(disk),seen=[];
  s.subscribe(snapshot=>{snapshot.value.squad.push('missing');throw Error('UI detached');});
  s.subscribe(snapshot=>seen.push(snapshot.value.squad));
  assert.equal(s.writeSquad(['a']).ok,true);assert.deepEqual(seen,[['a']]);
  assert.deepEqual(saved(disk).squad,['a']);assert.equal(disk.writes(),1);
});
