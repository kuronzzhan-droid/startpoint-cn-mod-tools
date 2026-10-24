const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {Node} = require('./wiki_equipment_fixture.cjs');
function environment() {
  const window={},host=new Node('main'),ui={el:(...args)=>new Node(...args)};
  for(const name of ['pages.js','boss-guide.js'])vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki',name),'utf8'),{window});
  const data={bossGuide:{title:'五重决战',summary:'上下半场随机路线',entry:{enabled:true,ticketName:'旧快照凭证'},
    rewards:[{name:'图纸',description:'60% 概率'}],notes:['机制血量来自本地快照'],
    stages:[{name:'试炼回廊',round:1,waves:[{name:'守门者',hp:100}],entryMechanics:['开场眩晕']}],
    bosses:[{name:'深界王',mechanics:['弹射破盾']}]}};
  return {window,host,ui,data,render:options=>window.renderWikiBossGuide(host,data,ui,options)};
}
test('embedded mechanics view omits stale entry and rewards while preserving lazy stage and boss queries',()=>{
  const x=environment(),before=JSON.stringify(x.data);x.render({mechanicsOnly:true});
  assert.ok(x.host.textContent.includes('本地资料快照'));
  assert.ok(x.host.textContent.includes('机制血量来自本地快照'));
  assert.ok(!x.host.textContent.includes('当前开放'));assert.ok(!x.host.textContent.includes('旧快照凭证'));
  assert.ok(!x.host.textContent.includes('60%'));assert.ok(!x.host.textContent.includes('开场眩晕'));
  const sections=x.host.all(node=>node.tag==='details');assert.equal(sections.length,2);
  for(const section of sections){section.open=true;section.fire('toggle');}
  assert.ok(x.host.textContent.includes('守门者'));assert.ok(x.host.textContent.includes('开场眩晕'));
  assert.ok(x.host.textContent.includes('深界王'));assert.ok(x.host.textContent.includes('弹射破盾'));
  assert.ok(!x.host.textContent.includes('60%'));assert.equal(JSON.stringify(x.data),before);
});
test('standalone legacy rendering remains compatible with its explicitly labelled local snapshot',()=>{
  const x=environment();x.render();assert.ok(x.host.textContent.includes('本地资料快照'));
  assert.ok(x.host.textContent.includes('当前开放：是'));assert.ok(x.host.textContent.includes('60% 概率'));
});
test('both directory and preserved five-boss routes explicitly request mechanics-only embedding',()=>{
  for(const route of ['dungeons/boss-1-99','five-boss']) {
    const x=environment();x.data.dungeons={items:[{id:'boss-1-99',legacyGuide:'five-boss'}]};
    let selected;x.window.renderWikiDungeons=(host,_data,_ui,options)=>{selected=options.id;options.renderLegacyGuide(host);};
    assert.equal(x.window.renderWikiPage(route,x.host,x.data,x.ui),true);assert.equal(selected,'boss-1-99');
    assert.ok(x.host.textContent.includes('Boss 机制速查'));assert.ok(!x.host.textContent.includes('60%'));
    assert.ok(!x.host.textContent.includes('当前开放'));
  }
});
