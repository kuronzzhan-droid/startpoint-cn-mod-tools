const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
class Node {
  constructor(tag, cls = '', attributes = {}) {
    Object.assign(this, {nodeType: 1, tag, className: cls, attributes, children: [], listeners: {}, scrollWidth: 100, clientWidth: 100, overflowX: 'visible'});
    this.layoutReads = {scrollWidth: 0, clientWidth: 0, style: 0};
    for (const property of ['scrollWidth', 'clientWidth']) {
      let value = this[property];
      Object.defineProperty(this, property, {get: () => {this.layoutReads[property]++; return value;}, set: next => {value = next;}});
    }
    this.classList = {toggle: (name, on) => {const names = new Set(this.className.split(' ')); on ? names.add(name) : names.delete(name); this.className = [...names].join(' ');}};
  }
  append(node) {node.parentElement = this; this.children.push(node);}
  getAttribute(name) {return this.attributes[name] ?? null;}
  setAttribute(name, value) {this.attributes[name] = value;}
  addEventListener(name, fn) {this.listeners[name] = fn;}
  contains(node) {return node === this || this.children.some(child => child.contains(node));}
  matches(selector) {
    return selector.split(',').some(value => value.startsWith('.') ? this.className.split(' ').includes(value.slice(1))
      : value === '[draggable="true"]' ? this.attributes.draggable === 'true'
      : /^\[role="[^"]+"\]$/.test(value) ? this.attributes.role === value.slice(7, -2)
      : value === '[hidden]' ? this.hidden || this.attributes.hidden !== undefined
      : value.startsWith('[contenteditable]') ? this.attributes.contenteditable !== undefined && this.attributes.contenteditable !== 'false'
      : value === this.tag);
  }
  closest(selector) {for (let node = this; node; node = node.parentElement) if (node.matches(selector)) return node; return null;}
  querySelectorAll(selector) {return this.children.flatMap(node => [...((selector === 'a[href^="#"]' ? node.tag === 'a' : node.matches(selector)) ? [node] : []), ...node.querySelectorAll(selector)]);}
  querySelector(selector) {for (const child of this.children) {if (child.matches(selector)) return child; const nested = child.querySelector(selector); if (nested) return nested;} return null;}
}
function setup(hash = '', width = 390, lateRouter = false) {
  const listeners = {}, changes = {}, mediaChanges = {}, header = new Node('header', 'masthead'), nav = new Node('nav', 'app-navigation');
  header.append(nav);
  for (const path of ['', 'team', 'community', 'weapons', 'dungeons', 'tier-list']) nav.append(new Node('a', '', {href: '#' + path}));
  const main = new Node('main'), content = new Node('div'); main.append(content);
  const media = {matches: width <= 760, addEventListener: (event, fn) => {mediaChanges[event] = fn;}};
  let dialog = null, now = 1000;
  const scrolls = [], document = {activeElement: null, createElement: tag => new Node(tag),
    querySelector: selector => selector === '.app-navigation' ? nav : dialog,
    getElementById: () => main, addEventListener: (name, fn, options) => {listeners[name] = {fn, options};}};
  let currentHash = '';
  const location = {};
  Object.defineProperty(location, 'hash', {get: () => currentHash, set(value) {
    currentHash = value; const path = value.replace(/^#/, ''), prefix = path.split('/')[0];
    const category = prefix === 'character' ? '' : prefix === 'weapon' ? 'weapons'
      : ['shops', 'five-boss'].includes(prefix) ? 'dungeons' : prefix;
    nav.children.forEach(link => link.setAttribute('aria-current', link.getAttribute('href') === '#' + category ? 'page' : 'false'));
  }});
  location.hash = hash ? '#' + hash : '';
  if (lateRouter) nav.children.forEach(link => link.setAttribute('aria-current', 'false'));
  let navChanged;
  const window = {location, innerWidth: width, matchMedia: () => media,
    MutationObserver: class {constructor(fn) {navChanged = fn;} observe() {}},
    getComputedStyle: node => {node.layoutReads.style++; return {overflowX: node.overflowX};}, scrollTo: options => scrolls.push(options),
    addEventListener: (name, fn) => {changes[name] = fn;}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki/mobile-navigation.js'), 'utf8'), {window, document, Date: {now: () => now}});
  function fire(type, target, points, patch = {}) {
    const event = {target, touches: type === 'touchend' ? [] : points, changedTouches: points, cancelable: true, prevented: false, stopped: false,
      preventDefault() {this.prevented = true;}, stopPropagation() {this.stopped = true;}, ...patch};
    listeners[type].fn(event); return event;
  }
  const point = (x, y, identifier = 1) => ({identifier, clientX: x, clientY: y});
  function swipe(target = content, start = [240, 200], end = [110, 205], patch = {}) {
    fire('touchstart', target, [point(...start)]); const move = fire('touchmove', target, [point(...end)], patch);
    fire('touchend', target, [point(...end)]); return move;
  }
  function layoutReads() {
    const reads = {scrollWidth: 0, clientWidth: 0, style: 0};
    function visit(node) {for (const key of Object.keys(reads)) reads[key] += node.layoutReads[key]; node.children.forEach(visit);}
    visit(header); visit(main); return reads;
  }
  return {window, document, nav, main, content, header, media, changes, mediaChanges, listeners, scrolls, fire, point, swipe,
    layoutReads, setDialog: value => {dialog = value;}, later: value => {now += value;}, navChanged: () => navChanged()};
}

test('navigation becomes ready when the initial router loads after the gesture script', () => {
  const x = setup('community', 390, true); assert.doesNotMatch(x.header.className, /mobile-nav-ready/);
  x.window.location.hash = '#community'; x.navChanged(); assert.match(x.header.className, /mobile-nav-ready/);
  x.swipe(x.nav.children[2]); assert.equal(x.window.location.hash, '#weapons');
});
test('mobile header swipes move one adjacent route and content swipes work on browse pages', () => {
  const x = setup('team'); x.swipe(x.nav.children[1]); assert.equal(x.window.location.hash, '#community'); assert.equal(x.scrolls.length, 1);
  x.changes.hashchange(); x.swipe(); assert.equal(x.window.location.hash, '#weapons');
  x.changes.hashchange(); x.swipe(x.content, [100, 200], [240, 205]); assert.equal(x.window.location.hash, '#community');
  assert.match(x.header.className, /mobile-nav-ready/);
});
test('vertical scroll, short movements, taps, slow holds and desktop width never navigate', () => {
  for (const [start, end] of [[[150, 150], [156, 300]], [[150, 150], [125, 150]], [[150, 150], [150, 150]], [[240, 100], [160, 180]]]) {
    const x = setup('weapons'); const move = x.swipe(x.content, start, end); assert.equal(x.window.location.hash, '#weapons');
    if (Math.abs(end[1] - start[1]) >= Math.abs(end[0] - start[0])) assert.equal(move.prevented, false);
  }
  const held = setup(); held.fire('touchstart', held.content, [held.point(240, 100)]); held.later(1300);
  held.fire('touchmove', held.content, [held.point(100, 100)]); held.fire('touchend', held.content, [held.point(100, 100)]);
  assert.equal(held.window.location.hash, '');
  const desktop = setup('weapons', 1280); desktop.swipe(desktop.nav.children[3]); assert.equal(desktop.window.location.hash, '#weapons');
});

test('taps, undecided movements and vertical scrolling do not read layout', () => {
  for (const end of [[240, 100], [234, 102], [236, 180]]) {
    const x = setup('community'), child = new Node('span'); x.content.append(child);
    x.fire('touchstart', child, [x.point(240, 100)]);
    assert.deepEqual(x.layoutReads(), {scrollWidth: 0, clientWidth: 0, style: 0});
    assert.equal(x.fire('touchmove', child, [x.point(...end)]).prevented, false);
    x.fire('touchend', child, [x.point(...end)]);
    assert.deepEqual(x.layoutReads(), {scrollWidth: 0, clientWidth: 0, style: 0});
    assert.equal(x.window.location.hash, '#community');
  }
});

test('confirmed content horizontal intent checks scrolling ancestors only once', () => {
  const x = setup('community'), child = new Node('span'); x.content.append(child);
  x.content.scrollWidth = 500; // Overflow alone is not a native horizontal scroller.
  x.fire('touchstart', child, [x.point(240, 100)]);
  assert.equal(x.fire('touchmove', child, [x.point(234, 102)]).prevented, false);
  assert.deepEqual(x.layoutReads(), {scrollWidth: 0, clientWidth: 0, style: 0});
  assert.equal(x.fire('touchmove', child, [x.point(226, 102)]).prevented, true);
  assert.deepEqual(x.layoutReads(), {scrollWidth: 2, clientWidth: 2, style: 1});
  assert.equal(x.fire('touchmove', child, [x.point(200, 104)]).prevented, true);
  assert.equal(x.fire('touchmove', child, [x.point(110, 105)]).prevented, true);
  x.fire('touchend', child, [x.point(110, 105)]);
  assert.deepEqual(x.layoutReads(), {scrollWidth: 2, clientWidth: 2, style: 1});
  assert.equal(x.window.location.hash, '#weapons');
});
test('all main pages accept touch swipes on safe content, including team and tier pages', () => {
  for (const [hash, expected] of [['', '#team'], ['team', '#community'], ['community', '#weapons'], ['weapons', '#dungeons'], ['dungeons', '#tier-list']]) {
    const x = setup(hash); assert.equal(x.swipe().prevented, true); assert.equal(x.window.location.hash, expected);
  }
  const last = setup('tier-list'); last.swipe(last.content, [100, 100], [240, 105]); assert.equal(last.window.location.hash, '#dungeons');
});
test('team and tier drag zones keep gestures but their header still switches pages', () => {
  for (const hash of ['team', 'tier-list']) {
    const x = setup(hash), board = new Node('div', hash === 'team' ? 'team-board' : 'tier-board'); x.content.append(board);
    assert.equal(x.swipe(board).prevented, false); assert.equal(x.window.location.hash, '#' + hash);
    x.swipe(x.nav.children[hash === 'team' ? 1 : 5], [100, 100], [240, 105]);
    assert.equal(x.window.location.hash, hash === 'team' ? '#' : '#dungeons');
  }
});
test('search forms and hidden old forms do not disable the whole page, but touching a search control does not navigate', () => {
  const x = setup('community'), search = new Node('form', 'community-code-search-form', {role:'search'});
  const input = new Node('input'); search.append(input); x.content.append(search);
  assert.equal(x.swipe(input).prevented, false); assert.equal(x.window.location.hash, '#community');
  x.swipe(); assert.equal(x.window.location.hash, '#weapons');
  const hidden = new Node('section'); hidden.hidden = true; hidden.append(new Node('form')); x.main.append(hidden);
  x.swipe(x.nav.children[3]); assert.equal(x.window.location.hash, '#dungeons');
});
test('read-only details and admin lists swipe their active header category without enabling content gestures', () => {
  for (const [hash, expected] of [['character/c1', '#team'], ['weapon/w1', '#dungeons'], ['dungeons/boss1', '#tier-list'], ['community/admin', '#weapons']]) {
    const x = setup(hash); x.swipe(); assert.equal(x.window.location.hash, '#' + hash);
    x.swipe(x.nav.children[2]); assert.equal(x.window.location.hash, expected);
    assert.match(x.header.className, /mobile-nav-ready/);
  }
});
test('admin editing, login and other drafts block header swipes; accounts routes stay excluded even before their forms load', () => {
  for (const formClass of ['admin-edit-form', 'community-auth-form', 'community-account-create', 'dungeon-editor', 'wiki-aliases-form']) {
    const x = setup('community/admin'); x.main.append(new Node('form', formClass));
    assert.equal(x.swipe(x.nav.children[2]).prevented, false); assert.equal(x.window.location.hash, '#community/admin');
    x.main.children.pop(); x.swipe(x.nav.children[2]); assert.equal(x.window.location.hash, '#weapons');
  }
  for (const hash of ['community/accounts', 'community/accounts/member']) {
    const x = setup(hash); x.swipe(x.nav.children[2]); assert.equal(x.window.location.hash, '#' + hash);
    assert.doesNotMatch(x.header.className, /mobile-nav-ready/);
  }
});
test('inputs, controls, draggable elements, forms, open dialogs and focused editors remain untouched', () => {
  for (const node of [new Node('input'), new Node('textarea'), new Node('button'), new Node('summary'), new Node('form'),
    new Node('div', '', {contenteditable: 'true'}), new Node('a', '', {draggable: 'true'}), new Node('div', '', {role: 'combobox'}), new Node('div', '', {role:'scrollbar'})]) {
    const x = setup('weapons'); x.content.append(node); const child = new Node('span'); node.append(child);
    assert.equal(x.swipe(child).prevented, false); assert.equal(x.window.location.hash, '#weapons');
  }
  const focused = setup('community'); focused.document.activeElement = new Node('input'); focused.swipe(focused.nav.children[2]); assert.equal(focused.window.location.hash, '#community');
  const modal = setup(); modal.setDialog({}); modal.swipe(modal.nav.children[0]); assert.equal(modal.window.location.hash, '');
});
test('mouse and pen drags switch only the narrow-screen header; touch pointers do not duplicate touch events', () => {
  function drag(x, target, pointerType = 'mouse') {
    x.fire('pointerdown', target, [], {pointerType, pointerId:7, isPrimary:true, button:0, clientX:250, clientY:100});
    x.fire('pointermove', target, [], {pointerType, pointerId:7, clientX:120, clientY:105});
    x.fire('pointerup', target, [], {pointerType, pointerId:7, clientX:120, clientY:105});
  }
  for (const pointerType of ['mouse', 'pen']) {
    const x = setup('community'); drag(x, x.content, pointerType); assert.equal(x.window.location.hash, '#community');
    drag(x, x.nav.children[2], pointerType); assert.equal(x.window.location.hash, '#weapons');
    assert.equal(x.fire('click', x.nav.children[2], [], {detail:1, sourceCapabilities:{firesTouchEvents:false}}).prevented, true);
    x.fire('pointerdown', x.nav.children[4], [], {pointerType, pointerId:8, isPrimary:true, button:0, clientX:250, clientY:100});
    x.fire('pointerup', x.nav.children[4], [], {pointerType, pointerId:8, clientX:250, clientY:100});
    assert.equal(x.fire('click', x.nav.children[4], [], {detail:1, sourceCapabilities:{firesTouchEvents:false}}).prevented, false);
  }
  const touch = setup('community'); drag(touch, touch.nav.children[2], 'touch'); assert.equal(touch.window.location.hash, '#community');
  touch.swipe(touch.nav.children[2]); assert.equal(touch.window.location.hash, '#weapons');
  const desktop = setup('community', 1280); drag(desktop, desktop.nav.children[2]); assert.equal(desktop.window.location.hash, '#community');
});
test('swipe navigation honors accepted and rejected draft guards without premature hash or scroll changes', async () => {
  for (const accepted of [true, false]) {
    const x = setup('tier-list'); let settle, calls = 0;
    x.window.WFNavigationGuard = {navigate: destination => {calls++; return new Promise(resolve => {settle = () => {if (accepted) x.window.location.hash = destination; resolve(accepted);};});}};
    x.swipe(x.content, [100, 100], [240, 105]);
    assert.equal(x.window.location.hash, '#tier-list'); assert.equal(x.scrolls.length, 0);
    x.swipe(x.nav.children[5], [100, 100], [240, 105]); assert.equal(calls, 1);
    settle(); await new Promise(setImmediate);
    assert.equal(x.window.location.hash, accepted ? '#dungeons' : '#tier-list'); assert.equal(x.scrolls.length, accepted ? 1 : 0);
  }
});
test('horizontal scrolling containers retain native scrolling while ordinary linked cards can swipe', () => {
  const x = setup('community'), scroller = new Node('div'); scroller.scrollWidth = 500; scroller.clientWidth = 280; scroller.overflowX = 'auto';
  x.content.append(scroller); const link = new Node('a'); scroller.append(link);
  x.fire('touchstart', link, [x.point(240, 100)]);
  assert.deepEqual(x.layoutReads(), {scrollWidth: 0, clientWidth: 0, style: 0});
  // Check the original target's ancestors even if a later event reports another target.
  assert.equal(x.fire('touchmove', x.content, [x.point(210, 102)]).prevented, false);
  const reads = x.layoutReads(); assert.deepEqual(reads, {scrollWidth: 2, clientWidth: 2, style: 1});
  assert.equal(x.fire('touchmove', x.content, [x.point(110, 105)]).prevented, false);
  x.fire('touchend', x.content, [x.point(110, 105)]);
  assert.deepEqual(x.layoutReads(), reads); assert.equal(x.window.location.hash, '#community');
  const ordinary = new Node('a'); x.content.append(ordinary); assert.equal(x.swipe(ordinary).prevented, true); assert.equal(x.window.location.hash, '#weapons');
});
test('browser edge gestures, multi-touch, canceled and already-native scrolling never switch', () => {
  for (const [start, end] of [[[5, 100], [180, 100]], [[385, 100], [200, 100]]]) {
    const x = setup('weapons'); x.swipe(x.content, start, end); assert.equal(x.window.location.hash, '#weapons');
  }
  const multiple = setup(); multiple.fire('touchstart', multiple.content, [multiple.point(240, 100), multiple.point(200, 100, 2)]);
  multiple.fire('touchend', multiple.content, [multiple.point(100, 100)]); assert.equal(multiple.window.location.hash, '');
  const canceled = setup(); canceled.fire('touchstart', canceled.content, [canceled.point(240, 100)]); canceled.fire('touchcancel', canceled.content, []);
  canceled.fire('touchend', canceled.content, [canceled.point(100, 100)]); assert.equal(canceled.window.location.hash, '');
  const native = setup(); native.swipe(native.content, [240, 100], [100, 100], {cancelable: false}); assert.equal(native.window.location.hash, '');
});
test('a swipe suppresses its synthesized click, allows keyboard activation and does not wrap at either end', () => {
  const x = setup(); x.swipe(); const keyboard = x.fire('click', x.content, [], {detail: 0}); assert.equal(keyboard.prevented, false);
  const click = x.fire('click', x.content, [], {detail: 1}); assert.equal(click.prevented, true); assert.equal(click.stopped, true);
  assert.equal(x.fire('click', x.content, [], {detail: 1}).prevented, false);
  const first = setup(); first.swipe(first.nav.children[0], [100, 100], [240, 100]); assert.equal(first.window.location.hash, '');
  const last = setup('tier-list'); last.swipe(last.nav.children[5]); assert.equal(last.window.location.hash, '#tier-list');
});
test('a new tap after swiping is not swallowed by the previous swipe click guard', () => {
  const x = setup(); x.swipe(); const target = new Node('button'); x.main.append(target);
  x.fire('touchstart', target, [x.point(150, 200)]); x.fire('touchend', target, [x.point(150, 200)]);
  const click = x.fire('click', target, [], {detail: 1}); assert.equal(click.prevented, false);
  assert.equal(x.window.location.hash, '#team');
  const hybrid = setup(); hybrid.swipe();
  assert.equal(hybrid.fire('click', hybrid.content, [], {detail: 1, sourceCapabilities: {firesTouchEvents: false}}).prevented, false);
  assert.equal(hybrid.fire('click', hybrid.content, [], {detail: 1, sourceCapabilities: {firesTouchEvents: true}}).prevented, true);
});
test('route or viewport changes cancel in-progress swipes without disturbing later navigation', () => {
  const x = setup(); x.fire('touchstart', x.content, [x.point(240, 100)]); x.window.location.hash = '#community/admin'; x.changes.hashchange();
  x.fire('touchend', x.content, [x.point(100, 100)]); assert.equal(x.window.location.hash, '#community/admin');
  x.window.location.hash = '#weapons'; x.changes.hashchange(); x.fire('touchstart', x.content, [x.point(240, 100)]);
  x.media.matches = false; x.mediaChanges.change(); x.fire('touchend', x.content, [x.point(100, 100)]); assert.equal(x.window.location.hash, '#weapons');
  assert.equal(x.listeners.touchstart.options.passive, true); assert.equal(x.listeners.touchmove.options.passive, false);
});
test('a raw child-route change or a newly opened editor cancels the swipe even while the same header category stays current', () => {
  const x = setup('community/admin'); x.fire('touchstart', x.nav.children[2], [x.point(240, 100)]);
  x.fire('touchmove', x.nav.children[2], [x.point(100, 100)]); x.window.location.hash = '#community/another';
  x.fire('touchend', x.nav.children[2], [x.point(100, 100)]); assert.equal(x.window.location.hash, '#community/another');
  const draft = setup('community/admin'); draft.fire('touchstart', draft.nav.children[2], [draft.point(240, 100)]);
  draft.fire('touchmove', draft.nav.children[2], [draft.point(100, 100)]); draft.main.append(new Node('form', 'admin-edit-form'));
  draft.fire('touchend', draft.nav.children[2], [draft.point(100, 100)]); assert.equal(draft.window.location.hash, '#community/admin');
});
