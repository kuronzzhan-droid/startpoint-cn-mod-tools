const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {Node} = require('./wiki_equipment_fixture.cjs');
const policy = require('../wiki/rating-score.js');
function setup() {
  const sort=new Node('select'),button=new Node('button'),characters=[{id:'a',name:'A',rarity:5},{id:'b',name:'B',rarity:3},{id:'c',name:'C',rarity:4},{id:'d',name:'D',rarity:5}];
  sort.value='rating';let changes=0;
  const records={a:{average:5,voters:1},b:{average:4.5,voters:100},c:{average:2.5,voters:5}};
  Object.values(records).forEach(item=>item.rankScore=policy.score(item.average,item.voters));
  const views={a:0,b:200,c:50};
  const window={WFCharacterOrder:{compare:(a,b)=>a.id.localeCompare(b.id)}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki/catalog-sort.js'),'utf8'),{window});
  const controller=window.WFCatalogSort.create({sort,button,ratings:{isRatingSort:()=>sort.value==='rating',compare:(a,b,direction)=>policy.compare(records[a.id],records[b.id],direction)},
    views:{compare(a,b,direction){const av=views[a.id],bv=views[b.id];if((av===undefined)!==(bv===undefined))return av===undefined?1:-1;return av===undefined?0:(av-bv)*(direction==='asc'?1:-1);}},onChange:()=>changes++});
  return{sort,button,controller,records,order:()=>[...characters].sort(controller.compare).map(item=>item.id),changes:()=>changes};
}
test('default score desc uses adjusted vote confidence and direction changes independently of criterion',()=>{
  const x=setup();assert.equal(x.controller.getDirection(),'desc');assert.deepEqual(x.order(),['b','a','c','d']);
  x.button.fire('click');assert.equal(x.sort.value,'rating');assert.equal(x.button.attributes['aria-pressed'],'true');
  assert.deepEqual(x.order(),['c','a','b','d']);x.sort.value='views';x.sort.fire('change');
  assert.equal(x.controller.getDirection(),'asc');assert.deepEqual(x.order(),['a','c','b','d']);
  x.button.fire('click');assert.deepEqual(x.order(),['b','c','a','d']);assert.equal(x.changes(),3);
});
test('ties prioritize more voters in both directions; standard criteria use stable opaque ID ties',()=>{
  const x=setup();x.records.a={rankScore:2.5,voters:8};x.records.b={rankScore:2.5,voters:12};
  assert.deepEqual(x.order(),['b','a','c','d']);x.button.fire('click');assert.deepEqual(x.order(),['b','a','c','d']);
  x.sort.value='rarity';assert.deepEqual(x.order(),['b','c','a','d']);x.button.fire('click');assert.deepEqual(x.order(),['a','d','c','b']);
  x.sort.value='name';assert.deepEqual(x.order(),['d','c','b','a']);x.button.fire('click');assert.deepEqual(x.order(),['a','b','c','d']);
  x.sort.value='default';assert.deepEqual(x.order(),['a','b','c','d']);
});
test('the real entry lists score then views, defaults to score and loads both helpers before app',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../wiki/index.html'),'utf8');
  assert.match(html,/<select id="sort-order"><option value="rating" selected>评分<\/option><option value="views">查看次数<\/option>/);
  assert.match(html,/id="sort-direction"[^>]*aria-pressed="false"/);
  for(const name of ['catalog-ratings.js','catalog-views.js','catalog-sort.js'])assert.ok(html.indexOf(`src="${name}`)<html.indexOf('src="app.js'));
});
