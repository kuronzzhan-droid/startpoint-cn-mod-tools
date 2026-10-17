const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {Node: BaseNode} = require('./wiki_equipment_fixture.cjs');
class Node extends BaseNode {
  matches(value) {return value.startsWith('.') ? this.className.split(' ').includes(value.slice(1)) : this.tag === value;}
  querySelectorAll(selector) {return this.all(node=>node.matches(selector));}
  querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
  async fire(name) {for (const fn of this.events[name] || []) await fn({target:this,preventDefault(){}});}
}
const weaponId='w123456789abc',characterId='c123456789abc';
const drop={kind:'equipment',name:'测试长剑',amountText:'1 件',equipmentId:weaponId,probabilityText:'普通掉落 5%'};
const cost={kind:'item',name:'首领硬币',amountText:'10 枚'};
function env() {
  const document=new Node('document'),el=(...args)=>Object.assign(new Node(...args),{document}),host=el('main');document.append(host);
  const window={location:{href:'http://127.0.0.1:8877/#shops',origin:'http://127.0.0.1:8877',protocol:'http:'}};
  const context={window,URL};
  for(const file of ['rewards.js','shops.js','dungeons.js'])vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki',file),'utf8'),context);
  const data={equipment:[{id:weaponId,name:'测试长剑',icon:'media/sword.webp'}],characters:[{id:characterId,name:'测试角色'}],
    dungeons:{items:[{id:'boss-a',title:'测试首领'},{id:'boss-b',title:'另一首领'}]},
    rewards:{schemaVersion:1,source:{label:'灰服资料快照',status:'gray-snapshot',checkedAt:'2026-09-30'},
      dungeons:{'boss-a':{quests:[{name:'超级挑战',difficulty:'超级',firstClear:[{kind:'beads',name:'星导石',amountText:'50'}],sPlus:[],drops:[drop],notes:['首次通关奖励单独计入']}],shopIds:['shop-a'],notes:[]}},
      shops:[{id:'shop-a',title:'首领兑换所',dungeonIds:['boss-a'],notes:[],items:[{rewards:[drop],costs:[cost],stock:3,availableFrom:null,availableUntil:null,notes:[]}]},
        {id:'shop-b',title:'其他兑换所',dungeonIds:['boss-b'],items:[{rewards:[{kind:'mana',name:'玛纳',amountText:'1000'}],costs:[],stock:null}]}]}};
  const ui={el};return {window,host,data,ui,el,find:cls=>host.querySelector(cls),render:options=>window.renderWikiShops(host,data,ui,options),
    rewards:id=>window.WFWikiRewardView.renderDungeon(host,id,data,ui)};
}
test('dungeon rewards stay folded until opened and link the matching shop and known equipment', async()=>{
  const x=env();x.rewards('boss-a');assert.equal(x.find('.dungeon-shop-link').href,'#shops/shop-a');
  const quest=x.find('.reward-quest');assert.ok(!quest.open);assert.equal(x.host.querySelectorAll('.reward-card').length,0);
  quest.open=true;await quest.fire('toggle');const cards=x.host.querySelectorAll('.reward-card');assert.equal(cards.length,2);
  assert.equal(cards[1].href,`#weapon/${weaponId}`);assert.equal(cards[1].querySelector('img').src,'http://127.0.0.1:8877/media/sword.webp');
  assert.ok(x.host.textContent.includes('普通掉落 5%'));assert.ok(x.host.textContent.includes('首次通关奖励单独计入'));
  await quest.fire('toggle');assert.equal(x.host.querySelectorAll('.reward-card').length,2);
});
test('missing dungeon rows or empty reward sections say uncollected without asserting no game rewards',async()=>{
  const x=env();x.rewards('unknown');assert.ok(x.host.textContent.includes('资料尚未收录'));assert.ok(!x.host.textContent.includes('无掉落'));
  x.host.replaceChildren();x.data.rewards.dungeons['boss-a']={quests:[{name:'待补关卡',drops:[],firstClear:[],sPlus:[],notes:[]}],shopIds:[]};
  x.rewards('boss-a');const quest=x.find('.reward-quest');quest.open=true;await quest.fire('toggle');
  assert.ok(x.host.textContent.includes('奖励明细尚未收录'));assert.ok(x.host.textContent.includes('对应兑换商店资料尚未收录'));
});
test('empty reward rows with an explicit explanation show the explanation without an uncollected warning',async()=>{
  const explanation='无尽入口不结算常规关卡、首通、SS或每轮掉落奖励';
  for (const noteValues of [[explanation],['', '  ', null]]) {
    const x=env();x.data.rewards.dungeons['boss-a'].quests=[{name:'无尽入口',drops:[],firstClear:[],sPlus:[],notes:noteValues}];
    x.rewards('boss-a');const quest=x.find('.reward-quest');quest.open=true;await quest.fire('toggle');
    const body=quest.querySelector('.reward-quest-body');
    assert.equal(body.textContent.includes(explanation),noteValues.includes(explanation));
    assert.equal(body.textContent.includes('奖励明细尚未收录'),!noteValues.includes(explanation));
    assert.equal(body.querySelectorAll('.reward-card').length,0);
  }
});
test('reward text is literal, unknown assets are not linked, and only trusted local weapon icons load',()=>{
  const x=env(),R=x.window.WFWikiRewardView;x.data.equipment[0].icon='https://evil.test/sword.png';
  x.host.append(R.rewardList(x.ui,[{...drop,name:'<img onerror=alert(1)>',amountText:'<b>100</b>'},
    {...drop,equipmentId:'wffffffffffff'}, {...drop,equipmentId:'javascript:alert(1)'},
    {kind:'character',name:'测试角色',amountText:'1',characterId}],R.context(x.data)));
  const cards=x.host.querySelectorAll('.reward-card');assert.equal(cards[0].textContent.includes('<img onerror=alert(1)>'),true);
  assert.equal(x.host.querySelectorAll('img').length,0);assert.equal(cards[1].tag,'div');assert.equal(cards[2].tag,'div');
  assert.equal(cards[3].href,`#character/${characterId}`);
});
test('shop directory searches reward and cost names and filters by associated dungeon',async()=>{
  const x=env();x.render({});assert.equal(x.host.querySelectorAll('.shop-card').length,2);
  const search=x.find('.shop-search');search.value='首领硬币';await search.fire('input');
  assert.deepEqual(x.host.querySelectorAll('.shop-card').filter(node=>!node.hidden).map(node=>node.href),['#shops/shop-a']);
  search.value='';await search.fire('input');const filter=x.find('.shop-dungeon-filter');filter.value='boss-b';await filter.fire('change');
  assert.deepEqual(x.host.querySelectorAll('.shop-card').filter(node=>!node.hidden).map(node=>node.href),['#shops/shop-b']);
});
test('shop details keep reward quantities, costs, stock semantics and configured dates distinct',()=>{
  const x=env();const shop=x.data.rewards.shops[0];shop.items.push(
    {rewards:[drop],costs:[cost],stock:-1}, {rewards:[drop],costs:[],stock:null,availableFrom:'2026-01-01T00:00:00Z',availableUntil:'2026-02-01T00:00:00Z'},
    {rewards:[],costs:[],stock:0});x.render({id:shop.id});
  assert.equal(x.find('.shop-related').querySelector('a').href,'#dungeons/boss-a');
  const rows=x.host.querySelectorAll('.shop-exchange');assert.equal(rows.length,4);
  assert.ok(rows[0].textContent.includes('配置库存：3'));assert.ok(rows[0].textContent.includes('10 枚'));
  assert.ok(rows[1].textContent.includes('兑换次数不限'));assert.ok(rows[2].textContent.includes('库存资料待补'));
  assert.ok(rows[2].textContent.includes('配置时间：2026-01-01T00:00:00Z'));assert.ok(!rows[2].textContent.includes('当前开放'));
  assert.ok(rows[3].textContent.includes('配置库存：0'));assert.ok(rows[3].textContent.includes('兑换奖励资料尚未收录'));
});
test('large shops paginate rendering and searching resets the visible count',async()=>{
  const x=env();x.data.rewards.shops[0].items=Array.from({length:130},(_,i)=>({rewards:[{kind:'item',name:`材料${i}`,amountText:'1'}],costs:[cost],stock:1}));
  x.render({id:'shop-a'});assert.equal(x.host.querySelectorAll('.shop-exchange').length,60);
  await x.find('.shop-more').fire('click');assert.equal(x.host.querySelectorAll('.shop-exchange').length,120);
  const search=x.find('.shop-search');search.value='材料129';await search.fire('input');
  assert.equal(x.host.querySelectorAll('.shop-exchange').length,1);assert.ok(x.find('.shop-more').hidden);
  search.value='';await search.fire('input');assert.equal(x.host.querySelectorAll('.shop-exchange').length,60);
});
test('missing or invalid shop metadata gives an uncollected state without broken links',()=>{
  const x=env();x.data.rewards.shops=[{id:'../../bad',title:'无效'}];x.render({});
  assert.equal(x.host.querySelectorAll('.shop-card').length,0);assert.ok(x.host.textContent.includes('资料尚未收录'));
  x.render({id:'shop-missing'});assert.ok(x.host.textContent.includes('商店资料尚未收录'));assert.equal(x.find('.back-button').href,'#shops');
});
