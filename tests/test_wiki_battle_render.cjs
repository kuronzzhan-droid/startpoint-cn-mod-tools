const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {Node:Base}=require('./wiki_equipment_fixture.cjs');
const file=path.join(__dirname,'../wiki/battle-render.js');
function setup(width=320,dpr=3,callbacks={}){
 const contexts=[],observers=[],listeners=new Map();
 class Node extends Base{
  constructor(...args){super(...args);this.dataset={};this.style={setProperty:(k,v)=>{this.style[k]=String(v);}};this.clientWidth=width;this.srcWrites=0;
   this.classList={add:c=>{if(!this.className.split(' ').includes(c))this.className+=' '+c;},remove:c=>{this.className=this.className.split(' ').filter(x=>x!==c).join(' ');},
    toggle:(c,on)=>{if(on)this.classList.add(c);else this.classList.remove(c);}};
   if(this.tag==='canvas'){const calls=[];this.context=new Proxy({calls},{get:(o,k)=>k in o?o[k]:(...args)=>calls.push([k,...args])});contexts.push(this.context);}
  }
  getAttribute(k){return this.attributes[k]??null;}
  removeAttribute(k){delete this.attributes[k];}
  set src(v){this._src=v;this.srcWrites++;}get src(){return this._src;}
  getContext(){return this.context;}
 }
 const document=new Node('document'),host=new Node('main');document.append(host);
 const window={devicePixelRatio:dpr,addEventListener:(k,f)=>listeners.set(k,f),removeEventListener:k=>listeners.delete(k),
  ResizeObserver:class{constructor(cb){this.cb=cb;observers.push(this);}observe(node){this.node=node;}disconnect(){this.stopped=true;}}};
 document.createElement=tag=>new Node(tag);
 const el=(...args)=>new Node(...args),content={characters:{},media:{},coffin:{url:'media/coffin.webp',width:64,height:64,anchorX:32,anchorY:37}};
 for(let i=0;i<6;i++){const id='c'+i;content.characters[id]={id,name:'角色'+i,title:'称号'+i,stats:{deployCost:20},skill:{name:'技能'+i,cooldown:20,cost:15}};
  content.media[id]={avatar:`media/avatar${i}.webp`,actions:{idle:{url:`media/idle${i}.webp`,width:24,height:32,anchorX:12,anchorY:30,animated:true,poster:{url:`media/poster${i}.webp`,width:24,height:32,anchorX:12,anchorY:30}},
   skill_ready:{url:`media/cast${i}.webp`,width:48,height:70,anchorX:30,anchorY:60,animated:true,duration:1,poster:{url:`media/cast-poster${i}.webp`,width:48,height:70,anchorX:30,anchorY:60}}}};
 }
 const state={squad:Object.keys(content.characters),content,status:'running',tick:0,time:0,energy:60,baseHp:100,wave:1,mode:'campaign',stageId:'fire',units:[],enemies:[],coffins:[]};
 const unit=(id=1,characterId='c0')=>({id,characterId,x:2.5,y:4.5,col:2,row:4,hp:90,maxHp:100,readyAtTick:20,statuses:[]});
 const enemy=(id=10,rank='boss')=>({id,characterId:'c1',x:2.5,y:1.5,hp:200,maxHp:400,rank,statuses:[]});
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki/battle-vfx.js'),'utf8'),{window,document});
 if(fs.existsSync(file))vm.runInNewContext(fs.readFileSync(file,'utf8'),{window,document});
 assert.equal(typeof window.WFBattleRender?.create,'function','battle renderer must be implemented');
 const renderer=window.WFBattleRender.create({host,content,ui:{el},...callbacks});
 const nodes=cls=>host.all(n=>n.className.split(' ').includes(cls));
 return {renderer,state,unit,enemy,content,host,window,contexts,observers,listeners,nodes,resize(w){observers[0].cb([{contentRect:{width:w}}]);}};
}

test('board exposes 35 grid controls and stable six-card roster without changing model state',()=>{
 const x=setup(),before=JSON.stringify(x.state);x.renderer.draw(x.state);
 const cells=x.renderer.board.all(n=>n.tag==='button');assert.equal(cells.length,35);
 assert.equal(new Set(cells.map(n=>`${n.dataset.col},${n.dataset.row}`)).size,35);
 assert.ok(cells.every(n=>n.getAttribute('aria-label')));
 const cards=[...x.renderer.roster.children];assert.equal(cards.length,6);
 assert.ok(cards.every(n=>n.dataset.gesture==='deploy'&&n.dataset.characterId));
 assert.equal(x.renderer.energyDisplay.dataset.gesture,undefined);assert.equal(x.renderer.energyDisplay.tag,'div');
 x.renderer.draw(x.state);assert.deepEqual(x.renderer.roster.children,cards);assert.equal(JSON.stringify(x.state),before);
});

test('existing sprite, health and source nodes update in place while unchanged frames do not restart animated images',()=>{
 const x=setup();x.state.units=[x.unit()];x.renderer.draw(x.state);
 const sprite=x.nodes('battle-entity')[0],image=x.nodes('battle-sprite')[0],writes=image.srcWrites;
 x.state.tick=20;x.state.units[0].hp=45;x.renderer.draw(x.state);
 assert.equal(x.nodes('battle-entity')[0],sprite);assert.equal(x.nodes('battle-sprite')[0],image);assert.equal(image.srcWrites,writes);
 assert.match(sprite.className,/is-ready/);assert.equal(x.nodes('battle-health')[0].getAttribute('aria-valuenow'),'45');
 const cell=x.renderer.board.all(n=>n.dataset.unitId==='1')[0];assert.ok(cell);assert.match(cell.getAttribute('aria-label'),/角色0/);
});

test('idle and skill images preserve one scale and common world foot anchor, with static posters while paused',()=>{
 const x=setup();x.state.units=[x.unit()];x.renderer.draw(x.state);const image=x.nodes('battle-sprite')[0];
 const idleScale=parseFloat(image.style.width)/24;
 assert.equal(parseFloat(image.style.left)+12*idleScale,0);assert.equal(parseFloat(image.style.top)+30*idleScale,0);
 x.renderer.draw(x.state,[{id:1,type:'cast',entityId:1,tick:0}]);
 assert.equal(image.src,'media/cast0.webp');const castScale=parseFloat(image.style.width)/48;
 assert.ok(Math.abs(castScale-idleScale)<1e-8);assert.ok(Math.abs(parseFloat(image.style.left)+30*castScale)<1e-8);
 assert.ok(Math.abs(parseFloat(image.style.top)+60*castScale)<1e-8);
 x.state.status='paused';x.renderer.draw(x.state);assert.equal(image.src,'media/cast-poster0.webp');
 x.state.status='running';x.state.tick=21;x.renderer.draw(x.state);assert.equal(image.src,'media/idle0.webp');
});
test('large skill effect canvas does not shrink a small idle actor',()=>{
 const x=setup(300),media=x.content.media.c0;media.actions.idle={...media.actions.idle,width:17,height:18,anchorX:8,anchorY:16};media.actions.skill_ready={...media.actions.skill_ready,width:92,height:94,anchorX:47,anchorY:76};
 x.state.units=[x.unit()];x.renderer.draw(x.state);const img=x.nodes('battle-sprite')[0],scale=parseFloat(img.style.width)/17;assert.ok(parseFloat(img.style.width)>40);
 x.renderer.draw(x.state,[{id:1,type:'cast',entityId:1,tick:0}]);assert.ok(Math.abs(parseFloat(img.style.width)/92-scale)<1e-8);
});

test('death replaces a unit with the native coffin, simulation countdown and locked roster without healing or ready UI',()=>{
 const x=setup();x.state.units=[x.unit()];x.renderer.draw(x.state);
 x.state.units=[];x.state.coffins=[{unitId:1,characterId:'c0',col:2,row:4,releaseAtTick:400}];x.renderer.draw(x.state);
 const corpse=x.nodes('battle-coffin')[0];assert.ok(corpse);assert.equal(x.nodes('battle-entity').length,0);
 const image=corpse.all(n=>n.tag==='img')[0];assert.equal(image.src,'media/coffin.webp');assert.equal(image.style.width,'128px');
 assert.match(corpse.textContent,/20/);assert.equal(x.renderer.roster.children[0].disabled,true);
 x.state.tick=20;x.renderer.draw(x.state);assert.match(corpse.textContent,/19/);
 x.state.coffins=[];x.state.tick=400;x.renderer.draw(x.state);assert.equal(x.nodes('battle-coffin').length,0);
 assert.equal(x.renderer.roster.children[0].disabled,false);
});

test('bosses and vanguards have different visual scale and independently updated health',()=>{
 const x=setup();x.state.enemies=[x.enemy(10),x.enemy(11,'vanguard')];x.renderer.draw(x.state);
 assert.equal(x.nodes('battle-boss').length,1);assert.equal(x.nodes('battle-vanguard').length,1);
 const images=x.nodes('battle-sprite');assert.ok(parseFloat(images[0].style.width)>parseFloat(images[1].style.width));
 assert.match(x.host.textContent,/先锋/);assert.match(x.host.textContent,/Boss/);
});
test('boss HUD and state badges reflect live HP and real status expiry instead of effect animation lifetime',()=>{
 const x=setup();x.state.enemies=[x.enemy()];x.state.units=[x.unit()];x.state.units[0].hp=20;
 x.state.units[0].statuses=[{type:'shield',remaining:20,until:10},{type:'attackUp',ratio:.2,until:30},{type:'slow',ratio:.2,until:20}];x.renderer.draw(x.state);
 assert.equal(x.nodes('battle-boss-hud')[0].hidden,false);assert.equal(x.nodes('battle-boss-track')[0].getAttribute('aria-valuenow'),'200');
 const ally=x.nodes('battle-ally')[0];assert.match(ally.className,/has-shield/);assert.match(ally.className,/is-low-health/);
 assert.equal(x.nodes('battle-status-icon').filter(n=>!n.hidden).length,3);
 x.state.tick=10;x.renderer.draw(x.state);assert.doesNotMatch(ally.className,/has-shield/);assert.equal(x.nodes('battle-status-icon').filter(n=>!n.hidden).length,2);
 x.state.enemies=[];x.state.tick=31;x.renderer.draw(x.state);assert.equal(x.nodes('battle-boss-hud')[0].hidden,true);assert.equal(x.nodes('battle-status-icon').filter(n=>!n.hidden).length,0);
});
test('wave banners and short hit feedback expire on simulation ticks and stay fixed during pause',()=>{
 const x=setup();x.state.units=[x.unit()];x.renderer.draw(x.state,[{id:1,type:'damage',targetId:1,value:10,tick:0,position:{x:2.5,y:4.5}}]);
 const banner=x.nodes('battle-banner')[0],ally=x.nodes('battle-ally')[0];assert.equal(banner.hidden,false);assert.match(ally.className,/is-hurt/);
 x.state.status='paused';x.renderer.draw(x.state);assert.equal(banner.hidden,false);assert.match(ally.className,/is-hurt/);
 x.state.status='running';x.state.tick=41;x.renderer.draw(x.state);assert.equal(banner.hidden,true);assert.doesNotMatch(ally.className,/is-hurt/);
 x.state.wave=2;x.renderer.draw(x.state);assert.equal(banner.hidden,false);assert.match(banner.textContent,/第 2 波/);
});
test('exhausted follow-up counts do not show an active badge before the duration expires',()=>{
 const x=setup();x.state.units=[x.unit()];const effect={type:'followup',procs:4,maxProcs:5,until:100};x.state.units[0].statuses=[effect];x.renderer.draw(x.state);
 assert.equal(x.nodes('battle-status-icon').filter(n=>!n.hidden).length,1);effect.procs=5;x.renderer.draw(x.state);
 assert.equal(x.nodes('battle-status-icon').filter(n=>!n.hidden).length,0);
});

test('canvas backing pixels cap at DPR 2 and static grass only redraws when its size changes',()=>{
 for(const width of [280,342,382]){
  const x=setup(width,4);x.renderer.draw(x.state);const canvases=x.renderer.board.all(n=>n.tag==='canvas');
  assert.equal(canvases[0].width,width*2);assert.equal(canvases[0].height,Math.round(width*7/5*2));
  const count=x.contexts[0].calls.length;x.state.tick++;x.renderer.draw(x.state);assert.equal(x.contexts[0].calls.length,count);
  x.resize(width-20);x.renderer.draw(x.state);assert.equal(canvases[0].width,(width-20)*2);assert.ok(x.contexts[0].calls.length>count);
 }
});
test('paused resize redraws static presentation immediately without advancing simulation',()=>{const x=setup(300);x.state.status='paused';x.state.units=[x.unit()];x.renderer.draw(x.state);const before=JSON.stringify(x.state);const canvas=x.renderer.board.all(n=>n.tag==='canvas')[0];x.resize(250);assert.equal(canvas.width,500);assert.equal(JSON.stringify(x.state),before);});

test('dense effect bursts obey 48 visual and 12 floating-text caps while leaving logical HP untouched',()=>{
 const x=setup();x.state.units=[x.unit()];x.renderer.draw(x.state);const fx=x.contexts[1];fx.calls.length=0;
 const events=Array.from({length:100},(_,i)=>({id:i+1,type:'damage',entityId:10,targetId:1,value:5,position:{x:2.5,y:4.5},tick:0}));
 const before=JSON.stringify(x.state);x.renderer.draw(x.state,events);
 assert.ok(fx.calls.filter(c=>c[0]==='stroke').length<=48);assert.equal(fx.calls.filter(c=>c[0]==='fillText').length,1);
 assert.equal(fx.calls.find(c=>c[0]==='fillText')[1],'−500');
 assert.equal(JSON.stringify(x.state),before);
 fx.calls.length=0;x.state.tick=30;x.renderer.draw(x.state,events);assert.equal(fx.calls.filter(c=>c[0]==='fillText').length,0);
});

test('selection updates interactive hints without mutating the battle or hiding keyboard grid targets',()=>{
 const x=setup();x.renderer.draw(x.state);const before=JSON.stringify(x.state);
 x.renderer.setSelection({characterId:'c0'});assert.equal(x.renderer.roster.children[0].getAttribute('aria-pressed'),'true');
 x.renderer.setSelection(null);assert.equal(x.renderer.roster.children[0].getAttribute('aria-pressed'),'false');
 assert.equal(JSON.stringify(x.state),before);assert.equal(x.renderer.board.all(n=>n.tag==='button'&&n.disabled).length,0);
});

test('fire warnings mark the full one-cell damage radius and preview retains separate invalid landing hints',()=>{
 const x=setup(300);x.renderer.draw(x.state);const fx=x.contexts[1];fx.calls.length=0;
 x.renderer.draw(x.state,[{id:1,type:'warning',value:'fire',tick:0,position:{x:2.5,y:4.5}}]);
 const arc=fx.calls.find(c=>c[0]==='arc');assert.equal(arc[3],60,'one world cell is the actual fire damage radius');
 x.renderer.setSelection({characterId:'c0',cell:{col:2,row:4},valid:false});
 const target=x.renderer.board.all(n=>n.dataset.col==='2'&&n.dataset.row==='4')[0];
 assert.match(target.className,/is-drop-invalid/);assert.doesNotMatch(target.className,/is-drop-valid/);
 x.renderer.setSelection(null);assert.doesNotMatch(target.className,/is-drop-invalid/);
});

test('broken native action falls back only to the same character and late image errors after destroy stay inert',()=>{
 const x=setup();x.state.units=[x.unit()];x.renderer.draw(x.state);const image=x.nodes('battle-sprite')[0];
 image.fire('error');assert.equal(image.src,'media/poster0.webp');
 x.renderer.draw(x.state);assert.equal(image.src,'media/poster0.webp');
 x.renderer.destroy();x.renderer.destroy();const writes=image.srcWrites;image.fire('error');
 assert.equal(image.srcWrites,writes);assert.equal(x.host.children.length,0);assert.equal(x.observers[0].stopped,true);
 x.renderer.draw(x.state);assert.equal(x.host.children.length,0);
});
test('failed native action and poster fall back to same-character avatar and explicit retry reloads native action',()=>{
 const x=setup();x.state.units=[x.unit()];x.renderer.draw(x.state);const image=x.nodes('battle-sprite')[0];
 image.fire('error');image.fire('error');assert.equal(image.src,'media/avatar0.webp');assert.equal(image.hidden,false);
 x.renderer.retry();assert.equal(image.src,'media/idle0.webp?retry=1');assert.equal(image.hidden,false);
});
test('independent gauges reflect each skill duration while deployed cards remain selectable at zero public energy',()=>{
 const x=setup();x.content.characters.c1.skill.cooldown=30;x.state.units=[{...x.unit(),readyAtTick:400},{...x.unit(2,'c1'),readyAtTick:600}];x.state.energy=0;x.state.tick=100;x.renderer.draw(x.state);
 const cards=x.renderer.roster.children;assert.equal(cards[0].disabled,false);assert.equal(cards[0].dataset.gesture,undefined);assert.equal(cards[0].dataset.battleUnitId,'1');assert.equal(cards[2].disabled,true);
 const bars=x.nodes('battle-card-charge');assert.equal(bars[0].getAttribute('aria-valuenow'),'25');assert.equal(bars[1].getAttribute('aria-valuenow'),'17');
 assert.match(x.renderer.energyDisplay.textContent,/部署 \/ 回收/);assert.doesNotMatch(x.renderer.energyDisplay.getAttribute('aria-label'),/点击/);
});
test('selected ready unit casts without energy; recall charges separately and stale selection cannot issue commands',()=>{
 const calls=[],x=setup(320,2,{onCast:id=>calls.push(['cast',id]),onRecall:id=>calls.push(['recall',id])});x.state.units=[x.unit()];x.state.tick=20;x.state.energy=0;x.renderer.draw(x.state);x.renderer.setSelection({unitId:1});
 assert.equal(x.renderer.actions.hidden,false);assert.equal(x.renderer.castButton.disabled,false);assert.equal(x.renderer.recallButton.disabled,true);assert.match(x.renderer.actions.textContent,/技能0/);
 x.renderer.castButton.fire('click');x.renderer.recallButton.fire('click');assert.deepEqual(calls,[['cast',1]]);
 x.state.energy=10;x.renderer.draw(x.state);assert.equal(x.renderer.recallButton.disabled,false);x.renderer.recallButton.fire('click');assert.deepEqual(calls,[['cast',1],['recall',1]]);
 x.state.units=[];x.renderer.draw(x.state);assert.equal(x.renderer.actions.hidden,true);x.renderer.castButton.fire('click');assert.equal(calls.length,2);
});
test('unit operation panel waits for that unit full gauge, disables in pause and resumes without replacing controls',()=>{
 const x=setup();x.state.units=[{...x.unit(),readyAtTick:400}];x.state.tick=100;x.renderer.draw(x.state);x.renderer.setSelection({unitId:1});const panel=x.renderer.actions;
 assert.equal(x.renderer.castButton.disabled,true);assert.match(panel.textContent,/充能 25% · 15 秒/);
 x.state.tick=400;x.state.status='paused';x.renderer.draw(x.state);assert.equal(x.renderer.castButton.disabled,true);assert.equal(x.renderer.recallButton.disabled,true);
 x.state.status='running';x.renderer.draw(x.state);assert.equal(x.renderer.castButton.disabled,false);assert.equal(x.renderer.actions,panel);
});
test('recalled unit roster preserves visible health and frozen charge while allowing paid redeployment',()=>{
 const x=setup();x.state.reserves={c0:{hp:37,remainingTicks:200}};x.renderer.draw(x.state);const card=x.renderer.roster.children[0];
 assert.equal(card.dataset.gesture,'deploy');assert.equal(card.disabled,false);assert.match(card.textContent,/20 部署 · 生命37/);assert.match(card.getAttribute('title'),/充能剩余 10 秒/);
 assert.equal(x.nodes('battle-card-charge')[0].getAttribute('aria-valuenow'),'50');x.state.tick=200;x.renderer.draw(x.state);assert.equal(x.nodes('battle-card-charge')[0].getAttribute('aria-valuenow'),'50');
 x.state.energy=19;x.renderer.draw(x.state);assert.equal(card.disabled,true);
});
test('long personal gauge stays below 100 percent until the exact ready tick',()=>{
 const x=setup();x.content.characters.c0.skill.cooldown=75;x.state.units=[{...x.unit(),readyAtTick:1500}];x.state.tick=1493;x.renderer.draw(x.state);x.renderer.setSelection({unitId:1});
 assert.equal(x.nodes('battle-card-charge')[0].getAttribute('aria-valuenow'),'99');assert.match(x.renderer.actions.textContent,/充能 99%/);assert.equal(x.renderer.castButton.disabled,true);
 x.state.tick=1500;x.renderer.draw(x.state);assert.equal(x.nodes('battle-card-charge')[0].getAttribute('aria-valuenow'),'100');assert.equal(x.renderer.castButton.disabled,false);
});
