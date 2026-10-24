const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const tick = () => new Promise(setImmediate);
const source = (name) => fs.readFileSync(path.join(__dirname, '../wiki', name), 'utf8');
const url = (hex) => `media/pixels/${hex.repeat(64)}.webp`;
const action = (label, hex, poster, extra = {}) => ({kind:'idle',label,url:url(hex),poster:{url:url(poster),width:64,height:64},width:64,height:64,animated:true,...extra});
const index = (actions = [action('待机','a','1'),action('技能准备','b','2',{kind:'skill_ready'})]) => ({format:1,characters:{c1:{poster:{url:url('3')},actions}}});

function setup(manifest) {
  const assigned = [], windowEvents = {}, documentEvents = {};
  class Node {
    constructor(tag, cls = '', value = '') {
      Object.assign(this,{tag,className:cls,ownText:String(value),children:[],attributes:{},events:{},dataset:{},disabled:false,hidden:false});
      this.style = {setProperty:(key,value) => {this.style[key]=value;}};
    }
    append(...nodes) {
      for (const node of nodes) {
        if (node.tag === '#fragment') {this.append(...[...node.children]); continue;}
        node.remove(); node.parent=this; this.children.push(node);
      }
    }
    replaceChildren(...nodes) {this.children.forEach((node)=>{node.parent=null;});this.children=[];this.ownText='';this.append(...nodes);}
    remove() {if(this.parent)this.parent.children=this.parent.children.filter((node)=>node!==this);this.parent=null;}
    setAttribute(key,value) {this.attributes[key]=value;}
    getAttribute(key) {return this.attributes[key];}
    get isConnected() {return Boolean(this.root || this.parent?.isConnected);}
    get textContent() {return this.ownText+this.children.map((node)=>node.textContent).join('');}
    set textContent(value) {this.replaceChildren();this.ownText=String(value);}
    set src(value) {this._src=value;assigned.push({node:this,url:value});}
    get src() {return this._src;}
    addEventListener(name,action) {this.events[name]=action;}
    fire(name,extra={}) {if(!this.disabled)return this.events[name]?.({target:this,preventDefault(){},...extra});}
    all(matches) {return this.children.flatMap((node)=>[...(matches(node)?[node]:[]),...node.all(matches)]);}
    querySelectorAll(selector) {return this.all((node)=>selector.startsWith('.')?node.className.split(' ').includes(selector.slice(1)):node.tag===selector);}
    querySelector(selector) {return this.querySelectorAll(selector)[0]||null;}
  }
  const el=(...args)=>new Node(...args), root=el('html'), head=el('head'), body=el('body');root.root=true;root.append(head,body);
  const document={head,hidden:false,createElement:el,createDocumentFragment:()=>el('#fragment'),addEventListener:(event,fn)=>{documentEvents[event]=fn;}};
  const window={addEventListener:(event,fn)=>{windowEvents[event]=fn;},...(manifest?{WF_PIXEL_PREVIEWS:manifest}:{})};
  const context={window,document};vm.runInNewContext(source('pixel-previews.js'),context);
  const ui={el,list:(value)=>Array.isArray(value)?value:[],object:(value)=>value&&typeof value==='object'?value:{},
    text:(value,fallback='')=>value===undefined||value===null||value===''?fallback:String(value),safeUrl:(value)=>typeof value==='string'?value:'',
    picture:(_url,_alt,cls)=>el('img',cls),formatNumber:(value)=>value??'—',rarityBadge:()=>el('span'),nativeIcon:()=>el('span'),
    categoryName:()=>'官方原版',elementBadge:()=>el('span')};
  const host=()=>{const node=el('section');body.append(node);return node;};
  return {window,document,assigned,ui,host,context,api:window.WFPixelPreviews,scripts:()=>head.querySelectorAll('script'),
    route:()=>windowEvents.hashchange(),hidden:()=>{document.hidden=true;documentEvents.visibilitychange();}};
}
const button=(host,label)=>host.all((node)=>node.tag==='button'&&node.textContent===label)[0];
const image=(host)=>host.querySelector('.pixel-preview-image');

test('loading is deferred until mount, failed concurrent loads can retry with a fresh script, and success uses only a poster',async()=>{
  const x=setup();assert.equal(x.scripts().length,0);const first=x.host(),second=x.host();
  const a=x.api.mount(first,{id:'c1',name:'甲'},x.ui),b=x.api.mount(second,{id:'c1',name:'乙'},x.ui);
  assert.equal(x.scripts().length,1);assert.equal(x.scripts()[0].src,'data/pixel-previews.js');
  x.scripts()[0].onerror();await Promise.all([a,b]);assert.equal(x.scripts().length,0);
  assert.match(first.textContent,/暂时无法载入/);assert.ok(button(first,'重新加载像素预览'));
  button(first,'重新加载像素预览').fire('click');assert.equal(x.scripts().length,1);
  x.window.WF_PIXEL_PREVIEWS=index();x.scripts()[0].onload();await tick();
  assert.equal(image(first).src,url('1'));assert.equal(x.assigned.filter((row)=>row.node.tag==='img'&&row.url===url('a')).length,0);
});

test('invalid manifest responses reset loading state and can be retried; removed views do not receive late UI',async()=>{
  const x=setup(),host=x.host();const first=x.api.mount(host,{id:'c1',name:'甲'},x.ui);
  x.window.WF_PIXEL_PREVIEWS={format:9};x.scripts()[0].onload();await first;
  button(host,'重新加载像素预览').fire('click');assert.equal(x.scripts().length,1);host.remove();
  x.window.WF_PIXEL_PREVIEWS=index();x.scripts()[0].onload();await tick();assert.equal(image(host),null);
});

test('default selection and action changes show each action own first frame; animation starts only after explicit play',async()=>{
  const x=setup(index()),host=x.host();await x.api.mount(host,{id:'c1',name:'甲'},x.ui);
  assert.equal(image(host).src,url('1'));assert.equal(button(host,'停止').disabled,true);
  button(host,'播放动作').fire('click');assert.equal(image(host).src,url('a'));
  button(host,'技能准备').fire('click');assert.equal(image(host).src,url('2'));assert.equal(button(host,'停止').disabled,true);
  assert.equal(button(host,'技能准备').getAttribute('aria-pressed'),'true');
  assert.ok(!x.assigned.some((row)=>row.node===image(host)&&row.url===url('b')));
  button(host,'播放动作').fire('click');assert.equal(image(host).src,url('b'));
  button(host,'停止').fire('click');assert.equal(image(host).src,url('2'));
});

test('playback is exclusive across instances and stops on route changes and document hiding',async()=>{
  const x=setup(index()),first=x.host(),second=x.host();
  await x.api.mount(first,{id:'c1',name:'甲'},x.ui);await x.api.mount(second,{id:'c1',name:'乙'},x.ui);
  button(first,'播放动作').fire('click');button(second,'播放动作').fire('click');
  assert.equal(image(first).src,url('1'));assert.equal(image(second).src,url('a'));assert.equal(button(first,'停止').disabled,true);
  x.route();assert.equal(image(second).src,url('1'));button(first,'播放动作').fire('click');x.hidden();assert.equal(image(first).src,url('1'));
});

test('the real detail page mounts preview only on its tab and stops it when selecting another tab',async()=>{
  const x=setup(index()),host=x.host();vm.runInNewContext(source('detail.js'),x.context);
  x.window.renderWikiCharacter(host,{id:'c1',name:'甲'}, {},x.ui);
  assert.equal(image(host),null);button(host,'像素·动作').fire('click');await tick();
  assert.equal(image(host).src,url('1'));button(host,'播放动作').fire('click');assert.equal(image(host).src,url('a'));
  button(host,'资料').fire('click');assert.equal(image(host).src,url('1'));
  assert.equal(host.all((node)=>node.id==='panel-pixels')[0].hidden,true);
});

test('out-of-scope animation and poster URLs are never assigned; missing action posters cannot borrow another action first frame',async()=>{
  const bad=['https://outside.invalid/a.webp','/media/pixels/'+ 'a'.repeat(64)+'.webp',
    'media/pixels/../a.webp','media/pixels/'+ 'a'.repeat(64)+'.webp?x=1','data:image/webp;base64,AAAA'];
  const actions=bad.flatMap((value,i)=>[action(`非法动画${i}`,'a','1',{url:value}),action(`非法首帧${i}`,'b','2',{poster:{url:value}})]);
  actions.push(action('缺少首帧','a','1',{poster:undefined}),action('合法动作','c','4'));
  const x=setup(index(actions)),host=x.host();await x.api.mount(host,{id:'c1',name:'甲'},x.ui);
  assert.equal(image(host).src,url('4'));assert.deepEqual(host.querySelector('.pixel-preview-tools').children.map((node)=>node.textContent),['合法动作']);
  assert.ok(x.assigned.filter((row)=>row.node.tag==='img').every((row)=>/^media\/pixels\/[a-f0-9]{64}\.webp$/.test(row.url)));
});

test('animated image failures can retry, while static actions remain non-playable after a failed poster',async()=>{
  const x=setup(index()),host=x.host();await x.api.mount(host,{id:'c1',name:'甲'},x.ui);
  button(host,'播放动作').fire('click');image(host).fire('error');assert.equal(button(host,'播放动作').disabled,false);
  button(host,'播放动作').fire('click');assert.equal(image(host).src,url('a'));
  const staticView=x.host();x.window.WF_PIXEL_PREVIEWS=index([action('静态动作','a','1',{animated:false})]);
  await x.api.mount(staticView,{id:'c1',name:'乙'},x.ui);assert.equal(button(staticView,'播放动作').disabled,true);
  image(staticView).fire('error');assert.equal(button(staticView,'播放动作').disabled,true);
  button(staticView,'静态动作').fire('click');assert.equal(image(staticView).src,url('1'));
});
