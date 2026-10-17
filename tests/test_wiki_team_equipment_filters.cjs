const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
class Node {
  constructor(tag, cls = '', text = '') {Object.assign(this,{tag,className:cls,ownText:text,children:[],events:{},attributes:{},value:''});}
  append(...children) {this.children.push(...children);}
  setAttribute(key, value) {this.attributes[key] = value;}
  addEventListener(name, listener) {this.events[name] = listener;}
  all(match) {return this.children.flatMap((node) => [...(match(node) ? [node] : []), ...node.all(match)]);}
  fire(name) {this.events[name]?.();}
}
const equipment = [
  {id:'fire',name:'测试剑',aliases:['FIRE'],element:'火',rarity:5,soul:{available:true}},
  {id:'water',name:'水弓',element:'水',rarity:4,soul:{available:true}},
  {id:'without-soul',name:'火之专属',element:'火',rarity:4,soul:{available:false}},
  {id:'universal',name:'水色之剑',element:'通用/未分类',rarity:5,soul:{available:true}},
  {id:'unknown',name:'火之未知',rarity:3,soul:{available:true}},
];
function fixture(initialState, aliases = {}) {
  const window = {WFWikiAliases: {values: (_kind, id) => aliases[id] || [], watch() {}}}, updates = [];
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki/team-equipment-filters.js'),'utf8'),{window});
  const control = window.WFTeamEquipmentFilters.create({equipment,initialState,ui:{el:(...args) => new Node(...args)},onStateChange:(state) => updates.push(state)});
  const find = (label) => control.element.all((node) => node.attributes['aria-label'] === label)[0];
  return {control,updates,find,ids:() => equipment.filter(control.matches).map((item) => item.id)};
}
test('equipment attributes come only from metadata, including universal and unlabelled groups', () => {
  const x = fixture(); assert.equal(x.ids().length,5);
  x.find('武器火属性').fire('click'); assert.deepEqual(x.ids(),['fire','without-soul']);
  x.find('武器通用/未分类属性').fire('click'); assert.deepEqual(x.ids(),['universal']);
  x.find('武器未标注属性').fire('click'); assert.deepEqual(x.ids(),['unknown']);
});
test('weapon and soul share attribute, rarity and search state without hiding unavailable souls', () => {
  const x = fixture(); x.find('武器火属性').fire('click');
  const stars = x.find('配队武器星级'); stars.value = '5'; stars.fire('change');
  const search = x.find('配队武器搜索'); search.value = 'ＦＩＲＥ 测试'; search.fire('input');
  assert.deepEqual(x.ids(),['fire']);
  x.control.setMode('soul'); assert.deepEqual(x.ids(),['fire']);assert.equal(x.find('配队魂珠搜索').value,'ＦＩＲＥ 测试');
  search.value='';search.fire('input');stars.value='';stars.fire('change');assert.deepEqual(x.ids(),['fire','without-soul']);
  x.find('魂珠水属性').fire('click');assert.deepEqual(x.ids(),['water']);
  x.control.setMode('weapon');assert.deepEqual(x.ids(),['water']);assert.equal(x.control.getState().element,'水');
});

test('reset clears shared filters and invalid legacy restored filters cannot hide everything', () => {
  const x = fixture({weapon:{element:'not-real',rarity:'6'},soul:{element:'水'}});
  assert.equal(x.ids().length,5);x.control.setMode('soul');assert.equal(x.ids().length,5);
  x.find('魂珠水属性').fire('click');assert.deepEqual(x.ids(),['water']);
  x.control.element.all((node) => node.tag === 'button' && node.ownText === '重置筛选')[0].fire('click');
  assert.equal(x.ids().length,5);assert.equal(x.updates.at(-1).element,'');
  x.control.setMode('weapon');assert.equal(x.ids().length,5);
});

test('administrator nicknames participate in both equipment pickers and clearing them removes search matches', () => {
  const aliases = {fire:['火神剑']};
  const x = fixture({weapon:{search:'火神剑'},soul:{search:'火神剑'}},aliases);
  assert.deepEqual(x.ids(),['fire']);x.control.setMode('soul');assert.deepEqual(x.ids(),['fire']);
  aliases.fire=[];assert.deepEqual(x.ids(),[]);
});
