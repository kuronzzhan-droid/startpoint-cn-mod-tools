const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const tick = () => new Promise((resolve)=>setImmediate(resolve));
function setup(hostname='wiki.example') {
  const calls=[], nodes=[];
  const el=(tag,cls='',value='')=>{
    const node={tag,className:cls,textContent:value,children:[],events:{},append(...children){this.children.push(...children);},
      replaceChildren(...children){this.children=children;},setAttribute(){},addEventListener(name,callback){this.events[name]=callback;},remove(){}};
    nodes.push(node);return node;
  };
  const turnstile={render(_host,options){calls.push(['render',options]);return 'widget';},reset(id){calls.push(['reset',id]);},remove(id){calls.push(['remove',id]);}};
  const window={WFCommunity:{message:(error)=>error.message,client:{request:async(url)=>{calls.push(['request',url]);return {token:'test-token'};}}},turnstile};
  const document={createElement:el,documentElement:{dataset:{theme:'light'}},head:{append(){}}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki/community-challenge.js'),'utf8'),{window,document,location:{hostname},setTimeout,clearTimeout});
  return {C:window.WFCommunity,host:el('div'),ui:{el},calls,nodes};
}
test('verification tokens are consumed once and reset after each operation',async()=>{
  const x=setup(), changes=[];
  const challenge=x.C.challenge(x.host,{siteKey:'public-key'},'like_team',x.ui,(ready)=>changes.push(ready));await tick();
  const options=x.calls.find(([kind])=>kind==='render')[1];
  assert.equal(options.action,'like_team');assert.equal(options['response-field'],false);
  assert.equal(options.language,'zh-cn');
  options.callback('single-use');assert.equal(challenge.take(),'single-use');assert.equal(challenge.take(),'');
  challenge.reset();assert.deepEqual(x.calls.at(-1),['reset','widget']);assert.equal(changes.at(-1),false);
  options.callback('next-token');options['expired-callback']();assert.equal(challenge.take(),'');
  challenge.destroy();assert.deepEqual(x.calls.at(-1),['remove','widget']);
  challenge.reset();assert.deepEqual(x.calls.at(-1),['remove','widget']);
  options.callback('late-token');assert.equal(challenge.take(),'');
});
test('development verification never activates on a public hostname',async()=>{
  const x=setup();x.C.challenge(x.host,{development:true,siteKey:'production-key'},'like_team',x.ui);await tick();
  assert.equal(x.calls.filter(([kind])=>kind==='render').length,1);
  assert.equal(x.calls.filter(([kind])=>kind==='request').length,0);
});
test('explicit local verification requires a user action and receives only one token',async()=>{
  const x=setup('127.0.0.1');const challenge=x.C.challenge(x.host,{development:true},'like_team',x.ui);await tick();
  assert.equal(challenge.take(),'');assert.equal(x.calls.length,0);
  const button=x.nodes.find((node)=>node.textContent==='本机测试：完成验证');await button.events.click();
  assert.deepEqual(x.calls[0],['request','/development-challenge?action=like_team']);
  assert.equal(challenge.take(),'test-token');assert.equal(challenge.take(),'');
});
test('closing before asynchronous render prevents creating an orphan widget',async()=>{
  const x=setup();const challenge=x.C.challenge(x.host,{siteKey:'key'},'like_team',x.ui);challenge.destroy();await tick();
  assert.equal(x.calls.filter(([kind])=>kind==='render').length,0);
});
