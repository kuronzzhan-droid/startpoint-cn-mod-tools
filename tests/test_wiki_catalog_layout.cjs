const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Node {
  constructor(tag) {Object.assign(this, {tag, children:[], dataset:{}, attrs:{}, listeners:{}});}
  append(...children) {this.children.push(...children);}
  setAttribute(key,value) {this.attrs[key] = value;}
  closest() {return null;}
  replaceWith(node) {this.replacement = node;}
  addEventListener(type,fn) {this.listeners[type] = fn;}
  dispatchEvent(event) {this.listeners[event.type]?.(event);}
  click() {this.dispatchEvent({type:'click'});}
}
const storageKey = 'wf-wiki-catalog-layout-v2';
function setup(saved, blocked = false, existingStorage) {
  const catalog = new Node('section'), control = new Node('select');
  const storage = existingStorage || new Map(saved ? [[storageKey, saved]] : []), changes = [];
  catalog.addEventListener('cataloglayoutchange', () => changes.push(catalog.dataset.layout));
  const document = {getElementById:id=>id==='catalog-view'?catalog:control,createElement:tag=>new Node(tag)};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki/catalog-layout.js'), 'utf8'), {
    document, Event: class {constructor(type) {this.type = type;}},
    localStorage:{getItem:key=>{if(blocked)throw Error();return storage.get(key);},
      setItem:(key,value)=>{if(blocked)throw Error();storage.set(key,value);}},
  });
  return {catalog,group:control.replacement,storage,changes,buttons:control.replacement.children.filter(n=>n.tag==='button')};
}

test('portrait layout restores independently and changes notify the catalogue exactly once', () => {
  const x = setup('portrait');
  assert.equal(x.catalog.dataset.layout,'portrait');
  assert.deepEqual(x.buttons.map(b=>b.attrs['aria-label']), ['立绘','标准','致密']);
  assert.equal(x.buttons[0].attrs['aria-pressed'],'true');
  assert.equal(x.changes.length,0);
  x.buttons[0].click();assert.equal(x.changes.length,0);
  x.buttons[1].click();x.buttons[2].click();x.buttons[0].click();
  assert.deepEqual(x.changes,['standard','dense','portrait']);
  assert.equal(x.storage.get(storageKey),'portrait');
  assert.equal(x.buttons.filter(b=>b.attrs['aria-pressed']==='true').length,1);
});

test('four, nine and twelve-cell icons retain accessible names and independent layout values', () => {
  const x=setup();
  assert.deepEqual(x.buttons.map(button=>button.dataset.layout),['portrait','standard','dense']);
  assert.deepEqual(x.buttons.map(button=>button.title),['立绘','标准','致密']);
  assert.deepEqual(x.buttons.map(button=>button.children[0].children.length),[4,9,12]);
  x.buttons.forEach(button=>{
    assert.equal(button.type,'button');assert.equal(button.children[0].attrs['aria-hidden'],'true');
    assert.match(button.className,/catalog-layout-icon-button/);
  });
});

test('legacy dense and portrait choices migrate to standard once, then new selections persist on return', () => {
  for (const legacy of ['dense','portrait']) {
    const storage=new Map([['wf-wiki-catalog-layout',legacy]]), first=setup(undefined,false,storage);
    assert.equal(first.catalog.dataset.layout,'standard');assert.equal(storage.get(storageKey),'standard');
    assert.equal(storage.get('wf-wiki-catalog-layout'),legacy);assert.deepEqual(first.changes,[]);
    first.buttons[0].click();
    const returned=setup(undefined,false,storage);assert.equal(returned.catalog.dataset.layout,'portrait');assert.deepEqual(returned.changes,[]);
    returned.buttons[2].click();assert.equal(setup(undefined,false,storage).catalog.dataset.layout,'dense');
  }
});

test('obsolete choices and unavailable storage retain usable layout controls', () => {
  for (const blocked of [false,true]) {
    const x = setup('extra-large',blocked);
    assert.equal(x.catalog.dataset.layout,'standard');
    x.buttons[0].click();
    assert.equal(x.catalog.dataset.layout,'portrait');
    assert.deepEqual(x.changes,['portrait']);
  }
});
