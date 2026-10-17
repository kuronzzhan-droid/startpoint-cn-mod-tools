const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
class Node {
  constructor(tag, cls = '', value = '') {
    Object.assign(this, {tag, className: cls, ownText: String(value), children: [], events: {}, attributes: {}, value: '', open: false, hidden: false, pauses: 0});
    this.classList = {add: (cls) => {this.className += ` ${cls}`;}};
  }
  append(...nodes) {nodes.forEach((node) => {node.parent = this; this.children.push(node);});}
  replaceChildren(...nodes) {this.children.forEach((node) => {node.parent = null;}); this.children = []; this.ownText = ''; this.append(...nodes);}
  setAttribute(key, value) {this.attributes[key] = value;}
  get firstChild() {return this.children[0];}
  get textContent() {return this.ownText + this.children.map((node) => node.textContent).join('');}
  set textContent(value) {this.replaceChildren(); this.ownText = String(value);}
  addEventListener(event, action) {this.events[event] = action;}
  fire(event) {return this.events[event]?.();}
  pause() {this.pauses++; this.paused = true;}
  play() {this.paused = false; this.fire('play');}
  querySelectorAll(selector) {return this.children.flatMap((node) => [...(selector.startsWith('.')
    ? node.className.split(' ').includes(selector.slice(1)) : node.tag === selector) ? [node] : [], ...node.querySelectorAll(selector)]);}
  querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
}
const voice = (label, category = '主页', extra = {}) => ({slot: 'home/home_1', label, category,
  ja: '原文', zh: '中文台词', audio: `media/${encodeURIComponent(label)}.mp3`, textSource: 'current-speech', ...extra});
const fixtures = [voice('加入队伍', '加入与觉醒', {slot:'ally/join'}), voice('觉醒', '加入与觉醒', {slot:'ally/evolution'}),
  voice('主页 1'), voice('技能发动 1', '战斗', {slot:'相关技能'}), voice('登录 1', '登录'),
  voice('未标场景', '', {slot:'unknown'}), voice('已收录 MOD 台词', '剧情')];
function setup(entries = fixtures) {
  const window = {}, target = new Node('section');
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki/voices.js'), 'utf8'), {window});
  window.renderWikiVoices(target, entries, {name:'测试角色', origin:'新增MOD'}, {
    el: (...args) => new Node(...args), text: (value, fallback = '') => value === undefined || value === null || value === '' ? fallback : String(value),
    safeUrl: (value) => typeof value === 'string' && /^(?:media\/|https?:\/\/)/.test(value) ? value : '', safeData: (value) => value,
  });
  const open = (node, value = true) => {node.open = value; node.fire('toggle'); return node;};
  const select = (label) => target.querySelectorAll('select').find((node) => node.attributes['aria-label'] === label);
  return {target, open, cards: () => target.querySelectorAll('.voice-card'), groups: () => target.querySelectorAll('.voice-group'),
    audio: () => target.querySelectorAll('audio'), search: target.querySelector('input'),
    category: select('语音场景筛选'), translation: select('台词完整度筛选'),
    count: target.querySelector('.voice-match-count'), more: target.querySelector('.voice-load-more')};
}

test('existing scenes become foldable groups without inferring awakening stages or eagerly creating audio/text bodies', () => {
  const original = JSON.stringify(fixtures), x = setup();
  assert.deepEqual(x.groups().map((node) => node.querySelector('.voice-group-label').textContent), ['加入与觉醒', 'Home · 主页', '战斗语音', '登录语音', '其他', '剧情']);
  assert.ok(x.groups().every((node) => node.tag === 'details' && !node.open));
  assert.ok(x.cards().every((node) => node.tag === 'details' && !node.open && node.children.length === 1));
  assert.equal(x.audio().length, 0); assert.equal(x.target.querySelectorAll('.voice-entry-body').length, 0);
  assert.match(x.target.querySelector('.voice-stage-note').textContent, /未标注觉醒前后阶段/);
  assert.ok(x.groups().every((node) => !['觉醒前', '觉醒后'].includes(node.querySelector('.voice-group-label').textContent)));
  assert.equal(JSON.stringify(fixtures), original); assert.equal(x.cards().length, fixtures.length);
});

test('opening a row creates one native preload-none player and complete subtitles; closing pauses and reopening reuses it', () => {
  const x = setup([voice('长台词', '主页', {ja:'一行\n二行', zh:'第一行\n第二行', textSource:'current-speech + hash-matched-original'})]);
  const card = x.cards()[0]; x.open(card); const audio = x.audio()[0];
  assert.equal(audio.preload, 'none'); assert.equal(audio.controls, true); assert.equal(audio.src, 'media/%E9%95%BF%E5%8F%B0%E8%AF%8D.mp3');
  assert.match(card.textContent, /一行\n二行/); assert.match(card.textContent, /第一行\n第二行/);
  assert.match(card.textContent, /游戏内字幕 \+ 音频匹配原版台词/);
  audio.play(); x.open(card, false); assert.equal(audio.paused, true);
  x.open(card); assert.equal(x.audio().length, 1); assert.equal(x.audio()[0], audio);
});

test('playing another row stops previous audio, and collapsing its category pauses its player', () => {
  const x = setup([voice('主页'), voice('战斗', '战斗')]);
  x.cards().forEach((card) => x.open(card)); const [first, second] = x.audio();
  first.play(); assert.equal(first.paused, false); second.play(); assert.equal(first.paused, true); assert.equal(second.paused, false);
  x.open(x.groups()[1], false); assert.equal(second.paused, true);
});

test('pagination stays at 24 rows, appends without reopening categories or replacing existing players, and includes every supplied record', () => {
  const entries = Array.from({length: 51}, (_, index) => voice(`语音${index}`, index % 2 ? '战斗' : '主页'));
  const x = setup(entries), original = x.cards()[0]; x.open(original); const audio = x.audio()[0];
  assert.equal(x.cards().length, 24); assert.match(x.count.textContent, /51 条，已显示 24 条/);
  x.open(x.groups()[0], false); x.more.fire('click');
  assert.equal(x.cards().length, 48); assert.equal(x.groups()[0].open, false); assert.equal(x.cards()[0], original); assert.equal(x.audio()[0], audio);
  x.more.fire('click'); assert.equal(x.cards().length, 51); assert.equal(x.more.hidden, true);
  assert.equal(new Set(x.cards().map((card) => card.querySelector('.voice-entry-label').textContent)).size, 51);
  assert.deepEqual(x.groups().map((group) => group.querySelector('.voice-group-count').textContent), ['26 / 26 条', '25 / 25 条']);
});

test('search, scene selection and translation filters combine, reset pagination and pause removed players', () => {
  const x = setup([voice('温暖', '主页', {zh:'特定台词'}), voice('待补', '主页', {zh:''}), voice('战斗', '战斗', {zh:'特定台词'})]);
  x.open(x.cards()[0]); const audio = x.audio()[0]; audio.play();
  x.search.value = 'HOME'; x.search.fire('input'); assert.equal(x.cards().length, 2); assert.equal(audio.paused, true); assert.equal(x.audio().length, 0);
  x.translation.value = 'missing'; x.translation.fire('change'); assert.equal(x.cards().length, 1); assert.match(x.cards()[0].textContent, /待补/);
  x.translation.value = 'translated'; x.translation.fire('change'); assert.equal(x.cards().length, 1); assert.match(x.cards()[0].textContent, /温暖/);
  x.search.value = '特定'; x.search.fire('input'); x.category.value = '战斗'; x.category.fire('change');
  assert.equal(x.cards().length, 1); assert.equal(x.groups()[0].querySelector('.voice-group-label').textContent, '战斗语音');
  x.search.value = '无匹配'; x.search.fire('input'); assert.equal(x.cards().length, 0); assert.match(x.target.textContent, /没有匹配的语音/); assert.equal(x.more.hidden, true);
});

test('missing and unsafe media are explicit, malformed names stay text, and repeat errors add only one warning', () => {
  const x = setup([voice('<script>name</script>', 'constructor', {audio:'javascript:alert(1)', ja:'', zh:'', textSource:''}), voice('可用')]);
  assert.equal(x.groups()[0].querySelector('.voice-group-label').textContent, 'constructor');
  x.open(x.cards()[0]); assert.equal(x.audio().length, 0); assert.match(x.cards()[0].textContent, /本次快照未包含音频文件/);
  assert.match(x.cards()[0].textContent, /原文待补录/); assert.match(x.cards()[0].textContent, /翻译待补录/); assert.equal(x.target.querySelectorAll('script').length, 0);
  x.open(x.cards()[1]); const audio = x.audio()[0]; audio.fire('error'); audio.fire('error');
  assert.equal(x.cards()[1].querySelectorAll('.audio-unavailable').length, 1);
  const empty = setup([]); assert.match(empty.target.textContent, /未找到/); assert.equal(empty.audio().length, 0);
});
