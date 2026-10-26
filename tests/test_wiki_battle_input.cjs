const test=require('node:test'),assert=require('node:assert/strict'),I=require('../wiki/battle-input.js');
test('grid hit test rejects outside edges and includes scaled phone cells',()=>{const r={left:10,top:20,width:300,height:420};assert.deepEqual(I.cellAt(10,20,r),{col:0,row:0});assert.deepEqual(I.cellAt(309,439,r),{col:4,row:6});for(const [x,y]of [[310,20],[10,440],[9,20],[10,19]])assert.equal(I.cellAt(x,y,r),null);});
test('input deduplicates synthesized click after touch drop and cancels a second pointer',()=>{
 const listeners=new Map(),win=new EventTarget();const source={dataset:{gesture:'deploy',characterId:'a'},disabled:false,setPointerCapture(){},releasePointerCapture(){},closest:()=>source};
 const host={contains:()=>true,addEventListener:(n,f)=>listeners.set(n,f),removeEventListener:n=>listeners.delete(n)};
 let deployments=0,voices=0,selects=0;const doc={createElement:()=>({style:{},remove(){}}),body:{append(){}}};
 const input=I.create({host,board:{getBoundingClientRect:()=>({left:0,top:0,width:500,height:700})},window:win,document:doc,canSelect:()=>true,onVoice:()=>voices++,onSelect:()=>selects++,onDrop:()=>deployments++,onCell:()=>{}});
 const ev=(id,x,y)=>({target:source,pointerId:id,button:0,clientX:x,clientY:y,preventDefault(){}});
 listeners.get('pointerdown')(ev(1,5,5));listeners.get('pointermove')(ev(1,50,50));listeners.get('pointerup')(ev(1,50,50));listeners.get('click')({target:source,detail:1});assert.equal(deployments,1);assert.equal(voices,1);assert.equal(selects,0);
 listeners.get('pointerdown')(ev(2,5,5));listeners.get('pointerdown')(ev(3,6,6));listeners.get('pointerup')(ev(2,50,50));assert.equal(deployments,1);input.destroy();assert.equal(listeners.size,0);
});
test('escape cancels an in-progress drag so releasing it cannot deploy',()=>{
 const callbacks=new Map(),win=new EventTarget(),source={dataset:{gesture:'deploy',characterId:'a'},closest:()=>source},host={contains:()=>true,addEventListener:(k,f)=>callbacks.set(k,f),removeEventListener:k=>callbacks.delete(k)};
 let drops=0;const doc={createElement:()=>({style:{},remove(){}}),body:{append(){}}};
 const input=I.create({host,board:{getBoundingClientRect:()=>({left:0,top:0,width:500,height:700})},canSelect:()=>true,onVoice(){},onSelect(){},onDrop(){drops++;},onCell(){},window:win,document:doc});
 const ev={target:source,pointerId:1,button:0,clientX:10,clientY:10,preventDefault(){}};callbacks.get('pointerdown')(ev);callbacks.get('pointermove')({...ev,clientX:50});
 const escape=new Event('keydown');escape.key='Escape';win.dispatchEvent(escape);callbacks.get('pointerup')({...ev,clientX:50});assert.equal(drops,0);input.destroy();
});
test('deployed portrait selects its unit without deployment voice, drag or public energy gesture',()=>{
 const callbacks=new Map(),win=new EventTarget(),card={dataset:{battleUnitId:'7'},disabled:false,closest:selector=>selector==='[data-battle-unit-id]'?card:null};
 const host={contains:()=>true,addEventListener:(k,f)=>callbacks.set(k,f),removeEventListener:k=>callbacks.delete(k)};let voices=0,drops=0;const selected=[];
 const input=I.create({host,board:{getBoundingClientRect:()=>({left:0,top:0,width:500,height:700})},window:win,canSelect:()=>true,onVoice:()=>voices++,onSelect(){},onDrop:()=>drops++,onCell(){},onUnit:id=>selected.push(id)});
 const ev={target:card,pointerId:1,button:0,clientX:10,clientY:10,preventDefault(){}};callbacks.get('pointerdown')(ev);callbacks.get('pointermove')({...ev,clientX:100});callbacks.get('pointerup')({...ev,clientX:100});callbacks.get('click')({...ev,detail:1});
 assert.deepEqual(selected,[7]);assert.equal(voices,0);assert.equal(drops,0);card.disabled=true;callbacks.get('click')({...ev,detail:0});assert.deepEqual(selected,[7]);input.destroy();
});
test('a successful drop changing the portrait into a deployed card does not select it again via synthesized click',()=>{
 const callbacks=new Map(),win=new EventTarget(),source={dataset:{gesture:'deploy',characterId:'a'},closest(selector){return selector==='[data-gesture]'&&this.dataset.gesture||selector==='[data-battle-unit-id]'&&this.dataset.battleUnitId?this:null;}};
 const host={contains:()=>true,addEventListener:(k,f)=>callbacks.set(k,f),removeEventListener:k=>callbacks.delete(k)};let selections=0;const doc={createElement:()=>({style:{},remove(){}}),body:{append(){}}};
 const input=I.create({host,board:{getBoundingClientRect:()=>({left:0,top:0,width:500,height:700})},window:win,document:doc,canSelect:()=>true,onVoice(){},onSelect(){},onDrop(){delete source.dataset.gesture;source.dataset.battleUnitId='1';},onCell(){},onUnit:()=>selections++});
 const ev={target:source,pointerId:1,button:0,clientX:10,clientY:10,preventDefault(){}};callbacks.get('pointerdown')(ev);callbacks.get('pointermove')({...ev,clientX:50});callbacks.get('pointerup')({...ev,clientX:50});callbacks.get('click')({...ev,detail:1});assert.equal(selections,0);
 callbacks.get('pointerdown')(ev);callbacks.get('pointerup')(ev);callbacks.get('click')({...ev,detail:1});assert.equal(selections,1);input.destroy();
});
