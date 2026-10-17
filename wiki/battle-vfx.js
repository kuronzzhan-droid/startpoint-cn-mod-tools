/* Tick-driven presentation only. Native character animations remain DOM sprites. */
((root)=>{
 'use strict';
 const PALETTES={fire:['#ffab60','#fff1b8'],water:['#69d8ff','#d7f7ff'],thunder:['#ffe574','#fffbc8'],
  wind:['#abed88','#ecffd2'],light:['#ffeaae','#fffef0'],dark:['#c99aff','#f1d9ff']};
 const LIFE={attack:12,damage:10,heal:16,buff:18,deploy:16,recall:14,death:18,ready:20,cast:18,warning:16};
 const PRIORITY={warning:3,ready:2,cast:2,deploy:2,recall:2,death:2};
 const clamp=(value,low,high)=>Math.max(low,Math.min(high,value));
 const point=value=>value&&Number.isFinite(value.x)&&Number.isFinite(value.y)&&Math.abs(value.x)<20&&Math.abs(value.y)<20?{x:value.x,y:value.y}:null;
 const entity=(state,id)=>(state.units||[]).find(unit=>unit.id===id)||(state.enemies||[]).find(unit=>unit.id===id);
 const tick=state=>Number.isFinite(state.tick)?state.tick:0;
 const amount=value=>value>0&&value<.1?'<0.1':value<1?Number(value.toFixed(1)):Math.round(value);
 function create({content,reducedMotion=false}){
  let visuals=[],texts=[],lastEventId=0;
  function prune(state){
   const now=tick(state);
   visuals=visuals.filter(v=>v.end>now&&!(v.type==='warning'&&v.sourceKnown&&!(entity(state,v.entityId)?.hp>0)));
   texts=texts.filter(v=>v.end>now);
  }
  function admit(visual){
   visuals.push(visual);
   if(visuals.length<=48)return;
   let index=0;for(let i=1;i<visuals.length;i++)if((PRIORITY[visuals[i].type]||1)<(PRIORITY[visuals[index].type]||1))index=i;
   visuals.splice(index,1);
  }
  function textFor(type,value,shield){
   return type==='heal'?(value>0?'+'+amount(value):''):value>0?'−'+amount(value)+(shield>0?' · 盾'+amount(shield):''):shield>0?'护盾 '+amount(shield):'';
  }
  function addText(event,visual){
   const {type,position,start,absorbed}=visual,value=event.value;
   if(!['damage','heal'].includes(type)||!Number.isFinite(value)||value<0||!textFor(type,value,absorbed))return;
   const target=Number.isSafeInteger(event.targetId)?'id'+event.targetId:`xy${position.x},${position.y}`,key=`${type}:${target}:${start}`;
   const found=texts.find(text=>text.key===key);
   if(found){found.value+=value;found.absorbed+=absorbed;return;}
   texts.push({key,type,position:{...position},value,absorbed,start,end:start+22});
   if(texts.length>12)texts.shift();
  }
  function ingest(state,events=[]){
   prune(state);const floor=lastEventId,seen=new Set(),now=tick(state);
   for(const event of events){
    if(!Number.isSafeInteger(event.id)||event.id<=floor||seen.has(event.id))continue;
    seen.add(event.id);lastEventId=Math.max(lastEventId,event.id);
    const type=event.type==='kill'?'death':event.type==='returned'?'ready':event.type;
    if(!LIFE[type])continue;
    const source=entity(state,event.entityId),target=entity(state,event.targetId),start=Number.isFinite(event.tick)?Math.min(now,event.tick):now;
    const position=point(event.position)||point(['damage','heal','buff','warning'].includes(type)?target||source:source);
    if(!position||start+LIFE[type]<=now)continue;
    const origin=point(event.sourcePosition)||point(source),characterId=event.characterId||source?.characterId;
    const definition=content?.characters?.[characterId],colors=PALETTES[definition?.element]||PALETTES.light;
    const visual={id:event.id,type,entityId:event.entityId,sourceKnown:!!source,position,origin,colors,
     role:definition?.role,value:typeof event.value==='string'||Number.isFinite(event.value)?event.value:null,
     absorbed:Number.isFinite(event.absorbed)?Math.max(0,event.absorbed):0,start,end:start+LIFE[type]};
    admit(visual);
    addText(event,visual);
   }
  }
  function pixel(ctx,x,y,size,color){ctx.fillStyle=color;ctx.fillRect(Math.round(x/2)*2,Math.round(y/2)*2,size,size);}
  function ring(ctx,x,y,radius,color,line=2){ctx.strokeStyle=color;ctx.lineWidth=line;ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);ctx.stroke();}
  function plus(ctx,x,y,size,color){
   ctx.fillStyle=color;ctx.fillRect(Math.round(x-size/2),Math.round(y-size/6),size,size/3);
   ctx.fillRect(Math.round(x-size/6),Math.round(y-size/2),size/3,size);
  }
  function sparks(ctx,visual,x,y,cell,progress,count=6,color=visual.colors[0]){
   const number=reducedMotion?1:count,spread=cell*(.07+progress*.32),rotation=(visual.id%7)*.23;
   for(let i=0;i<number;i++){
    const angle=i*Math.PI*2/number+rotation,offset=reducedMotion?cell*.1:spread;
    pixel(ctx,x+Math.cos(angle)*offset,y+Math.sin(angle)*offset,Math.max(2,cell*.045*(1-progress*.4)),color);
   }
  }
  function shield(ctx,x,y,size,color){
   ctx.strokeStyle=color;ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(x-size,y-size);
   ctx.lineTo(x+size,y-size);ctx.lineTo(x+size,y+size*.3);ctx.lineTo(x,y+size);ctx.lineTo(x-size,y+size*.3);ctx.closePath();ctx.stroke();
  }
  function slash(ctx,visual,x,y,cell,progress){
   ctx.strokeStyle=visual.colors[1];ctx.lineWidth=Math.max(2,cell*.055*(1-progress*.6));ctx.beginPath();
   const radius=cell*(reducedMotion?.22:.15+.18*progress);
   ctx.moveTo(x-radius,y+radius*.65);ctx.lineTo(x,y-cell*.05);ctx.lineTo(x+radius,y-radius*.65);ctx.stroke();
   if(!reducedMotion)sparks(ctx,visual,x,y,cell,progress,3);
  }
  function projectile(ctx,visual,x,y,cell,progress){
   const from=visual.origin;if(!from){slash(ctx,visual,x,y,cell,progress);return;}
   const sx=from.x*cell,sy=from.y*cell,t=reducedMotion?1:Math.min(1,progress*1.8),px=sx+(x-sx)*t,py=sy+(y-sy)*t;
   if(!reducedMotion){ctx.strokeStyle=visual.colors[0];ctx.lineWidth=2;ctx.beginPath();
    const tail=Math.max(0,t-.22);ctx.moveTo(sx+(x-sx)*tail,sy+(y-sy)*tail);ctx.lineTo(px,py);ctx.stroke();}
   pixel(ctx,px-3,py-3,6,visual.colors[1]);
  }
  function warning(ctx,visual,x,y,cell,progress){
   const fire=visual.value==='fire',support=['water','light'].includes(visual.value),radius=cell*(fire?1:.42);
   const color=support?'#a6e4e2':'#ffad83';ctx.globalAlpha=1;
   ring(ctx,x,y,radius,color,fire?3:2);
   ctx.strokeStyle=support?'#d8ffea':'#fff0ce';ctx.lineWidth=2;ctx.beginPath();
   ctx.arc(x,y,radius+4,-Math.PI/2,-Math.PI/2+Math.PI*2*progress);ctx.stroke();
   if(fire){ctx.fillStyle='#ff765218';ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);ctx.fill();}
   else{pixel(ctx,x-2,y-9,4,color);pixel(ctx,x-2,y+1,4,color);}
  }
  function cue(ctx,visual,cell,now){
   const progress=clamp((now-visual.start)/(visual.end-visual.start),0,1),x=visual.position.x*cell,y=visual.position.y*cell;
   ctx.globalAlpha=reducedMotion?.85:Math.min(1,(1-progress)*1.5);const [color,light]=visual.colors;
   switch(visual.type){
    case 'warning':warning(ctx,visual,x,y,cell,progress);break;
    case 'attack':
     if(visual.role==='ranged'||visual.origin&&Math.hypot(visual.position.x-visual.origin.x,visual.position.y-visual.origin.y)>1.4)projectile(ctx,visual,x,y,cell,progress);
     else slash(ctx,visual,x,y,cell,progress);break;
    case 'damage':
     if(visual.absorbed>0)shield(ctx,x,y-cell*.13,cell*.2,'#aeeaff');
     if(visual.value>0)sparks(ctx,visual,x,y-cell*.08,cell,progress,6,light);break;
    case 'heal':
     plus(ctx,x,y-cell*(.14+(reducedMotion?0:progress*.25)),cell*.22,'#a6ffc6');
     if(!reducedMotion)sparks(ctx,visual,x,y,cell,progress,4,'#73eeb2');break;
    case 'buff':
     if(visual.value==='shield')shield(ctx,x,y-cell*.15,cell*.24,'#aeeaff');
     else{const up=y-cell*(.12+(reducedMotion?0:progress*.3));ctx.strokeStyle=visual.value==='slow'||visual.value==='healReduction'?'#d2b1fa':'#ffefab';ctx.lineWidth=3;ctx.beginPath();
      ctx.moveTo(x-cell*.13,up+cell*.08);ctx.lineTo(x,up-cell*.06);ctx.lineTo(x+cell*.13,up+cell*.08);ctx.stroke();}break;
    case 'deploy':
     ring(ctx,x,y,cell*(reducedMotion?.24:.12+progress*.35),color);sparks(ctx,visual,x,y,cell,progress,5);break;
    case 'recall':{
     const r=cell*(reducedMotion?.22:.38*(1-progress));ring(ctx,x,y,r,'#88dcff');
     if(!reducedMotion)for(let i=0;i<4;i++){const angle=i*Math.PI/2;pixel(ctx,x+Math.cos(angle)*r,y+Math.sin(angle)*r,4,'#dbf8ff');}break;}
    case 'death':sparks(ctx,visual,x,y-cell*.1,cell,progress,6,'#c3c9bd');break;
    case 'ready':
     plus(ctx,x,y-cell*(reducedMotion?.38:.3+progress*.15),cell*.18,'#fff4a2');
     ring(ctx,x,y,cell*.22,'#fff4a2');break;
    case 'cast':
     ring(ctx,x,y,cell*(reducedMotion?.3:.16+progress*.4),color,3);
     if(!reducedMotion)sparks(ctx,visual,x,y,cell,progress,6,light);break;
   }
  }
  function range(ctx,state,selection,cell){
   if(!selection)return;
   const unit=selection.unitId?(state.units||[]).find(u=>u.id===selection.unitId&&u.hp>0):null;
   const preview=selection.characterId&&selection.cell,valid=preview&&Number.isInteger(preview.col)&&Number.isInteger(preview.row)&&preview.col>=0&&preview.col<5&&preview.row>=0&&preview.row<7;
   const def=content?.characters?.[unit?.characterId||(valid?selection.characterId:null)],radius=def?.stats?.range;
   if(!Number.isFinite(radius)||radius<=0||radius>12)return;
   const x=unit?.x??preview.col+.5,y=unit?.y??preview.row+.5,color=selection.valid===false?'#ffb2a1':def.role==='healer'?'#a4efc4':'#e5f2c5';
   ctx.globalAlpha=.8;ctx.setLineDash([4,4]);ring(ctx,x*cell,y*cell,radius*cell,color);ctx.setLineDash([]);
   ctx.globalAlpha=.08;ctx.fillStyle=color;ctx.beginPath();ctx.arc(x*cell,y*cell,radius*cell,0,Math.PI*2);ctx.fill();
  }
  function draw(ctx,state,{width,height,dpr=1,selection}={}){
   prune(state);if(!ctx||!Number.isFinite(width)||!Number.isFinite(height)||width<=0||height<=0)return;
   const scale=clamp(Number.isFinite(dpr)?dpr:1,1,2),cell=width/5,now=tick(state);
   ctx.save();ctx.setTransform(scale,0,0,scale,0,0);ctx.clearRect(0,0,width,height);ctx.imageSmoothingEnabled=false;
   range(ctx,state,selection,cell);for(const visual of visuals)if(visual.type!=='warning')cue(ctx,visual,cell,now);
   for(const visual of visuals)if(visual.type==='warning')cue(ctx,visual,cell,now);
   ctx.textAlign='center';ctx.textBaseline='middle';ctx.font=`bold ${clamp(Math.round(cell*.22),11,15)}px sans-serif`;
   for(const text of texts){
    const age=now-text.start;ctx.globalAlpha=reducedMotion?1:Math.min(1,(text.end-now)/6);
    const label=textFor(text.type,text.value,text.absorbed);ctx.fillStyle=text.type==='heal'?'#baffd0':text.value===0?'#bcefff':'#fff6e8';
    const x=text.position.x*cell,y=text.position.y*cell-cell*.36-(reducedMotion?0:age*.65);
    ctx.strokeStyle='#153124';ctx.lineWidth=3;ctx.strokeText(label,x,y);ctx.fillText(label,x,y);
   }
   ctx.restore();
  }
  function clear(){visuals=[];texts=[];lastEventId=0;}
  function setReducedMotion(value){reducedMotion=!!value;}
  return {ingest,draw,clear,setReducedMotion,stats:()=>({visuals:visuals.length,texts:texts.length,lastEventId})};
 }
 const api={create};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WFBattleVfx=api;
})(typeof window==='undefined'?globalThis:window);
