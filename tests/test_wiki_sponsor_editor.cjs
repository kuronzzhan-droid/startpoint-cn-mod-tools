const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const community = require('../wiki/community-client.js');
const sponsor = require('../wiki/sponsor.js');
class Node {
  constructor(tag, className = '', text = '') {Object.assign(this, {tag, className, text:String(text), children:[], events:{}, attributes:{}, value:'', checked:false, disabled:false});}
  append(...nodes) {nodes.forEach(node => {node.parent = this; this.children.push(node);});}
  replaceChildren(...nodes) {this.children.forEach(node => node.parent = null); this.children = []; this.text = ''; this.append(...nodes);}
  get textContent() {return this.text + this.children.map(node => node.textContent).join('');}
  set textContent(value) {this.replaceChildren(); this.text = String(value);}
  set innerHTML(_value) {throw new Error('Sponsor content must remain text');}
  setAttribute(key, value) {this.attributes[key] = value;}
  getAttribute(key) {return this.attributes[key];}
  addEventListener(name, callback) {this.events[name] = callback;}
  get isConnected() {return this.connected === true || Boolean(this.parent?.isConnected);}
  async fire(name) {if (name === 'click' && this.disabled) return; return this.events[name]?.({preventDefault(){}});}
  all(selector) {const match = node => selector.startsWith('.') ? node.className.split(' ').includes(selector.slice(1)) : node.tag === selector;
    return this.children.flatMap(node => [...(match(node) ? [node] : []), ...node.all(selector)]);}
}
const el = (...args) => new Node(...args), tick = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => {let resolve, reject; const promise = new Promise((a,b) => {resolve = a; reject = b;}); return {promise, resolve, reject};};
const record = (values = {}) => ({enabled:false, title:'', description:'', imageUrl:'', targetUrl:'', revision:0, updatedAt:null, ...values});
const ready = (values = {}) => record({enabled:true, title:'赞助标题', description:'简短说明', imageUrl:'https://cdn.example.com/banner.png', targetUrl:'https://example.com/', revision:3, updatedAt:1790884800000, ...values});
function setup({request = async () => record(), confirm, renderer = sponsor.createCard} = {}) {
  const calls = [], previews = [], document = {createElement:tag => el(tag)};
  const window = {WFCommunity:{...community}, WFSponsor:{...sponsor, createCard(...args){previews.push(args); return renderer(...args);}},
    ...(confirm ? {WFCommunityAdminConfirm:{ask:confirm}} : {})};
  const send = (route, body, method = body ? 'PATCH' : 'GET') => {calls.push({route, body, method}); return request(route, body, method);};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki/sponsor-editor.js'),'utf8'),
    {window, document, URL, setInterval(){throw new Error('No polling');}, setTimeout(){throw new Error('No polling');}});
  const box = window.WFCommunity.sponsorEditor({ui:{el}, request:send}); box.connected = true;
  return {box, calls, previews, window, status:box.all('.community-status')[0],
    field:label => box.all('input').find(node => node.getAttribute('aria-label') === label),
    button:label => box.all('button').find(node => node.textContent === label),
    open:async () => {box.open = true; await box.fire('toggle'); await tick();}, submit:() => box.all('form')[0].fire('submit')};
}
const echoed = (body, revision = body.expectedRevision + 1) => ({...body, revision, updatedAt:1790884800001});

test('sponsor editor is collapsed, loads on first expansion, never writes or previews while typing', async () => {
  const x = setup({request:async () => ready()});
  assert.equal(x.box.open, false); assert.equal(x.calls.length, 0); assert.equal(x.box.isDirty(), false);
  assert.equal(x.field('广告标题').disabled, true); await x.open();
  assert.deepEqual(x.calls, [{route:'/admin/sponsorship', body:undefined, method:'GET'}]);
  assert.equal(x.field('广告标题').value, '赞助标题'); assert.equal(x.box.isDirty(), false);
  x.field('广告图片地址').value = 'https://cdn.example.com/other.png'; await x.field('广告图片地址').fire('input');
  x.box.open = false; await x.box.fire('toggle'); await x.open();
  assert.equal(x.calls.length, 1); assert.equal(x.previews.length, 0); assert.equal(x.box.all('img').length, 0); assert.equal(x.box.isDirty(), true);
  assert.match(x.box.textContent, /仅站长、副站长/); assert.match(x.box.textContent, /不记录广告点击或曝光/);
});

test('empty configuration has no invented ad and can be saved disabled', async () => {
  const x = setup({request:async (_path, body) => body ? echoed(body) : record()}); await x.open();
  assert.equal(x.field('广告标题').value, ''); assert.equal(x.field('启用赞助广告').checked, false);
  await x.button('预览广告').fire('click'); assert.equal(x.box.all('article').length, 0); assert.match(x.status.textContent, /请先填写/);
  await x.submit(); assert.equal(x.calls.length, 2); assert.equal(x.calls[1].body.enabled, false); assert.equal(x.box.isDirty(), false);
});

test('preview is explicit, non-navigable, works while disabled and is discarded on edit or collapse', async () => {
  const x = setup({request:async () => ready({enabled:false})}); await x.open();
  assert.equal(x.previews.length, 0); await x.button('预览广告').fire('click');
  assert.equal(x.previews.length, 1); assert.equal(x.previews[0][2].preview, true);
  assert.equal(x.box.all('article').length, 1); assert.equal(x.box.all('img').length, 1); assert.equal(x.box.all('a').length, 0);
  assert.equal(x.box.all('img')[0].referrerPolicy, 'no-referrer');
  x.field('广告标题').value = '<img src=x onerror=bad()>'; await x.field('广告标题').fire('input'); assert.equal(x.box.all('img').length, 0);
  await x.button('预览广告').fire('click'); assert.equal(x.box.all('h2')[0].textContent, '<img src=x onerror=bad()>');
  assert.equal(x.box.all('img').length, 1); x.box.open = false; await x.box.fire('toggle'); assert.equal(x.box.all('img').length, 0);
  assert.equal(x.calls.length, 1);
});

test('save sends only editable fields plus expectedRevision and accepts normalized HTTPS and local image receipts', async () => {
  const x = setup({request:async (_path, body) => body ? echoed(body) : record()}); await x.open();
  x.field('广告标题').value = '  e\u0301赞助  '; x.field('简短说明').value = '  内容  ';
  x.field('广告跳转链接').value = ' HTTPS://EXAMPLE.COM '; x.field('广告图片地址').value = `media/${'a'.repeat(64)}.png`;
  x.field('启用赞助广告').checked = true; await x.submit();
  const call = x.calls[1]; assert.equal(call.method, 'PATCH'); assert.equal(call.route, '/admin/sponsorship');
  assert.deepEqual(Object.keys(call.body).sort(), ['description','enabled','expectedRevision','imageUrl','targetUrl','title']);
  assert.equal(call.body.title, 'é赞助'); assert.equal(call.body.description, '内容'); assert.equal(call.body.targetUrl, 'https://example.com/');
  assert.equal(call.body.imageUrl, `/media/${'a'.repeat(64)}.png`); assert.equal(call.body.expectedRevision, 0);
  assert.equal(x.box.isDirty(), false); assert.equal(x.previews.length, 0); assert.match(x.status.textContent, /广告已保存/);
});

test('validation checks code-point limits, enabled prerequisites, control characters and unsafe URLs before any write', async () => {
  const x = setup({request:async (_path, body) => body ? echoed(body) : record()}); await x.open();
  const cases = [
    ['广告标题','😀'.repeat(61),/60/], ['简短说明','😀'.repeat(161),/160/], ['广告标题','a\nb',/换行/],
    ['广告跳转链接','javascript:alert(1)',/HTTPS/], ['广告跳转链接','//example.com/',/HTTPS/],
    ['广告跳转链接','https://user:pass@example.com/',/HTTPS/], ['广告跳转链接','https://localhost/',/HTTPS/],
    ['广告图片地址','https://cdn.example.com/banner.svg',/PNG/], ['广告图片地址','data:image/png;base64,x',/PNG/],
    ['广告图片地址','media/not-a-hash.png',/站内/],
  ];
  for (const [label,value,pattern] of cases) {
    x.field(label).value = value; await x.submit(); assert.equal(x.calls.length, 1); assert.match(x.status.textContent, pattern); x.field(label).value = '';
  }
  x.field('启用赞助广告').checked = true; await x.submit(); assert.equal(x.calls.length, 1); assert.match(x.status.textContent, /填写广告标题/);
  x.field('广告标题').value = '😀'.repeat(60); x.field('简短说明').value = '😀'.repeat(160); x.field('广告跳转链接').value = 'https://example.com/';
  await x.submit(); assert.equal(x.calls.length, 2); assert.equal(x.box.isDirty(), false);
});

test('malformed reads leave fields disabled and explicit reload can recover', async () => {
  for (const bad of [null, {}, record({enabled:'false'}), record({title:5}), ready({revision:-1}), ready({revision:3.5}), ready({updatedAt:'2026-10-02'}), ready({updatedAt:null}), ready({targetUrl:'http://example.com'})]) {
    let valid = false; const x = setup({request:async () => valid ? record() : bad}); await x.open();
    assert.equal(x.field('广告标题').disabled, true); assert.equal(x.button('保存广告').disabled, true);
    valid = true; await x.button('重新读取').fire('click'); assert.equal(x.field('广告标题').disabled, false); assert.equal(x.calls.length, 2);
  }
});

test('strict save receipts preserve draft on wrong revision, field values or timestamp', async () => {
  for (const change of [result => ({...result, revision:8}), result => ({...result, title:'其他内容'}), result => ({...result, enabled:'true'}), result => ({...result, updatedAt:null})]) {
    const x = setup({request:async (_path, body) => body ? change(echoed(body)) : ready()}); await x.open();
    x.field('广告标题').value = '未保存草稿'; await x.submit();
    assert.equal(x.field('广告标题').value, '未保存草稿'); assert.equal(x.box.isDirty(), true); assert.doesNotMatch(x.status.textContent, /广告已保存/);
    assert.match(x.status.textContent, /重新读取/);
  }
});

test('conflict retains draft and prevents another write until an explicit confirmed reload', async () => {
  let discard = false, reads = 0; const x = setup({confirm:async () => discard, request:async (_path, body) => {
    if (body) throw Object.assign(new Error('冲突'), {status:409, code:'edit_conflict'}); return ready({title:++reads === 1 ? '原广告' : '他人新广告', revision:reads + 2});
  }}); await x.open(); x.field('广告标题').value = '我的草稿'; await x.submit();
  assert.equal(x.field('广告标题').value, '我的草稿'); assert.equal(x.button('保存广告').disabled, true); assert.match(x.status.textContent, /其他管理员/);
  await x.submit(); await x.button('重新读取').fire('click'); assert.equal(x.calls.length, 2); assert.equal(x.field('广告标题').value, '我的草稿');
  discard = true; await x.button('重新读取').fire('click'); assert.equal(x.calls.length, 3); assert.equal(x.field('广告标题').value, '他人新广告');
  assert.equal(x.button('保存广告').disabled, false); assert.equal(x.box.isDirty(), false);
});

test('failed writes retain input and permit explicit retry without automatic network work', async () => {
  let fail = true; const x = setup({request:async (_path, body) => {
    if (!body) return ready(); if (fail) throw new Error('网络失败'); return echoed(body);
  }}); await x.open(); x.field('广告标题').value = '草稿'; await x.submit(); await tick();
  assert.equal(x.calls.length, 2); assert.equal(x.box.isDirty(), true); assert.equal(x.button('保存广告').disabled, false);
  fail = false; await x.submit(); assert.equal(x.calls.length, 3); assert.equal(x.box.isDirty(), false);
});

test('pending reads and saves coalesce repeated actions and block navigation', async () => {
  const reading = deferred(), writing = deferred(); const x = setup({request:(_path, body) => body ? writing.promise : reading.promise});
  const opening = x.open(); await tick(); await x.button('重新读取').fire('click');
  assert.equal(x.calls.length, 1); assert.equal(await x.box.canClose(), false); assert.equal(x.box.isBusy(), true);
  reading.resolve(ready()); await opening; x.field('广告标题').value = '草稿'; const saving = x.submit();
  await x.submit(); await x.button('重新读取').fire('click'); await x.button('预览广告').fire('click');
  assert.equal(x.calls.length, 2); assert.equal(x.previews.length, 0); assert.equal(await x.box.canClose(), false);
  writing.resolve(echoed(x.calls[1].body)); await saving; assert.equal(x.box.isBusy(), false); assert.equal(await x.box.canClose(), true);
});

test('navigation confirmations coalesce and cannot discard a newer edit', async () => {
  const waiting = deferred(); let confirmations = 0; const x = setup({confirm:() => {confirmations++; return waiting.promise;}}); await x.open();
  x.field('广告标题').value = '未保存'; const first = x.box.canClose(), second = x.box.canClose(); assert.equal(first, second); await tick();
  assert.equal(confirmations, 1); assert.equal(x.box.isBusy(), true); await x.submit(); assert.equal(x.calls.length, 1);
  x.field('广告标题').value = '更新的草稿'; waiting.resolve(true); assert.equal(await first, false); assert.equal(x.box.isBusy(), false);
});

test('missing or failing confirmation and preview helpers do not lose drafts or navigate', async () => {
  for (const confirm of [undefined, () => {throw new Error('确认失败');}, async () => false]) {
    const x = setup({confirm, request:async () => ready(), renderer:() => {throw new Error('预览失败');}}); await x.open();
    x.field('广告标题').value = '保留草稿'; assert.equal(await x.box.canClose(), false); assert.equal(x.field('广告标题').value, '保留草稿');
    await x.button('预览广告').fire('click'); assert.match(x.status.textContent, /预览暂不可用/); assert.equal(x.calls.length, 1);
  }
});

test('late reads and saves do not modify detached editors', async () => {
  const pending = deferred(), x = setup({request:() => pending.promise}); const opening = x.open(); await tick();
  x.box.connected = false; pending.resolve(ready()); await opening; assert.equal(x.field('广告标题').value, '');
  const write = deferred(), y = setup({request:(_path, body) => body ? write.promise : Promise.resolve(ready())}); await y.open();
  y.field('广告标题').value = '离开前草稿'; const saving = y.submit(); y.box.connected = false;
  write.resolve(echoed(y.calls[1].body)); await saving; assert.equal(y.field('广告标题').value, '离开前草稿'); assert.equal(y.box.isDirty(), true);
});
