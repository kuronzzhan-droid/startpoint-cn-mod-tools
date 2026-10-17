const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../wiki/rewards-loader.js'), 'utf8');
const payload = () => ({schemaVersion:1,dungeons:{'boss-a':{quests:[],shopIds:['shop-a'],notes:[]}},
  shops:[{id:'shop-a',title:'首领兑换所',items:[],dungeonIds:['boss-a'],notes:[]}]});
function loader(preloaded) {
  const scripts=[], timers=new Map();let sequence=0;
  const characters=[{id:'c123456789abc',name:'测试角色'}],data={characters};
  const window={WFWikiData:{},WF_WIKI:data};if(preloaded)window.WF_WIKI_REWARDS=preloaded;
  const context={window,setTimeout:(fn,delay)=>{timers.set(++sequence,{fn,delay});return sequence;},
    clearTimeout:id=>timers.delete(id),
    document:{createElement:()=>({remove(){this.removed=true;}}),head:{append:script=>scripts.push(script)}}};
  vm.runInNewContext(source,context);
  return {data,window,scripts,timers,load:()=>window.WFWikiData.loadRewards(),
    complete(value,index=scripts.length-1){window.WF_WIKI_REWARDS=value;scripts[index].onload();}};
}
test('reward metadata installs without downloading until a reward route requests it',()=>{
  const x=loader();assert.equal(typeof x.window.WFWikiData.loadRewards,'function');
  assert.equal(x.scripts.length,0);assert.equal(x.timers.size,0);assert.equal(x.data.rewards,undefined);
  assert.equal(x.data.characters[0].name,'测试角色');
});
test('concurrent reward requests share one script and subsequent reads reuse its valid snapshot',async()=>{
  const x=loader(),first=x.load(),second=x.load();assert.equal(x.scripts.length,1);
  assert.equal(x.scripts[0].src,'rewards-data.js');assert.equal(x.scripts[0].async,true);
  const value=payload();x.complete(value);assert.equal(await first,value);assert.equal(await second,value);
  assert.equal(x.data.rewards,value);assert.equal(x.scripts[0].removed,true);assert.equal(x.timers.size,0);
  assert.equal(await x.load(),value);assert.equal(x.scripts.length,1);
});
test('network failures and invalid reward metadata can retry without poisoning the shared data',async()=>{
  const x=loader(),first=x.load();x.scripts[0].onerror();await assert.rejects(first,/暂未载入/);
  assert.equal(x.data.rewards,undefined);assert.equal(x.scripts[0].removed,true);
  const second=x.load();x.complete({...payload(),shops:[{id:'../bad',title:'错误',items:[]}]});
  await assert.rejects(second,/不完整/);assert.equal(x.data.rewards,undefined);
  const third=x.load(),value=payload();x.complete(value);assert.equal(await third,value);
  assert.equal(x.scripts.length,3);assert.equal(x.data.characters[0].name,'测试角色');
});
test('a timed out reward load removes its script, ignores late handlers and permits retry',async()=>{
  const x=loader(),pending=x.load(),timer=[...x.timers.values()][0];assert.equal(timer.delay,30000);
  timer.fn();await assert.rejects(pending,/超时/);assert.equal(x.scripts[0].removed,true);
  assert.equal(x.timers.size,0);const retry=x.load();x.scripts[0].onerror();
  assert.equal(x.scripts[1].removed,undefined);const value=payload();x.complete(value);assert.equal(await retry,value);
});
test('a preloaded valid reward snapshot is attached without network or timers',async()=>{
  const value=payload(),x=loader(value);assert.equal(await x.load(),value);
  assert.equal(x.data.rewards,value);assert.equal(x.scripts.length,0);assert.equal(x.timers.size,0);
});
test('wrong reward schema, array dungeon maps and incomplete shop items fail before attachment',async()=>{
  for(const value of [{...payload(),schemaVersion:2},{...payload(),dungeons:[]},
    {...payload(),shops:[{id:'shop-a',title:'兑换所'}]}]) {
    const x=loader(),pending=x.load();x.complete(value);await assert.rejects(pending,/不完整/);
    assert.equal(x.data.rewards,undefined);assert.equal(x.timers.size,0);
  }
});
