const test=require('node:test'),assert=require('node:assert/strict'),P=require('../wiki/battle-page.js');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),{Node}=require('./wiki_equipment_fixture.cjs');
test('leave protection follows mounted session even after hash changes; cancel restores previous state',async()=>{
 const state={status:'running'},events=[];let answer=false,connected=true;
 const guard=P.makeGuard({getState:()=>state,isConnected:()=>connected,pause:()=>{events.push('pause');state.status='paused';},resume:()=>{events.push('resume');state.status='running';},ask:async()=>answer});
 assert.equal(guard.isActive(),true);assert.equal(await guard.canLeave(),false);assert.deepEqual(events,['pause','resume']);
 state.status='paused';assert.equal(await guard.canLeave(),false);assert.equal(state.status,'paused');
 answer=true;assert.equal(await guard.canLeave(),true);assert.equal(state.status,'paused');connected=false;assert.equal(guard.isActive(),false);
});
test('finished or preparation views never ask to abandon combat',()=>{let state=null;const guard=P.makeGuard({getState:()=>state,isConnected:()=>true});assert.equal(guard.needsProtection(),false);state={status:'won'};assert.equal(guard.needsProtection(),false);state={status:'running'};assert.equal(guard.needsProtection(),true);});

test('unit selection keeps battle running and dispatches direct free cast or separately paid recall without energy selection',()=>{
 const window=new Node('window'),document=new Node('document'),host=new Node('main');document.body=new Node('body');document.append(document.body);document.body.append(host);document.hidden=false;
 const characters=Object.fromEntries(Array.from({length:6},(_,i)=>['c'+i,{id:'c'+i,name:'角色'+i,stats:{hp:100,range:2,deployCost:20},skill:{name:'技能'+i,gauge:600,cooldown:30}}]));
 const content={characters,stages:[{id:'fire'}],media:Object.fromEntries(Object.keys(characters).map(id=>[id,{}])),recallCost:10};const options={squad:Object.keys(characters),mode:'campaign',stageId:'fire'};
 let selection,input,view,state,pauses=0,unregistered=0;const commands=[],settings={muted:false,volume:.65};
 Object.assign(window,{WF_BATTLE_CONTENT:content,WFCommunityAdminConfirm:{ask:async()=>true},WFNavigationGuard:{register:()=>()=>unregistered++},
  WFBattleStorage:{create:()=>({read:()=>({value:{settings}}),destroy(){}})},WFBattleSelection:{roles:{},mount:args=>{selection=args;return {destroy(){}};}},
  WFBattleModel:{create:()=>state={...options,status:'running',tick:0,lastCommandId:0,energy:0,units:[],enemies:[],coffins:[]},setPaused(s,v){pauses++;s.status=v?'paused':'running';},
   dispatch(s,action){commands.push(action);s.lastCommandId=action.id;return {ok:true,events:[]};}},
  WFBattleMedia:{create:()=>({unlock(){},preload(){},handle(){},setMuted(){},setVolume(){},destroy(){}})},
  WFBattleClock:{create:()=>({start(){},pause(){},destroy(){}})},WFBattleInput:{create:args=>{input=args;return {destroy(){}};}},
  WFBattleRender:{create:args=>{view=args;return {draw(){},setSelection(){},destroy(){},board:new Node('div')};}}
 });
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki/battle-page.js'),'utf8'),{window,document});const page=window.WFBattlePage.render(host,null,{el:(...args)=>new Node(...args)});selection.onStart(options);
 state.units.push({id:1,characterId:'c0',hp:100,col:2,row:4,readyAtTick:0});input.onUnit(1);assert.equal(state.status,'running');assert.equal(pauses,0);
 view.onCast(1);assert.equal(commands[0].type,'cast');assert.equal(commands[0].unitId,1);assert.equal(state.energy,0);assert.equal(pauses,0);
 input.onCell({col:2,row:4});view.onRecall(1);assert.equal(commands[1].type,'recall');assert.equal(commands[1].unitId,1);assert.equal(pauses,0);
 state.status='paused';view.onCast(1);assert.equal(commands.length,2);page.destroy();assert.equal(unregistered,1);
});

test('character details describe only supported refund ratio and optional trigger cooldown or per-battle limit',()=>{
 const window=new Node('window'),document=new Node('document'),host=new Node('main');document.body=new Node('body');document.append(document.body);document.body.append(host);
 const character={id:'c0',name:'角色',role:'melee',stats:{hp:100,range:2,deployCost:20},skill:{name:'技能',description:'角色招牌技能',gauge:600,cooldown:30}};
 const content={characters:{c0:character},stages:[{id:'fire'}],media:{c0:{}}};let selection;
 Object.assign(window,{WF_BATTLE_CONTENT:content,WFNavigationGuard:{register:()=>()=>{}},WFBattleStorage:{create:()=>({read:()=>({value:{settings:{muted:false,volume:.65}}}),destroy(){}})},
  WFBattleSelection:{roles:{melee:'近战'},mount:args=>{selection=args;return {destroy(){}};}}});
 const el=(...args)=>Object.assign(new Node(...args),{showModal(){this.open=true;},close(){this.open=false;}});
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki/battle-page.js'),'utf8'),{window,document});const page=window.WFBattlePage.render(host,null,{el});
 const details=()=>{selection.onInspect(character);const dialogs=document.all(n=>n.tag==='dialog');assert.equal(dialogs.length,1);assert.equal(dialogs[0].open,true);return dialogs[0].textContent;};
 assert.doesNotMatch(details(),/施技后回槽|回槽触发冷却|每局最多触发/);
 character.skill.refund={ratio:.2,ct:0};const unlimited=details();assert.match(unlimited,/施技后回槽 20%/);assert.doesNotMatch(unlimited,/回槽触发冷却|每局最多触发/);
 character.skill.refund={ratio:.3,ct:15,limit:3};const limited=details();assert.match(limited,/施技后回槽 30% · 回槽触发冷却 15 秒 · 每局最多触发 3 次/);
 page.destroy();assert.equal(document.all(n=>n.tag==='dialog').length,0);
});

test('battle notices summarize state changes without repeat tick or drag announcements, keeping media events intact',()=>{
 const window=new Node('window'),document=new Node('document'),host=new Node('main');document.body=new Node('body');document.append(document.body);document.body.append(host);
 const characters={a:{name:'甲'},b:{name:'乙'}},content={characters,stages:[{id:'fire'}],media:{a:{},b:{}}};let selection,input,clock,state,events=[];const delivered=[];
 Object.assign(window,{WF_BATTLE_CONTENT:content,WFNavigationGuard:{register:()=>()=>{}},WFBattleStorage:{create:()=>({read:()=>({value:{settings:{muted:false,volume:.65}}}),destroy(){}})},
  WFBattleSelection:{mount:args=>{selection=args;return{destroy(){}};}},WFBattleModel:{create:()=>state={tick:0,status:'running',squad:['a','b'],units:[],enemies:[],coffins:[]},canDeploy:()=>'',advance:s=>{s.tick++;return events;}},
  WFBattleMedia:{create:()=>({unlock(){},preload(){},setMuted(){},setVolume(){},handle:batch=>delivered.push(batch),destroy(){}})},
  WFBattleRender:{create:()=>({draw(){},setSelection(){},destroy(){}})},WFBattleInput:{create:args=>{input=args;return{destroy(){}};}},WFBattleClock:{create:args=>{clock=args;return{start(){},destroy(){}};}}
 });
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki/battle-page.js'),'utf8'),{window,document});const page=window.WFBattlePage.render(host,null,{el:(...args)=>new Node(...args)});selection.onStart({squad:['a','b']});
 const notice=host.all(n=>n.className==='battle-notice')[0],descriptor=Object.getOwnPropertyDescriptor(Node.prototype,'textContent');let writes=0;
 Object.defineProperty(notice,'textContent',{get:()=>descriptor.get.call(notice),set:value=>{writes++;descriptor.set.call(notice,value);}});
 input.onPreview({characterId:'a'},{col:0,row:0});input.onPreview({characterId:'a'},{col:0,row:1});assert.equal(writes,1);assert.equal(notice.attributes['aria-live'],'off');
 state.tick=100;events=[{type:'ready',characterId:'a'},{type:'ready',characterId:'b'}];clock.step();assert.match(notice.textContent,/甲、乙技能就绪/);assert.equal(notice.attributes['aria-live'],'polite');assert.equal(writes,2);assert.equal(delivered.at(-1),events);
 clock.step();assert.equal(writes,2);events=[{type:'damage',characterId:'a'}];clock.step();assert.equal(writes,2);
 events=[{type:'death',characterId:'a'}];clock.step();assert.match(notice.textContent,/甲倒下.*20秒/);assert.equal(writes,3);assert.equal(delivered.at(-1),events);
 state.tick+=80;events=[{type:'returned',characterId:'a'}];clock.step();assert.match(notice.textContent,/甲已复归/);assert.equal(writes,4);page.destroy();
});
