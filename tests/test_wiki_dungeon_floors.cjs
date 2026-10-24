const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {Node: BaseNode} = require('./wiki_equipment_fixture.cjs');
class Node extends BaseNode {
  constructor(...args) {super(...args); this.dataset = {};}
  querySelectorAll(selector) {return this.all(node => selector.split(',').some(part => part.trim().startsWith('.')
    ? node.className.split(' ').includes(part.trim().slice(1)) : node.tag === part.trim()));}
  querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
  async fire(name, extra = {}) {for (const callback of this.events[name] || []) await callback({target:this, preventDefault(){}, ...extra});}
}
const normal = 'event-rush-700099', fantasy = 'event-rush-700098';
const guide = (id, text = '') => ({guide:{id, text, revision:0, teamIds:[], imageIds:[], images:[]}, teams:[]});
function setup(responder = async route => route === '/admin/me' ? null : guide(route.split('/').at(-1))) {
  const document = new Node('document'), el = (...args) => Object.assign(new Node(...args), {document});
  const host = el('main'); document.append(host);
  const calls = [], window = {location:{hash:'#dungeons', href:'http://localhost/#dungeons', origin:'http://localhost', protocol:'http:'},
    WFCommunity:{client:{request:async(...args) => {calls.push(args); return responder(...args);}}, message:error => error.message || '错误'}};
  const context = {window, document, URL, URLSearchParams, AbortController, setTimeout, clearTimeout};
  for (const file of ['dungeons-floors.js', 'dungeons.js', 'dungeons-admin.js']) vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki', file), 'utf8'), context);
  const item = {id:normal, title:'深渊连战', category:'模式', quests:[{name:'深渊连战 第1战', element:'暗'},
    {name:'深渊连战 第2战'}, {name:'深渊连战 第30战'}, {name:'深渊连战 无尽'}]};
  const data = {dungeons:{items:[item]}};
  return {window, host, data, item, calls, find:cls=>host.querySelector(cls),
    button(label){return host.all(node=>node.tag==='button' && node.textContent===label)[0];},
    render:()=>window.renderWikiDungeons(host, data, {el}, {id:normal})};
}

test('scopes use actual floor numbers and special entries, never arbitrary quest order or unsupported modes', () => {
  const x = setup(), scopes = x.window.WFDungeonFloors.scopes;
  assert.deepEqual(Array.from(scopes(x.item), item=>item.id), [normal, `${normal}-floor-1`, `${normal}-floor-2`, `${normal}-floor-30`, `${normal}-floor-endless`]);
  assert.equal(scopes({...x.item, id:'boss-1-99'}).length, 0);
  const entries = scopes({id:fantasy, title:'幻想', quests:[{name:'第15关 最终协力·始龙之眼'}, {name:'第1关 圣诞试炼·雪像'},
    {name:'第1层 重复'}, {name:'第16关 不在快照中'}, {name:'练习模式'}, {name:'无尽'}]});
  assert.deepEqual(Array.from(entries, item=>item.id), [fantasy, `${fantasy}-floor-1`, `${fantasy}-floor-15`, `${fantasy}-floor-practice`]);
});

test('only the selected scope loads and revisiting it does not refetch or query other floors', async () => {
  const x = setup(); await x.render();
  assert.deepEqual(x.calls.map(call=>call[0]), ['/admin/me', `/dungeons/${normal}`]);
  await x.button('第 2 层').fire('click');
  assert.equal(x.calls.length, 3); assert.equal(x.calls[2][0], `/dungeons/${normal}-floor-2`);
  await x.button('第 30 层').fire('click'); await x.button('第 2 层').fire('click');
  assert.equal(x.calls.length, 4);
  const visible = x.host.querySelectorAll('.dungeon-floor-panel').filter(panel=>!panel.hidden);
  assert.equal(visible.length, 1); assert.ok(visible[0].textContent.includes('深渊连战 · 第 2 层'));
  assert.equal(x.button('第 2 层').attributes['aria-pressed'], 'true');
});

test('switching floors preserves editor drafts and save targets with independent revisions', async () => {
  const x = setup(async (route, body, method) => {
    if (route === '/admin/me') return {id:'admin', email:'admin@example.test', role:'editor'};
    const result = guide(route.split('/').at(-1));
    return method === 'PATCH' ? {...result, guide:{...result.guide, ...body, revision:body.expectedRevision + 1}} : result;
  });
  await x.render(); await x.button('编辑攻略与推荐队伍').fire('click');
  const original = x.find('.dungeon-editor'), draft = original.querySelector('.dungeon-guide-input'); draft.value='通用未保存草稿';
  await x.button('第 1 层').fire('click');
  const firstPanel = x.host.querySelectorAll('.dungeon-floor-panel').find(panel=>!panel.hidden);
  await firstPanel.all(node=>node.tag==='button' && node.textContent==='编辑攻略与推荐队伍')[0].fire('click');
  const firstEditor = firstPanel.querySelector('.dungeon-editor'); firstEditor.querySelector('.dungeon-guide-input').value='只用于第一层';
  await firstEditor.fire('submit');
  const request = x.calls.find(call=>call[2]==='PATCH');
  assert.equal(request[0], `/admin/dungeons/${normal}-floor-1`); assert.equal(request[1].expectedRevision, 0);
  await x.button('通用攻略').fire('click');
  assert.equal(draft.value, '通用未保存草稿'); assert.ok(original.isConnected);
  await original.fire('submit');
  assert.equal(x.calls.at(-1)[0], `/admin/dungeons/${normal}`); assert.equal(x.calls.at(-1)[1].text, '通用未保存草稿');
  assert.equal(x.calls.filter(call=>call[0]==='/admin/me').length, 1);
});

test('late response for a hidden floor cannot replace the visible floor or survive leaving the page', async () => {
  let firstResponse; const x = setup(async route => {
    if (route.endsWith('-floor-1')) return new Promise(resolve=>{firstResponse=resolve;});
    return route === '/admin/me' ? null : guide(route.split('/').at(-1), '已读取');
  });
  await x.render(); const pending = x.button('第 1 层').fire('click');
  await x.button('第 2 层').fire('click'); firstResponse(guide(`${normal}-floor-1`, '第一层延迟响应')); await pending;
  const visible = x.host.querySelectorAll('.dungeon-floor-panel').find(panel=>!panel.hidden);
  assert.ok(!visible.textContent.includes('第一层延迟响应'));
  await x.button('第 1 层').fire('click'); assert.ok(x.host.querySelectorAll('.dungeon-floor-panel').find(panel=>!panel.hidden).textContent.includes('第一层延迟响应'));
  const another = setup(async route=>route === '/admin/me' ? null : new Promise(resolve=>{firstResponse=resolve;}));
  const rendering = another.render(); another.window.location.hash='#team'; another.host.replaceChildren();
  firstResponse(guide(normal, '过期响应')); await rendering;
  assert.equal(another.host.textContent, '');
});
