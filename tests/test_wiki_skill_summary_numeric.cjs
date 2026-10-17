const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
class Node {
  constructor(tag, className='', value='') {Object.assign(this,{tag,className,ownText:String(value),children:[],attributes:{},events:{},dataset:{},open:false});}
  append(...nodes) {this.children.push(...nodes);}
  replaceChildren(...nodes) {this.ownText='';this.children=nodes;}
  setAttribute(key,value) {this.attributes[key]=value;}
  addEventListener(name,action) {this.events[name]=action;}
  fire(name='click') {return this.events[name]?.();}
  get textContent() {return this.ownText+this.children.map((node)=>node.textContent).join('');}
  querySelectorAll(selector) {return this.children.flatMap((node)=>[...(selector.startsWith('.')?node.className.split(' ').includes(selector.slice(1)):node.tag===selector)?[node]:[],...node.querySelectorAll(selector)]);}
  querySelector(selector) {return this.querySelectorAll(selector)[0]||null;}
}
const el=(...args)=>new Node(...args), list=(v)=>Array.isArray(v)?v:[], text=(v,f='')=>v==null||v===''?f:String(v);
const ui={el,list,text,object:(v)=>v&&typeof v==='object'?v:{},picture:()=>el('img'),nativeIcon:()=>el('span'),elementBadge:()=>el('span'),rarityBadge:()=>el('span'),formatNumber:String};
function setup() {
  const window={};for(const file of ['character-levels.js','skill-summary-numeric.js','character-summary.js'])
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki',file),'utf8'),{window});
  const mount=(skill,mode='max')=>{const host=el('main');window.renderWikiSkillSummaryNumeric(host,window.WFCharacterLevels.projectEntry(skill,mode,{kind:'skill',includeNumeric:true}),ui);return host;};
  return {window,mount};
}
const field=(label,value)=>({label,value});
const row=(kind,label,value,context=[])=>({kind,label,context,values:value});
const damage=(value,context=[])=>row('damage','伤害',[field('单次命中倍率',value),field('区间命中次数设定','4'),field('判定持续','1秒')],context);
const formula=(limit,context=[])=>row('formula','叠层成长规则',[field('成长变量1',`min(状态层数 ÷ 1, ${limit})`)],context);
const skill=(rows,extra={})=>({name:'测试技能',gauge:500,gaugeMin:550,numericDetails:{rows,notes:['测试来源说明']},...extra});
const open=(node)=>{node.open=true;node.fire('toggle');};
const fold=(host,prefix)=>host.querySelectorAll('.summary-numeric-more').find((node)=>node.children[0].textContent.startsWith(prefix));

test('damage is prioritized without multiplying hits or combining duplicate and conditional effects',()=>{
  const x=setup(),input=skill([row('condition','攻击力',[field('效果量','25→50%'),field('持续时间','10秒')]),
    damage('1→2倍',['主位发动']),damage('1→2倍',['合击位发动']),damage('0倍')]);
  const snapshot=JSON.stringify(input),host=x.mount(input);open(fold(host,'详细数值'));
  const items=host.querySelectorAll('.summary-numeric-item');
  assert.deepEqual(items.map((item)=>item.querySelector('h5').textContent),['伤害','伤害','伤害','攻击力']);
  assert.match(items[0].textContent,/主位发动/);assert.match(items[1].textContent,/合击位发动/);
  assert.match(items[0].textContent,/单次命中倍率2倍区间命中次数设定4/);
  assert.equal(items[0].querySelectorAll('dd')[0].textContent,'2倍');assert.match(items[2].textContent,/0倍/);
  assert.doesNotMatch(items[0].textContent,/8倍/);assert.match(items[3].textContent,/50%/);
  assert.equal(JSON.stringify(input),snapshot);
});

test('growth definitions retain their exact branch and source rather than being borrowed from another condition or program',()=>{
  const yes=['延迟 0.1秒','形态切换标记：成立'],no=['延迟 0.1秒','形态切换标记：不成立'];
  const input=skill([formula(99,yes),damage('1.3→1.5 + (0 + 0.3 × 成长变量1)倍',yes),
    formula(10,no),damage('2→3 + 成长变量1倍',no)],{relatedPrograms:[{kind:'关联技能',numericDetails:{rows:[formula(777,yes),damage('4→5 + 成长变量1倍',yes)]}}]});
  const host=setup().mount(input);open(fold(host,'详细数值'));const items=host.querySelectorAll('.summary-numeric-item');
  assert.match(items[0].textContent,/1.5 \+ \(0 \+ 0.3 × 成长变量1\)倍/);assert.match(items[0].textContent,/99\)/);assert.doesNotMatch(items[0].textContent,/10\)|777\)/);
  assert.match(items[1].textContent,/不成立/);assert.match(items[1].textContent,/10\)/);assert.doesNotMatch(items[1].textContent,/99\)/);
  assert.match(items[2].textContent,/关联效果 1 · 关联技能/);assert.match(items[2].textContent,/777\)/);assert.doesNotMatch(items[2].textContent,/99\)/);
  assert.equal(host.querySelectorAll('.summary-numeric-formula').length,0);open(fold(host,'成长规则'));
  assert.equal(host.querySelectorAll('.summary-numeric-formula').length,3);
});

test('unresolved or differently conditioned growth variables are explicitly marked and their original definitions remain inspectable',()=>{
  const host=setup().mount(skill([formula(9,['其他条件']),damage('成长变量1 + 成长变量2倍',['当前条件'])]));
  open(fold(host,'详细数值'));
  const item=host.querySelector('.summary-numeric-item');assert.equal(item.querySelector('.summary-numeric-definition'),null);
  assert.match(item.textContent,/成长变量1 未记录同条件定义/);assert.match(item.textContent,/成长变量2 的定义未记录/);
  open(fold(host,'成长规则'));assert.match(host.querySelector('.summary-numeric-formula').textContent,/其他条件.*9\)/s);
});

test('all details start closed with zero effect DOM; effects, rules and notes only render when opened',()=>{
  const host=setup().mount(skill([formula(10),...Array.from({length:12},(_,i)=>damage(`${i+1}倍`))]));
  const details=fold(host,'详细数值');assert.equal(details.open,false);
  assert.equal(host.querySelectorAll('.summary-numeric-item').length,0);assert.equal(host.querySelectorAll('dl').length,0);
  assert.equal(host.querySelectorAll('.summary-numeric-context').length,0);assert.equal(host.querySelectorAll('.summary-numeric-definition').length,0);
  assert.equal(host.querySelectorAll('details').length,1);open(details);open(details);
  assert.equal(host.querySelectorAll('.summary-numeric-item').length,6);assert.equal(host.querySelectorAll('.summary-numeric-formula').length,0);
  assert.equal(host.querySelectorAll('.summary-numeric-notes').length,0);
  const more=fold(host,'展开其余');assert.match(more.textContent,/6 条/);open(more);open(more);
  assert.equal(host.querySelectorAll('.summary-numeric-item').length,12);open(fold(host,'成长规则'));
  assert.equal(host.querySelectorAll('.summary-numeric-formula').length,1);open(fold(host,'数值说明'));assert.match(host.textContent,/测试来源说明/);
});

test('support skills display buff amounts, durations and healing without claiming an unrecorded damage multiplier',()=>{
  const host=setup().mount(skill([row('condition','技能伤害',[field('持续时间','10→15秒'),field('效果量','50→100%')]),
    row('heal','比例回复',[field('计算基准','目标最大生命'),field('比例','15%')])]));
  const preview=host.querySelector('.summary-numeric-preview');assert.match(preview.textContent,/技能伤害 100% · 15秒/);
  assert.match(preview.textContent,/比例回复 目标最大生命15%/);assert.equal(host.querySelectorAll('dl').length,0);
  open(fold(host,'详细数值'));
  assert.match(host.textContent,/持续时间15秒效果量100%/);assert.match(host.textContent,/目标最大生命/);assert.match(host.textContent,/15%/);
  assert.equal(host.querySelectorAll('dt').filter((node)=>node.textContent==='单次命中倍率').length,0);
  const empty=setup().mount(skill([row('damage','缺值',[field('倍率',null)])]));assert.match(empty.textContent,/倍率与效果数值未记录/);
});

test('the real overview switches initial/max endpoints and skill forms including related effects while preserving source data',()=>{
  const x=setup(),character={name:'概览角色',skills:[
    {...skill([damage('1→2倍')]),kind:'main',level:'1',name:'普通'},
    {...skill([formula(99),damage('3→4 + 成长变量1倍')]),kind:'main',level:'2',name:'进化'},
    {...skill([damage('5→6倍')],{relatedPrograms:[{kind:'触发效果',numericDetails:{rows:[damage('7→8倍')]}}]}),kind:'switched',level:'2',name:'切换'}]};
  const before=JSON.stringify(character),host=el('main');x.window.renderWikiCharacterSummary(host,character,{},ui,{});
  const read=()=>host.querySelector('.summary-skill-body'),levels=host.querySelector('.summary-level-toolbar').querySelectorAll('button');
  assert.match(read().textContent,/进化/);assert.match(read().textContent,/4 \+ 成长变量1倍/);assert.doesNotMatch(read().textContent,/99\)/);
  open(fold(host,'详细数值'));assert.match(read().textContent,/99\)/);
  levels[0].fire();assert.match(read().textContent,/3 \+ 成长变量1倍/);assert.doesNotMatch(read().textContent,/3→4/);
  assert.equal(read().querySelectorAll('.summary-numeric-item').length,0);assert.equal(fold(host,'详细数值').open,false);
  host.querySelector('.summary-skill-choices').querySelectorAll('button')[2].fire();
  assert.match(read().textContent,/切换/);assert.match(read().textContent,/单次倍率 5倍 \/ 7倍/);
  open(fold(host,'详细数值'));assert.match(read().textContent,/关联效果 1 · 触发效果.*7倍/s);
  levels[1].fire();assert.match(read().textContent,/单次倍率 6倍 \/ 8倍/);
  assert.equal(read().querySelectorAll('.summary-numeric-item').length,0);
  open(fold(host,'详细数值'));assert.match(read().textContent,/关联效果 1 · 触发效果.*8倍/s);
  assert.equal(JSON.stringify(character),before);assert.equal(host.querySelectorAll('audio').length,0);
});

test('a numeric-only skill remains visible and unrelated program rules cannot silently define a base skill variable',()=>{
  const x=setup(),host=el('main'),input={numericDetails:{rows:[damage('成长变量1倍')]},relatedPrograms:[{numericDetails:{rows:[formula(8)]}}]};
  x.window.renderWikiCharacterSummary(host,{name:'无文案',skills:[input]},{},ui,{});
  open(fold(host,'详细数值'));
  const item=host.querySelector('.summary-numeric-item');assert.ok(item);assert.match(item.textContent,/成长变量1 的定义未记录/);assert.doesNotMatch(item.textContent,/8\)/);
  open(fold(host,'成长规则'));assert.match(host.querySelector('.summary-numeric-formula').textContent,/关联效果 1.*8\)/s);
});

test('brief damage values retain zero and never infer a final multiplier from interval counts or hit caps',()=>{
  const attack=damage('4→5倍');attack.values.push(field('命中次数上限','10'));
  const host=setup().mount(skill([attack,damage('0倍',['另一分支'])])),preview=host.querySelector('.summary-numeric-preview');
  assert.match(preview.textContent,/单次倍率 5倍 \/ 0倍/);assert.doesNotMatch(preview.textContent,/20倍|50倍|最终|总倍率/);
  assert.equal(host.querySelectorAll('.summary-numeric-item').length,0);
});

test('dynamic skills keep a readable projected first multiplier while hiding growth rules and the detailed branch list',()=>{
  const yes=['形态切换标记：成立'],no=['形态切换标记：不成立'];
  const first='36.4→42 + 能力1成长(1.75→3.5) + (0 + 2.164948 × 成长变量1)倍';
  const host=setup().mount(skill([formula(99,yes),damage(first,yes),damage('5.5 + 成长变量1倍',yes),formula(10,no),damage(first,no)]));
  const preview=host.querySelector('.summary-numeric-preview');
  assert.match(preview.textContent,/单次倍率（首项） 42 \+ 能力1成长\(3.5\)/);assert.match(preview.textContent,/依条件变化/);
  assert.doesNotMatch(preview.textContent,/99\)|10\)|36.4→42|5.5/);assert.equal(preview.querySelectorAll('.summary-numeric-chip').length,2);
  assert.match(preview.querySelector('.summary-numeric-brief-formula').attributes.title,/2.164948 × 成长变量1/);
  assert.equal(host.querySelectorAll('.summary-numeric-context').length,0);
});

test('fixed and proportional damage preview uses its recorded basis rather than pretending to be a multiplier',()=>{
  const host=setup().mount(skill([row('effect','固定伤害',[field('数值','100')]),
    row('damage','比例伤害',[field('计算基准','目标当前生命'),field('比例','10%')])]));
  const preview=host.querySelector('.summary-numeric-preview');assert.match(preview.textContent,/固定伤害 100/);
  assert.match(preview.textContent,/比例伤害 目标当前生命10%/);assert.doesNotMatch(preview.textContent,/倍率|100倍/);
  assert.equal(host.querySelectorAll('dl').length,0);
});

test('overview reserves a separate variant mount after the identity and forwards the navigation callback',()=>{
  const x=setup(),host=el('main'),character={id:'variant-id',name:'变体入口'},onNavigate=()=>{},calls=[];
  x.window.WFCharacterVariants={mount:(...args)=>calls.push(args)};
  x.window.renderWikiCharacterSummary(host,character,{},ui,{onVariantNavigate:onNavigate});
  const root=host.children[0],variants=host.querySelector('.summary-variants');
  assert.equal(root.children[root.children.indexOf(variants)-1].className,'summary-header');
  assert.equal(calls.length,1);assert.equal(calls[0][0],variants);assert.equal(calls[0][1],character);
  assert.equal(calls[0][2],ui);assert.equal(calls[0][3].onNavigate,onNavigate);
});
