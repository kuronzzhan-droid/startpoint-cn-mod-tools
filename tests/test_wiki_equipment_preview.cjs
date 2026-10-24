const test = require('node:test');
const assert = require('node:assert/strict');
const {environment} = require('./wiki_equipment_fixture.cjs');
const entries = [
  {id:'fire',name:'火武器',category:'其他武器',rarity:5,element:'火',enhancement:{maxLevel:120}},
  {id:'water',name:'水武器',category:'其他武器',rarity:3,element:'水'},
  {id:'general',name:'通用武器',category:'深渊武器',rarity:5,element:'通用/未分类'},
  {id:'missing',name:'未分类武器',category:'深渊武器',rarity:4},
];
const find = (root, key, value) => root.all(node => node.attributes[key] === value)[0];
const cls = (root, value) => root.all(node => node.className === value)[0];
function catalogue() {
  const x=environment();x.window.renderWikiWeaponPage(x.host,{equipment:entries},x.ui);
  x.host.all(n=>n.tag==='button'&&n.textContent==='全部展开')[0].fire('click');return x;
}
test('attribute selection synchronizes toolbar/floating controls and composes with rarity/category/search',()=>{
  const {host}=catalogue(),panel=cls(host,'equipment-attribute-popover');
  const names=()=>host.all(n=>n.tag==='strong'&&n.parent.className==='equipment-card-title').map(n=>n.textContent);
  const select=(label,value)=>{const n=find(host,'aria-label',label);n.value=value;n.fire('change');};
  cls(host,'secondary-button equipment-attribute-current').fire('click');assert.equal(panel.hidden,false);
  find(host,'data-weapon-element','火').fire('click');assert.equal(panel.hidden,true);
  assert.deepEqual(names(),['火武器']);assert.match(host.textContent,/共 1 件武器 · 1 件可强化/);
  assert.equal(cls(host,'secondary-button equipment-attribute-current').textContent,'属性：火');
  assert.equal(cls(host,'equipment-attribute-shortcut').textContent,'火');
  assert.equal(cls(host,'equipment-attribute-shortcut').attributes['aria-label'],'筛选武器属性，当前火');
  select('武器星级','3');assert.deepEqual(names(),[]);select('武器星级','');
  find(host,'data-weapon-element','通用').fire('click');assert.deepEqual(names(),['通用武器','未分类武器']);
  select('武器分类','其他武器');assert.deepEqual(names(),[]);select('武器分类','');
  find(host,'data-weapon-element','').fire('click');assert.equal(names().length,4);
  const search=find(host,'aria-label','搜索武器');search.value='水武器';search.fire('input');assert.deepEqual(names(),['水武器']);
});
test('floating picker focuses selection, closes with Escape/outside click, and cleans listeners on route leave',()=>{
  const {host,document,window}=catalogue(),shortcut=cls(host,'equipment-attribute-shortcut'),panel=cls(host,'equipment-attribute-popover');
  shortcut.fire('click');assert.equal(panel.hidden,false);assert.equal(document.activeElement,find(host,'data-weapon-element',''));
  document.fire('keydown',{key:'Escape'});assert.equal(panel.hidden,true);assert.equal(document.activeElement,shortcut);
  shortcut.fire('click');document.fire('pointerdown',{target:document.body});assert.equal(panel.hidden,true);
  shortcut.fire('click');assert.equal(document.events.keydown.size,1);
  window.fire('hashchange');assert.equal(shortcut.isConnected,false);assert.equal(document.events.keydown.size,0);
  assert.equal(window.events.hashchange.size,0);
});
test('same-route rerender removes the previous floating control; direct weapon page has none',()=>{
  const x=catalogue(),old=cls(x.host,'equipment-attribute-shortcut');old.fire('click');
  x.window.renderWikiWeaponPage(x.host,{equipment:entries},x.ui);
  assert.equal(old.isConnected,false);assert.equal(x.document.events.keydown.size,0);
  assert.equal(x.host.all(n=>n.className==='equipment-attribute-shortcut').length,1);
  x.window.renderWikiWeaponPage(x.host,{equipment:entries},x.ui,'fire');x.checkRemoved();
  assert.equal(x.host.all(n=>n.className==='equipment-attribute-shortcut').length,0);
  assert.equal(x.window.events.hashchange.size,0);
});
const weapon = {
  id:'test',name:'试验武器',category:'悖论武器',rarity:5,element:'火',
  stats:{base:{hp:10,atk:2},awakened:{hp:100,atk:20}},baseEffects:['自身 攻击力 10%'],awakenedEffects:['自身 攻击力 50%'],
  soul:{available:true,effects:['魂珠独有 攻击力 5%'],note:'魂珠不继承强化。'},
  enhancement:{maxLevel:200,forms:[
    {level:120,name:'强化武器',stats:{additional:{hp:200,atk:30},total:{hp:300,atk:50}},effects:['强化追加 20%'],finalEffects:['最终 攻击力 70%'],initialFinalEffects:['初始本体合计 攻击力 30%']},
    {level:200,name:'终式武器',stats:{additional:{hp:400,atk:60},total:{hp:500,atk:80}},effects:['强化追加 50%'],finalEffects:['最终 攻击力 100%'],initialFinalEffects:['初始本体合计 攻击力 60%']},
  ]},
};
function cardFixture(entry=weapon) {const x=environment();const card=x.window.WFEquipmentCard.create(entry,x.ui);x.host.append(card);return {...x,card};}
const click = (card,key,value) => find(card,key,value).fire('click');
const toggleMode = (card) => find(card,'role','switch').fire('click');
test('weapon/soul switches retain enhancement and initial/max choice, and each card owns its own mode',()=>{
  const {card,window,host,ui}=cardFixture();
  assert.equal(card.attributes['data-equipment-mode'],'weapon');
  const modes=find(card,'aria-label','试验武器效果类型'),mode=find(modes,'role','switch');
  assert.equal(modes.all(n=>n.tag==='button').length,1);assert.equal(mode.type,'button');
  assert.equal(mode.attributes['aria-checked'],'false');assert.equal(mode.textContent,'武器');assert.match(mode.title,/当前：武器/);
  assert.equal(cls(mode,'equipment-mode-track').attributes['aria-hidden'],'true');
  card.open=true;card.fire('toggle');click(card,'data-level','200');click(card,'data-effect-level','initial');
  let body=cls(card,'equipment-state');assert.match(body.textContent,/初始本体合计 攻击力 60%/);
  const stats=cls(card,'equipment-final-stats');assert.equal(stats.hidden,false);assert.match(stats.textContent,/HP 500 \/ 攻击力 80/);
  toggleMode(card);assert.equal(stats.hidden,true);assert.equal(card.attributes['data-enhancement-level'],'200');
  assert.equal(mode.attributes['aria-checked'],'true');assert.equal(mode.textContent,'魂珠');assert.match(mode.title,/当前：魂珠/);
  assert.match(body.textContent,/魂珠独有 攻击力 5%/);assert.doesNotMatch(body.textContent,/最终|HP 500|强化追加 50/);
  assert.equal(find(card,'aria-label','试验武器本体效果等级').hidden,true);
  const other=window.WFEquipmentCard.create(weapon,ui);host.append(other);assert.equal(other.attributes['data-equipment-mode'],'weapon');
  toggleMode(card);assert.equal(stats.hidden,false);assert.match(body.textContent,/初始本体合计 攻击力 60%/);
  assert.equal(mode.attributes['aria-checked'],'false');assert.equal(mode.textContent,'武器');
  assert.equal(find(card,'data-effect-level','initial').attributes['aria-pressed'],'true');
  click(card,'data-effect-level','max');assert.match(body.textContent,/最终 攻击力 100%/);
  const calculation=cls(card,'equipment-calculation');assert.equal(calculation.open,false);assert.match(calculation.textContent,/强化追加 50%/);
});
test('absent souls cannot be selected and unavailable notes remain accessible',()=>{
  const {card}=cardFixture({...weapon,soul:{available:false,effects:[],note:'当前服务端未登记魂珠。'}});
  const button=find(card,'role','switch');assert.equal(button.disabled,true);assert.match(button.title,/未登记/);
  assert.match(button.attributes['aria-label'],/无可用魂珠/);assert.equal(button.textContent,'无魂珠');
  assert.equal(button.attributes['aria-checked'],'false');
  button.fire('click');assert.equal(card.attributes['data-equipment-mode'],'weapon');
});

test('soul switch is independent while the icon retains native disclosure without extra symbols',()=>{
  const {card}=cardFixture(),summary=card.children.find(n=>n.tag==='summary');
  const actions=cls(card,'equipment-card-actions'),modes=find(card,'aria-label','试验武器效果类型');
  const symbol=cls(card,'equipment-disclosure-symbol'),mode=find(card,'role','switch');
  assert.equal(actions.parent,summary);assert.equal(summary.children.at(-1),actions);
  assert.deepEqual(actions.children,[modes]);assert.equal(symbol,undefined);
  assert.equal(cls(card,'equipment-card-title').contains(mode),false);
  assert.equal(summary.events.click,undefined);
  let prevented=0,stopped=0;
  mode.fire('click',{preventDefault(){prevented++;},stopPropagation(){stopped++;}});
  assert.equal(prevented,1);assert.equal(stopped,1);assert.equal(card.open,true);
  assert.equal(card.attributes['data-equipment-mode'],'soul');
  card.open=false;card.fire('toggle');assert.equal(card.attributes['data-equipment-mode'],'soul');
  card.open=true;card.fire('toggle');assert.match(cls(card,'equipment-state').textContent,/魂珠独有/);
});
test('legacy enhancement data preserves every effect without adding unlike conditions or hiding the only source',()=>{
  const {card}=cardFixture({...weapon,enhancement:{maxLevel:120,stats:{total:{hp:1,atk:2}},effects:['水·自身 攻击力 20%']}});
  card.open=true;card.fire('toggle');click(card,'data-level','120');
  const body=cls(card,'equipment-state'),direct=body.children.filter(n=>n.className!=='equipment-calculation').map(n=>n.textContent).join('');
  assert.match(direct,/自身 攻击力 50%/);assert.match(direct,/水·自身 攻击力 20%/);assert.doesNotMatch(direct,/70%/);
  assert.equal(cls(card,'equipment-calculation').open,false);
});
test('effect emphasis preserves original signs, decimals, conditions and literal markup without interpreting them',()=>{
  const text='HP≤30%时，攻击力+12.75%；持续20秒（限2次）<img onerror=alert(1)>';
  const {card}=cardFixture({...weapon,awakenedEffects:[text]});click(card,'data-level','0');card.open=true;card.fire('toggle');
  const list=cls(card,'equipment-state').children.find(n=>n.className==='equipment-effects');
  assert.equal(list.children[0].textContent,text);
  assert.deepEqual(list.all(n=>n.className==='equipment-effect-value').map(n=>n.textContent),['30%','+12.75%','20秒','2次','1']);
  assert.equal(list.all(n=>n.tag==='img').length,0);
  assert.equal(cls(card,'equipment-calculation').all(n=>n.className==='equipment-effect-value').length,0);
});
test('party restrictions remain visible beside weapon and soul effects rather than being buried or duplicated in calculations',()=>{
  const note='同队其他武器或魂珠每多1件，增益降低25%；达到4件失效。';
  const {card}=cardFixture({...weapon,partyRule:'paradoxDecay',notes:[note]});
  card.open=true;card.fire('toggle');click(card,'data-level','200');
  const body=cls(card,'equipment-state');
  assert.equal(body.children.filter(n=>n.className==='weapon-note').length,1);
  assert.equal(body.children.find(n=>n.className==='weapon-note').textContent,note);
  assert.doesNotMatch(cls(card,'equipment-calculation').textContent,/同队其他/);
  toggleMode(card);
  assert.equal(body.children.filter(n=>n.className==='weapon-note').length,1);
  assert.equal(body.children.find(n=>n.className==='weapon-note').textContent,note);
  toggleMode(card);assert.equal(body.textContent.split(note).length-1,1);
});
test('verified form summaries precede arrays and initial effects never borrow the max-level summary',()=>{
  const forms=weapon.enhancement.forms.map((form,i)=>({...form,finalDescription:`可信满级${form.level}：直击8段，覆写本体6段。`,
    ...(i?{}:{initialFinalDescription:'可信初始120：直击8段，覆写本体6段。'}),
    finalEffects:['本体直击6段','强化直击8段'],initialFinalEffects:[`初始数组${form.level}`]}));
  const {card}=cardFixture({...weapon,enhancement:{...weapon.enhancement,forms}});card.open=true;card.fire('toggle');
  const body=cls(card,'equipment-state'),visible=()=>body.children.filter(n=>n.className!=='equipment-calculation').map(n=>n.textContent).join('');
  click(card,'data-level','120');assert.match(visible(),/可信满级120/);assert.doesNotMatch(visible(),/本体直击6段/);
  click(card,'data-effect-level','initial');assert.match(visible(),/可信初始120/);assert.doesNotMatch(visible(),/可信满级/);
  click(card,'data-level','200');assert.match(visible(),/初始数组200/);assert.doesNotMatch(visible(),/可信满级|可信初始120/);
  click(card,'data-effect-level','max');assert.match(visible(),/可信满级200/);assert.doesNotMatch(visible(),/本体直击6段|初始数组200/);
  assert.match(cls(card,'equipment-calculation').textContent,/强化追加 50%/);
});
