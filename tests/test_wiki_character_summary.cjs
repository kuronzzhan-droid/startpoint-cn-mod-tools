const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Node {
  constructor(tag, className = '', text = '') {
    Object.assign(this, {tag, className, ownText: String(text), children: [], dataset: {}, attributes: {}, events: {}});
  }
  append(...nodes) {this.children.push(...nodes);}
  replaceChildren(...nodes) {this.children = nodes;}
  setAttribute(name, value) {this.attributes[name] = value;}
  addEventListener(name, callback) {this.events[name] = callback;}
  click() {this.events.click?.();}
  get textContent() {return this.ownText + this.children.map((node) => node.textContent).join('');}
  querySelectorAll(selector) {
    return this.children.flatMap((node) => [
      ...(selector.startsWith('.') ? node.className.split(' ').includes(selector.slice(1)) : node.tag === selector) ? [node] : [],
      ...node.querySelectorAll(selector),
    ]);
  }
}
const el = (tag, cls, value) => new Node(tag, cls, value);
const ui = {el, list: (v) => Array.isArray(v) ? v : [], object: (v) => v && typeof v === 'object' ? v : {},
  text: (v, fallback = '') => v == null || v === '' ? fallback : String(v), formatNumber: String,
  picture: () => el('img'), nativeIcon: () => el('img'), elementBadge: (v) => el('span', '', v), rarityBadge: () => el('span')};
const window = {renderWikiAbilityRows(host, entry) {
  host.append(el('p', '', entry.rows?.map((row) => row.description).join(' ') || entry.description)); return true;
}};
for (const file of ['character-levels.js', 'character-summary.js']) {
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki', file), 'utf8'), {window});
}

test('overview defaults to max, changes all effects and retains the selected skill form', () => {
  const source = {name:'测试角色', stats:{levels:[{level:1,hp:100,atk:10},{level:100,hp:1000,atk:200}]},
    skills:[{kind:'main',level:'1',name:'普通',gauge:600,gaugeMin:650},
      {kind:'main',level:'2',name:'进化',gauge:500,gaugeMin:550},
      {kind:'switched',level:'2',name:'切换',gauge:400,gaugeMin:450}],
    leader:{descriptionSource:'数据行自动解析',description:'攻击 10%→20%',rows:[{description:'攻击 10%→20%'}]},
    abilities:[1,2,3,4,5,6].map((slot) => ({slot,rows:[{description:`能力${slot} 5%→10%`}]}))};
  const snapshot = JSON.stringify(source), host = el('main'), calls = [];
  window.renderWikiCharacterSummary(host, source, {}, ui, {onOpenDetails: (tab) => calls.push(tab)});
  const one = (selector) => host.querySelectorAll(selector)[0];
  const levelButtons = one('.summary-level-toolbar').querySelectorAll('button');
  assert.equal(levelButtons[1].attributes['aria-pressed'],'true');
  assert.match(one('.summary-skill-body').textContent,/进化满技能等级所需能量500/);
  assert.match(one('.summary-leader').textContent,/攻击 20%/);
  const stats = one('.summary-fields').textContent;
  one('.summary-skill-choices').querySelectorAll('button')[2].click();
  levelButtons[0].click();
  assert.equal(levelButtons[0].attributes['aria-pressed'],'true');
  assert.match(one('.summary-skill-body').textContent,/切换初始技能等级所需能量（沿用对应形态）450/);
  assert.match(one('.summary-leader').textContent,/攻击 10%/);
  host.querySelectorAll('.summary-ability').forEach((row, index) => assert.match(row.textContent,new RegExp(`能力${index+1} 5%`)));
  assert.match(one('.summary-leader').textContent,/初始值仅取明确记录/);
  levelButtons[1].click();
  assert.match(one('.summary-skill-body').textContent,/切换满技能等级所需能量（沿用对应形态）400/);
  assert.equal(one('.summary-fields').textContent,stats);
  assert.equal(JSON.stringify(source),snapshot);
  assert.equal(host.querySelectorAll('audio').length,0);
  assert.equal(host.querySelectorAll('table').length,0);
  host.querySelectorAll('.summary-detail-button').forEach((button) => button.click());
  assert.deepEqual(calls,['profile','skills','skills','voices']);
});
