const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const order = require('../wiki/equipment-order.js');
class Node {
  constructor(tag, cls = '', text = '') {Object.assign(this,{tag,className:cls,ownText:text,children:[],events:{},attributes:{},value:''});}
  append(...nodes) {nodes.forEach((node) => {node.remove();node.parent=this;this.children.push(node);});}
  remove() {if(this.parent){this.parent.children=this.parent.children.filter(node=>node!==this);this.parent=null;}}
  replaceChildren(...nodes) {this.children.forEach(node=>node.parent=null);this.children=[];this.ownText='';this.append(...nodes);}
  replaceWith(next) {const index=this.parent.children.indexOf(this);this.parent.children[index]=next;next.parent=this.parent;this.parent=null;}
  setAttribute(key,value) {this.attributes[key]=String(value);}
  addEventListener(name,listener) {(this.events[name]??=new Set()).add(listener);}
  removeEventListener(name,listener) {this.events[name]?.delete(listener);}
  get textContent() {return this.ownText+this.children.map(node=>node.textContent).join('');}
  set textContent(text) {this.replaceChildren();this.ownText=text;}
  get isConnected() {return this.tag==='document'||Boolean(this.parent?.isConnected);}
  contains(other) {return this===other||this.children.some(node=>node.contains(other));}
  focus() {this.document.activeElement=this;}
  all(match) {return this.children.flatMap(node=>[...(match(node)?[node]:[]),...node.all(match)]);}
  fire(name,extra={}) {[...(this.events[name]||[])].forEach(fn=>fn({target:this,preventDefault(){},stopPropagation(){},...extra}));}
}
function environment() {
  const document=new Node('document'),window=new Node('window'),observers=[];
  const el=(...args)=>Object.assign(new Node(...args),{document});
  document.body=el('body');document.append(document.body);const host=el('main');document.body.append(host);
  Object.assign(window,{WFEquipmentOrder:order,WFWikiReadable:{
    lazyDetails(_ui,label,_unused,render){const d=el('details');d.append(el('summary','',label));d.addEventListener('toggle',()=>{if(d.open&&d.children.length===1)render(d);});return d;},
    renderReadable(parent,value){parent.append(el('p','',JSON.stringify(value)));},
  }});
  class MutationObserver {constructor(callback){this.callback=callback;}observe(){observers.push(this);}disconnect(){this.stopped=true;}}
  const storage=new Map();
  const context={window,document,MutationObserver,localStorage:{getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)}};
  ['equipment-attribute-filter.js','equipment-card.js','equipment-page.js'].forEach(file=>vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki',file),'utf8'),context));
  const ui={el,picture:(url,name,cls)=>{const img=el('img',cls,name);img.setAttribute('src',url);return img;},elementBadge:value=>el('span','element-badge',value)};
  return {window,document,host,ui,storage,checkRemoved(){observers.forEach(o=>{if(!o.stopped)o.callback();});}};
}
module.exports={Node,environment};
