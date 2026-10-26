const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Node {
  constructor(tag, className = '', value = '') {
    Object.assign(this, {tag, className, textContent:value, children:[], dataset:{}, attributes:{}, events:{}});
  }
  append(...nodes) { nodes.forEach(node=>{node.parent=this;this.children.push(node);}); }
  replaceChildren(...nodes) { this.children.forEach(node=>node.parent=null);this.children=[];this.append(...nodes); }
  get isConnected() {return Boolean(this.root || this.parent?.isConnected);}
  setAttribute(key, value) { this.attributes[key] = value; }
  getAttribute(key) { return this.attributes[key]; }
  addEventListener(key, callback) { this.events[key] = callback; }
  click() { this.events.click?.(); }
  querySelectorAll(selector) {
    return this.children.flatMap((node) => [
      ...(selector === '[data-catalog-avatar]' ? node.dataset.catalogAvatar != null : node.tag === selector) ? [node] : [],
      ...node.querySelectorAll(selector),
    ]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}
const el = (tag, cls, value) => new Node(tag, cls, value);
const characters = [{id:'c1', icon:'media/first.webp', avatars:{before:'media/first.webp',after:'media/second.webp'}},
  {id:'c2', icon:'media/single.webp', avatars:{before:'media/single.webp'}}, {id:'c3',icon:'media/legacy.webp'}];
function setup(saved, blocked = false) {
  const storage = new Map(saved ? [['wf-wiki-catalog-avatar', saved]] : []);
  const window = {}, catalog = el('main'), host = el('div');catalog.root=true;host.root=true;
  let imageCalls=0;
  const ui = {el, safeUrl:(v) => typeof v === 'string' && !v.startsWith('javascript:') ? v : '',
    picture:(url) => { imageCalls++;const img = el('img'); img.setAttribute('src',url); return img; }};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki/catalog-avatars.js'),'utf8'), {window,
    localStorage:{getItem:(key) => {if (blocked) throw Error(); return storage.get(key);},
      setItem:(key,value) => {if (blocked) throw Error(); storage.set(key,value);}}});
  const changes = [];
  const api = window.WFCatalogAvatars.create({host,catalog,characters,ui,onChange:form=>changes.push(form)});
  const cards = characters.map((character) => { const card = el('a'); card.append(api.picture(character)); catalog.append(card); return card; });
  return {api, catalog, host, cards, buttons:host.querySelectorAll('button'), storage, window, ui, changes,get imageCalls(){return imageCalls;}};
}
const src = (node) => node.querySelector('img').getAttribute('src');

test('a single toggle updates every catalogue avatar without rebuilding cards or changing other views', () => {
  const {cards,catalog,buttons,storage} = setup();
  const unrelatedTeam = el('img'); unrelatedTeam.setAttribute('src','media/team.webp');
  const source = JSON.stringify(characters), firstCards = [...catalog.children];
  assert.equal(src(cards[0]),'media/first.webp');
  assert.equal(buttons[0].attributes['aria-pressed'],'true');
  buttons[1].click();
  assert.equal(src(cards[0]),'media/second.webp');
  assert.equal(src(cards[1]),'media/single.webp');
  assert.equal(src(cards[2]),'media/legacy.webp');
  assert.match(cards[1].children[0].title,/未收录/);
  assert.equal(buttons[1].attributes['aria-pressed'],'true');
  assert.equal(storage.get('wf-wiki-catalog-avatar'),'after');
  assert.deepEqual(catalog.children,firstCards);
  assert.equal(unrelatedTeam.getAttribute('src'),'media/team.webp');
  assert.equal(JSON.stringify(characters),source);
  buttons[0].click();
  assert.equal(src(cards[0]),'media/first.webp');
});

test('persisted preference applies to new and filtered catalogue cards', () => {
  const {cards,api,buttons} = setup('after');
  assert.equal(src(cards[0]),'media/second.webp');
  assert.equal(buttons[1].attributes['aria-pressed'],'true');
  assert.equal(src(api.picture(characters[0])),'media/second.webp');
});

test('portrait consumers can read the saved form and update only when the choice changes', () => {
  const x = setup('after');
  assert.equal(x.api.getForm(), 'after');
  assert.deepEqual(x.changes, []);
  x.buttons[1].click();
  assert.deepEqual(x.changes, []);
  x.buttons[0].click();
  assert.equal(x.api.getForm(), 'before');
  assert.deepEqual(x.changes, ['before']);
  assert.equal(src(x.cards[0]), 'media/first.webp');
});

test('unavailable storage and obsolete settings still allow both choices', () => {
  for (const [saved,blocked] of [['invalid',false],['after',true]]) {
    const {cards,buttons} = setup(saved,blocked);
    assert.equal(src(cards[0]),'media/first.webp');
    buttons[1].click();
    assert.equal(src(cards[0]),'media/second.webp');
  }
});

test('team and community controls reuse the saved choice and preserve portrait presentation', () => {
  const x = setup(); x.buttons[1].click();
  const catalog = el('main'), host = el('div');
  catalog.root=true;host.root=true;
  const other = x.window.WFCatalogAvatars.create({host,catalog,characters,ui:x.ui,label:'编队头像'});
  const portrait = other.picture(characters[0],'角色一','team-slot-image'); catalog.append(portrait);
  assert.equal(src(portrait),'media/second.webp');
  assert.match(portrait.className,/team-slot-image/);assert.equal(portrait.dataset.avatarAlt,'角色一');
  assert.equal(host.children[0].attributes['aria-label'],'编队头像');
  host.querySelectorAll('button')[0].click();
  assert.equal(src(portrait),'media/first.webp');
  assert.equal(portrait.querySelector('img').draggable,false);
  assert.equal(src(x.cards[0]),'media/first.webp');
  assert.equal(x.buttons[0].attributes['aria-pressed'],'true');
  assert.equal(x.storage.get('wf-wiki-catalog-avatar'),'before');
});

test('shared setter and old controls broadcast one change to every mounted view and subscriber',()=>{
  const x=setup(),api=x.window.WFCatalogAvatars,notifications=[];
  const unsubscribe=api.subscribe(form=>notifications.push(form));
  api.setForm('after');assert.equal(api.getForm(),'after');assert.equal(x.api.getForm(),'after');
  assert.equal(src(x.cards[0]),'media/second.webp');assert.equal(x.buttons[1].attributes['aria-pressed'],'true');
  api.setForm('after');assert.deepEqual(x.changes,['after']);assert.deepEqual(notifications,['after']);
  x.buttons[0].click();assert.equal(api.getForm(),'before');assert.deepEqual(notifications,['after','before']);
  unsubscribe();api.setForm('after');assert.deepEqual(notifications,['after','before']);
});

test('detached controllers are pruned on broadcasts and no longer repaint or receive callbacks',()=>{
  const x=setup();x.host.replaceChildren();const before=x.imageCalls;
  x.window.WFCatalogAvatars.setForm('after');assert.equal(x.imageCalls,before);assert.deepEqual(x.changes,[]);
  assert.equal(src(x.cards[0]),'media/first.webp');
  const host=el('div'),catalog=el('main');host.root=true;catalog.root=true;
  const next=x.window.WFCatalogAvatars.create({host,catalog,characters,ui:x.ui});catalog.append(next.picture(characters[0]));
  assert.equal(src(catalog),'media/second.webp');host.querySelectorAll('button')[0].click();
  assert.equal(src(catalog),'media/first.webp');assert.deepEqual(x.changes,[]);
});

test('switching while a catalogue is unmounted does not create images or reopen the list',()=>{
  const x=setup();x.catalog.replaceChildren();x.catalog.hidden=true;const before=x.imageCalls;
  x.window.WFCatalogAvatars.setForm('after');assert.equal(x.catalog.hidden,true);assert.equal(x.catalog.children.length,0);
  assert.equal(x.imageCalls,before);assert.equal(x.buttons[1].attributes['aria-pressed'],'true');
  assert.equal(src(x.api.picture(characters[0])),'media/second.webp');
});
