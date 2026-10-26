const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
class Target {
  constructor() {this.events = new Map();}
  addEventListener(type, listener) {if (!this.events.has(type)) this.events.set(type,new Set());this.events.get(type).add(listener);}
  removeEventListener(type, listener) {this.events.get(type)?.delete(listener);}
  fire(type, extra = {}) {for (const callback of [...(this.events.get(type)||[])]) callback({currentTarget:this,...extra});}
  listeners() {return [...this.events.values()].reduce((total,set)=>total+set.size,0);}
}
class Node extends Target {
  constructor(tag, className='', value='') {
    super();Object.assign(this,{tag,className,textContent:value,children:[],attributes:{},isConnected:true,reads:0});
    this.style={values:new Map(),setProperty:(key,value)=>this.style.values.set(key,value),removeProperty:(key)=>this.style.values.delete(key)};
    this.classList={add:(value)=>{if (!this.className.split(' ').includes(value)) this.className+=` ${value}`;},
      remove:(value)=>{this.className=this.className.split(' ').filter((item)=>item!==value).join(' ');},contains:(value)=>this.className.split(' ').includes(value)};
  }
  append(...nodes) {this.children.push(...nodes);}
  replaceChildren(...nodes) {this.children=nodes;}
  setAttribute(key,value) {this.attributes[key]=value;}
  getAttribute(key) {return this.attributes[key];}
  querySelector(selector) {return this.children.find((node)=>node.tag===selector)||null;}
  getBoundingClientRect() {this.reads+=1;return {left:10,top:20,width:100,height:200};}
}
const before=`media/${'a'.repeat(64)}.webp`, after=`media/${'b'.repeat(64)}.webp`;
const character={id:'119990',code:'private_code',name:'角色甲',portraits:[{label:'觉醒前',url:before},{label:'觉醒后',url:after}]};
function setup({fine=true,reduced=false,narrow=false}={}) {
  const window=new Target(),document=new Target(),fineMedia=new Target(),reduceMedia=new Target(),narrowMedia=new Target(),frames=new Map();
  document.hidden=false;fineMedia.matches=fine;reduceMedia.matches=reduced;narrowMedia.matches=narrow;
  window.matchMedia=(query)=>query.includes('reduced')?reduceMedia:query.includes('max-width')?narrowMedia:fineMedia;
  let next=1,created=0;window.requestAnimationFrame=(callback)=>{const id=next++;frames.set(id,callback);return id;};
  window.cancelAnimationFrame=(id)=>frames.delete(id);
  const ui={el:(...args)=>{created++;return new Node(...args);}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki/portrait-cards.js'),'utf8'),{window,document});
  const api=window.WFPortraitCards.create({ui});
  return {api,window,document,fineMedia,reduceMedia,narrowMedia,frames,created:()=>created,
    flush:()=>{const pending=[...frames.values()];frames.clear();pending.forEach((callback)=>callback());}};
}
const mouse=(card,x=110,y=220,type='pointermove')=>card.fire(type,{pointerType:'mouse',clientX:x,clientY:y});
const serialize=(node)=>JSON.stringify({tag:node.tag,className:node.className,text:node.textContent,attrs:node.attributes,alt:node.alt,children:node.children.map(serialize)});

test('only the selected public portrait is created lazily and awakening can repaint without IDs or another image preload',()=>{
  const x=setup();assert.equal(x.created(),0);assert.equal(x.frames.size,0);
  const node=x.api.picture(character,'before'),first=node.querySelector('img');
  assert.equal(first.getAttribute('src'),before);assert.equal(first.loading,'lazy');assert.equal(first.decoding,'async');assert.equal(first.draggable,false);
  assert.match(first.alt,/角色甲.*觉醒前/);assert.equal(node.children.length,1);
  assert.doesNotMatch(serialize(node),/119990|private_code/);assert.doesNotMatch(serialize(node),new RegExp('b'.repeat(64)));
  x.api.paint(node,character,'before');assert.equal(node.querySelector('img'),first);
  x.api.paint(node,character,'after');assert.equal(node.querySelector('img').getAttribute('src'),after);assert.match(node.querySelector('img').alt,/觉醒后/);
  assert.equal(node.children.length,1);assert.equal(x.frames.size,0);
});

test('unknown or unavailable forms use a labelled fallback and unsafe media URLs never reach an image',()=>{
  const x=setup(),fallback=x.api.picture({portraits:[{label:'觉醒前',url:before}]},'after');
  assert.equal(fallback.querySelector('img').getAttribute('src'),before);assert.match(fallback.title,/未收录觉醒后/);
  const urls=['https://example.com/image.webp','/media/'+ 'a'.repeat(64)+'.webp','media/119990.webp',
    'media/../secret.webp',before+'?token=x','data:image/png;base64,a',before.replace('/','\\')];
  for (const url of urls) {
    const node=x.api.picture({portraits:[{label:'觉醒前',url}]});
    assert.equal(node.querySelector('img'),null);assert.match(node.children[0].textContent,/未收录立绘/);
  }
});

test('failed images show a readable placeholder and can be retried by repainting',()=>{
  const x=setup(),node=x.api.picture(character),image=node.querySelector('img');
  image.fire('error');assert.equal(node.querySelector('img'),null);assert.match(node.children[0].textContent,/无法加载/);
  x.api.paint(node,character);assert.notEqual(node.querySelector('img'),image);assert.equal(node.querySelector('img').getAttribute('src'),before);
  image.fire('error');assert.ok(node.querySelector('img'),'a late error from a replaced image cannot erase the current form');
});

test('mouse moves coalesce into one RAF and one bounds read; leave cancels pending work and restores the card',()=>{
  const x=setup(),card=new Node('a');x.api.attach(card);mouse(card,10,20,'pointerenter');
  for(let i=0;i<20;i++)mouse(card,60+i*3,120+i*5);
  assert.equal(x.frames.size,1);assert.equal(card.reads,1);assert.equal(card.style.values.size,0);
  x.flush();assert.equal(card.style.values.get('--portrait-rotate-y'),'8.00deg');assert.equal(card.style.values.get('--portrait-rotate-x'),'-5.70deg');
  assert.equal(card.style.values.get('--portrait-shift-x'),'8.00px');assert.equal(x.frames.size,0);
  mouse(card,-1000,-1000);x.flush();assert.equal(card.style.values.get('--portrait-rotate-x'),'6.00deg');
  assert.equal(card.style.values.get('--portrait-rotate-y'),'-8.00deg');assert.equal(card.style.values.get('--portrait-shift-y'),'-8.00px');
  mouse(card);assert.equal(x.frames.size,1);card.fire('pointerleave');assert.equal(x.frames.size,0);assert.equal(card.style.values.size,0);
  assert.equal(card.classList.contains('portrait-card-active'),false);
});

test('touch, coarse pointers and reduced motion never animate; preference changes stop an active animation immediately',()=>{
  for(const config of [{fine:false},{reduced:true}]) {
    const x=setup(config),card=new Node('a');x.api.attach(card);mouse(card);assert.equal(x.frames.size,0);assert.equal(card.reads,0);
  }
  const x=setup(),card=new Node('a');x.api.attach(card);card.fire('pointermove',{pointerType:'touch',clientX:1,clientY:1});assert.equal(x.frames.size,0);
  mouse(card);x.flush();assert.ok(card.style.values.size);x.reduceMedia.matches=true;x.reduceMedia.fire('change');assert.equal(card.style.values.size,0);
  x.reduceMedia.matches=false;x.reduceMedia.fire('change');mouse(card);assert.equal(x.frames.size,1);
  x.fineMedia.matches=false;x.fineMedia.fire('change');assert.equal(x.frames.size,0);
});

test('only one card tilts and page lifecycle events stop work without changing anchor access',()=>{
  const x=setup(),one=new Node('a'),two=new Node('a');one.setAttribute('href','#character/c0123456789ab');one.setAttribute('aria-label','角色甲详情');
  x.api.attach(one);x.api.attach(two);mouse(one);x.flush();mouse(two);assert.equal(one.style.values.size,0);x.flush();assert.ok(two.style.values.size);
  for(const event of ['hashchange','resize','scroll']){mouse(two);x.flush();x.window.fire(event);assert.equal(two.style.values.size,0);assert.equal(x.frames.size,0);}
  mouse(two);x.document.hidden=true;x.document.fire('visibilitychange');assert.equal(x.frames.size,0);
  x.document.hidden=false;mouse(one);x.flush();one.fire('blur');assert.equal(one.style.values.size,0);
  assert.equal(one.getAttribute('href'),'#character/c0123456789ab');assert.equal(one.getAttribute('aria-label'),'角色甲详情');
});

test('destroy removes old bindings and RAF, then the same controller can attach fresh cards normally',()=>{
  const x=setup(),old=new Node('a');x.api.attach(old);x.api.attach(old);assert.equal(old.listeners(),5);mouse(old);
  assert.equal(x.frames.size,1);x.api.destroy();assert.equal(x.frames.size,0);assert.equal(old.listeners(),0);
  assert.equal(x.window.listeners()+x.document.listeners()+x.fineMedia.listeners()+x.reduceMedia.listeners()+x.narrowMedia.listeners(),0);
  const fresh=new Node('a');x.api.attach(fresh);mouse(old);assert.equal(x.frames.size,0);mouse(fresh);x.flush();assert.ok(fresh.style.values.size);
  fresh.isConnected=false;mouse(fresh);x.flush();assert.equal(fresh.style.values.size,0);assert.equal(x.frames.size,0);
  x.api.destroy();x.api.destroy();assert.equal(fresh.listeners(),0);
});

test('collapse pauses motion without rebuilding card listeners, then resumes the same portrait safely',()=>{
  const x=setup(),card=new Node('a');x.api.attach(card);mouse(card);x.flush();mouse(card);
  x.api.pause();assert.equal(x.frames.size,0);assert.equal(card.style.values.size,0);assert.equal(card.listeners(),5);
  assert.equal(x.window.listeners()+x.document.listeners()+x.fineMedia.listeners()+x.reduceMedia.listeners()+x.narrowMedia.listeners(),0);
  mouse(card);assert.equal(x.frames.size,0);
  x.api.resume();x.api.resume();mouse(card);assert.equal(x.frames.size,1);x.flush();assert.ok(card.style.values.size);
  assert.equal(card.listeners(),5);x.api.destroy();assert.equal(card.listeners(),0);
});

test('portrait-only styles retain contain fit, safe motion margins, visible keyboard focus and responsive columns',()=>{
  const css=fs.readFileSync(path.join(__dirname,'../wiki/portrait-cards.css'),'utf8');
  assert.match(css,/object-fit:contain/);assert.match(css,/aspect-ratio:3\/4/);assert.match(css,/padding:12px/);
  assert.match(css,/\.portrait-card:focus-visible\{outline:/);assert.match(css,/prefers-reduced-motion:no-preference/);
  assert.match(css,/@media\(max-width:640px\).*repeat\(2,minmax\(0,1fr\)\)/);assert.match(css,/@media\(max-width:360px\)/);
  assert.doesNotMatch(css,/object-fit:cover/);
});

test('only the active portrait image receives 3D motion; its card and frame keep their geometry',()=>{
  const css=fs.readFileSync(path.join(__dirname,'../wiki/portrait-cards.css'),'utf8');
  const transforms=[...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter(([,selector,body])=>/transform:(?:perspective|translate)/.test(body));
  assert.equal(transforms.length,1);
  assert.match(transforms[0][1],/\.portrait-card-active \.portrait-card-image/);
  assert.match(transforms[0][2],/rotateX\(var\(--portrait-rotate-x/);
  assert.match(transforms[0][2],/rotateY\(var\(--portrait-rotate-y/);
  assert.match(css,/#catalog-view \.portrait-card\{[^}]*transform:none/);
  assert.match(css,/\.portrait-card-media>\.portrait-card-image\{[^}]*transform:none/);
});

test('opening overflow cannot restore an intrinsic image minimum that stretches the portrait frame or grid row',()=>{
  const css=fs.readFileSync(path.join(__dirname,'../wiki/portrait-cards.css'),'utf8');
  assert.match(css,/#catalog-view \.portrait-card \.card-art\{[^}]*flex:none;min-height:0;width:100%;aspect-ratio:3\/4/);
  assert.match(css,/\.portrait-card-media\{[^}]*position:absolute;inset:0;[^}]*width:100%;height:100%/);
  const activeRules=[...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter(([,selector])=>selector.includes('.portrait-card-active'));
  for(const [,selector,body] of activeRules){
    assert.doesNotMatch(body,/(?:^|;)(?:width|height|min-height|aspect-ratio|padding|flex):/);
    if(!selector.includes('.portrait-card-image'))assert.doesNotMatch(body,/(?:^|;)transform:/);
  }
});

test('desktop hover portrait breaks through only its active clipping layers and never captures clicks outside the link',()=>{
  const css=fs.readFileSync(path.join(__dirname,'../wiki/portrait-cards.css'),'utf8');
  const desktop=css.slice(css.indexOf('@media(min-width:769px)'),css.indexOf('@media(max-width:640px)'));
  assert.match(desktop,/\.portrait-card-active \.portrait-card-image\{[^}]*z-index:2;[^}]*scale\(1\.32\)/);
  assert.match(desktop,/#catalog-view \.portrait-card-active\{overflow:visible;[^}]*z-index:1/);
  assert.match(desktop,/#catalog-view \.portrait-card-active \.card-art,\.portrait-card-active \.portrait-card-media\{overflow:visible\}/);
  const overflowRules=[...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter(([,selector,body])=>body.includes('overflow:visible'));
  assert.equal(overflowRules.length,2);overflowRules.forEach(([,selector])=>assert.match(selector,/\.portrait-card-active/));
  assert.match(css,/\.portrait-card-media>\.portrait-card-image\{[^}]*pointer-events:none/);
  assert.doesNotMatch(css,/padding:calc|pointer-events:auto/);
  assert.ok((230-12*2)*1.32>230,'1.32 zoom intentionally reaches past the card edge with the original 12px padding');
});

test('static, mobile and non-hover states retain full portraits with all clipping layers closed',()=>{
  const css=fs.readFileSync(path.join(__dirname,'../wiki/portrait-cards.css'),'utf8');
  const outside=css.slice(0,css.indexOf('@media(min-width:769px)'))+css.slice(css.indexOf('@media(max-width:640px)'));
  assert.match(outside,/#catalog-view \.portrait-card\{[^}]*overflow:hidden;transform:none/);
  assert.match(outside,/#catalog-view \.portrait-card \.card-art\{[^}]*overflow:hidden/);
  assert.match(outside,/\.portrait-card-media\{[^}]*padding:12px;overflow:hidden/);
  assert.doesNotMatch(outside,/overflow:visible|scale\(|perspective\(/);
  const frame=fs.readFileSync(path.join(__dirname,'../wiki/character-frame.css'),'utf8');
  assert.match(frame,/\.wf-character-frame::after\{[^}]*z-index:1;pointer-events:none/);
});

test('narrow screens default to static even with a mouse; width changes clear both rendered tilt and pending frames',()=>{
  const x=setup({narrow:true}),card=new Node('a');x.api.attach(card);mouse(card);
  assert.equal(x.frames.size,0);assert.equal(card.reads,0);assert.equal(card.style.values.size,0);
  x.narrowMedia.matches=false;x.narrowMedia.fire('change');assert.equal(x.frames.size,0);
  mouse(card);x.flush();assert.ok(card.style.values.size);assert.equal(card.classList.contains('portrait-card-active'),true);
  x.narrowMedia.matches=true;x.narrowMedia.fire('change');assert.equal(card.style.values.size,0);assert.equal(card.classList.contains('portrait-card-active'),false);
  mouse(card);assert.equal(x.frames.size,0);
  x.narrowMedia.matches=false;x.narrowMedia.fire('change');mouse(card);assert.equal(x.frames.size,1);
  x.narrowMedia.matches=true;x.narrowMedia.fire('change');assert.equal(x.frames.size,0);x.flush();assert.equal(card.style.values.size,0);
  x.api.destroy();assert.equal(x.narrowMedia.listeners(),0);
});

test('mobile styles disable UI animation, transitions and smooth scrolling while preserving media and static transforms',()=>{
  const css=fs.readFileSync(path.join(__dirname,'../wiki/mobile-motion.css'),'utf8');
  const rules=css.replace(/\/\*[\s\S]*?\*\//g,'');
  assert.match(css,/@media\(max-width:768px\)/);
  assert.match(css,/\*,\*::before,\*::after\{[^}]*animation:none!important;transition:none!important;scroll-behavior:auto!important/);
  assert.match(css,/\.character-card:hover,#catalog-view \.portrait-card,\.portrait-card \.portrait-card-image\{transform:none!important;will-change:auto!important/);
  assert.doesNotMatch(rules,/display:none|visibility:hidden|pointer-events|\.pixel|\.voice|audio|img\{/);
  assert.doesNotMatch(css,/\*::after\{[^}]*transform:/,'functional static layout and expanded-arrow transforms must stay intact');
  const portraits=fs.readFileSync(path.join(__dirname,'../wiki/portrait-cards.css'),'utf8');
  assert.match(portraits,/@media\(min-width:769px\) and \(hover:hover\) and \(pointer:fine\) and \(prefers-reduced-motion:no-preference\)/);
});
