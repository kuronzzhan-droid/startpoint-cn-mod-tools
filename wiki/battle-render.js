/* Presentation only: simulation owns time, health, cooldowns and all commands. */
((root)=>{
 'use strict';
 const Vfx=typeof module!=='undefined'&&module.exports?require('./battle-vfx.js'):root.WFBattleVfx;
 function create({host,content,ui,onFailure=()=>{},onCast=()=>{},onRecall=()=>{},onInspect=()=>{}}){
  const {el}=ui,field=el('section','battle-field'),status=el('div','battle-status'),board=el('div','battle-board');
  const ground=el('canvas','battle-ground'),fx=el('canvas','battle-fx'),grid=el('div','battle-grid'),layer=el('div','battle-sprites');
  const roster=el('div','battle-roster'),energyDisplay=el('div','battle-energy'),energyValue=el('strong'),energyLabel=el('span','','部署 / 回收');
  const actions=el('section','battle-unit-actions'),actionTitle=el('strong'),actionHint=el('span','battle-action-hint'),actionCharge=el('span','battle-action-charge'),actionBar=el('i');
  const castButton=el('button','primary-button','发动技能'),recallButton=el('button','secondary-button','回收'),inspectButton=el('button','secondary-button','详情');
  actions.hidden=true;actions.setAttribute('aria-label','选中角色操作');actionCharge.append(actionBar);actions.append(actionTitle,actionHint,actionCharge,castButton,recallButton,inspectButton);
  for(const [node,callback]of [[castButton,onCast],[recallButton,onRecall],[inspectButton,onInspect]]){node.type='button';node.addEventListener('click',()=>{const unit=lastState?.units.find(u=>u.id===selection?.unitId&&u.hp>0);if(unit&&!node.disabled)callback(unit.id);});}
  const entry=el('span','battle-entry'),base=el('span','battle-base'),wave=el('span','battle-wave');
  const bossHud=el('div','battle-boss-hud'),bossName=el('span','battle-boss-name'),bossTrack=el('span','battle-boss-track'),bossBar=el('i'),bossValue=el('span','battle-boss-value');
  const banner=el('div','battle-banner');banner.hidden=true;banner.setAttribute('role','status');bossHud.hidden=true;
  bossTrack.append(bossBar);bossTrack.setAttribute('role','progressbar');bossHud.append(bossName,bossTrack,bossValue);
  status.append(wave,base,entry);status.setAttribute('aria-label','战场状态');board.setAttribute('aria-label','五列七行草地战场');
  board.dataset.navigationSwipeIgnore='';energyDisplay.setAttribute('role','status');
  energyDisplay.append(energyLabel,energyValue);board.append(ground,fx,grid,layer,bossHud,banner);field.append(status,board,actions,roster,energyDisplay);host.append(field);
  ground.setAttribute('aria-hidden','true');fx.setAttribute('aria-hidden','true');layer.setAttribute('aria-hidden','true');
  const groundCtx=ground.getContext('2d'),fxCtx=fx.getContext('2d'),cells=[],cards=new Map(),entities=new Map(),coffins=new Map(),castUntil=new Map();
  let dead=false,selection=null,width=0,height=0,dpr=0,pendingWidth=board.clientWidth||280,lastEventId=0,lastState=null;
  const motion=root.matchMedia?.('(prefers-reduced-motion: reduce)'),flashes=new Map();
  const visual=Vfx.create({content,reducedMotion:!!motion?.matches});let bannerUntil=0,shownWave=0;
  const setText=(node,text)=>{text=String(text);if(node.textContent!==text)node.textContent=text;};
  const attr=(node,key,value)=>{value=String(value);if(node.getAttribute(key)!==value)node.setAttribute(key,value);};
  const name=id=>content.characters[id]?.name||'角色',alive=unit=>unit.hp>0;
  const charge=(id,remaining)=>remaining<=0?100:Math.max(0,Math.min(99,Math.round((1-remaining/(content.characters[id].skill.cooldown*20))*100)));
  const remaining=unit=>Math.max(0,unit.readyAtTick-lastState.tick);
  const safeImage=def=>def&&typeof def.url==='string'&&/^media\/[a-zA-Z0-9_./-]+\.(webp|png|jpg)$/.test(def.url)&&!def.url.includes('..')&&Number.isFinite(def.width)&&def.width>0&&Number.isFinite(def.height)&&def.height>0;
  function imageState(img){
   const record={img,failed:new Set(),options:[],current:null,scale:1};
   record.onError=()=>{if(dead)return;if(record.current)record.failed.add(record.current.url);paintImage(record);onFailure('像素资源加载失败，已尝试同角色替代图，可重试资源。');};img.addEventListener('error',record.onError);
   return record;
  }
  function paintImage(record){
   const def=record.options.find(value=>safeImage(value)&&!record.failed.has(value.url));record.current=def||null;
   record.img.hidden=!def;if(!def)return;
   if(record.url!==def.url){record.url=def.url;record.img.src=def.url+(record.retry?`?retry=${record.retry}`:'');}
   const scale=def.avatar?width/5*.65/32:record.scale;record.img.style.width=`${def.width*scale}px`;record.img.style.height=`${def.height*scale}px`;
   record.img.style.left=`${-(def.anchorX??def.width/2)*scale}px`;record.img.style.top=`${-(def.anchorY??def.height)*scale}px`;
  }
  function scaleFor(media,kind){
   // Measure the idle body once; a large skill-effect canvas must not shrink its actor.
   const body=media?.actions?.idle;if(!safeImage(body))return 1;
   const factor=kind==='boss'?1.32:kind==='vanguard'?.76:1,cell=width/5;
   return Math.min(3,cell*.82*factor/body.width,cell*1.05*factor/body.height);
  }
  function createEntity(unit,enemy){
   const node=el('div',`battle-entity ${enemy?'battle-enemy battle-'+unit.rank:'battle-ally'}`),img=el('img','battle-sprite');
   const health=el('span','battle-health'),bar=el('i'),label=el('span','battle-unit-label'),ready=el('span','battle-ready'),gauge=el('span','battle-charge'),gaugeBar=el('i');
   const statusIcons=el('span','battle-status-icons'),icons=Array.from({length:3},()=>el('span','battle-status-icon'));statusIcons.append(...icons);
   img.alt='';img.draggable=false;health.setAttribute('role','progressbar');health.setAttribute('aria-label',`${name(unit.characterId)}生命`);
   health.append(bar);gauge.append(gaugeBar);gauge.hidden=enemy;node.append(ready,img,health,gauge,label,statusIcons);layer.append(node);
   return {node,img,health,bar,label,ready,gauge,gaugeBar,icons,picture:imageState(img)};
  }
  function updateEntity(record,unit,state,enemy){
   const media=content.media[unit.characterId],actions=media?.actions||{},casting=(castUntil.get(unit.id)||0)>state.tick;
   const action=(casting?actions.skill_ready:actions.idle)||actions.idle,still=state.status!=='running';
   record.picture.options=[still?(action?.poster||actions.idle?.poster):action,action?.poster,actions.idle?.poster,still?null:actions.idle,
    media?.avatar?{url:media.avatar,width:32,height:32,anchorX:16,anchorY:28,avatar:true}:null];
   record.picture.scale=scaleFor(media,enemy?unit.rank:'ally');paintImage(record.picture);
   record.node.style.left=`${unit.x/5*100}%`;record.node.style.top=`${unit.y/7*100}%`;record.node.style.zIndex=String(Math.round(unit.y*10)+10);
   const ratio=Math.max(0,Math.min(1,unit.hp/unit.maxHp));record.bar.style.width=`${ratio*100}%`;
   attr(record.health,'aria-valuemin',0);attr(record.health,'aria-valuemax',unit.maxHp);attr(record.health,'aria-valuenow',Math.max(0,Math.round(unit.hp)));
   const isReady=!enemy&&state.tick>=unit.readyAtTick;record.node.classList.toggle('is-ready',isReady);
   if(!enemy)record.gaugeBar.style.width=`${charge(unit.characterId,remaining(unit))}%`;
   record.node.classList.toggle('is-casting',casting);record.node.classList.toggle('is-missing',!record.picture.current);
   const buffs=(unit.statuses||[]).filter(b=>b.until>state.tick&&(b.type!=='shield'||b.remaining>0)
    &&(b.type!=='followup'||b.procs<(b.maxProcs||1)));
   const badges=[['shield','盾','护盾'],['healReduction','疗↓','治疗降低'],['slow','缓','减速'],['attackUp','↑','攻击提升'],['haste','速','攻速提升'],['basicHits','连','连击'],['followup','追','追击']]
    .filter(([type])=>buffs.some(b=>b.type===type)).slice(0,3);
   record.icons.forEach((icon,i)=>{const badge=badges[i];icon.hidden=!badge;if(badge){setText(icon,badge[1]);attr(icon,'title',badge[2]);attr(icon,'aria-label',badge[2]);}});
   record.node.classList.toggle('has-shield',buffs.some(b=>b.type==='shield'));
   record.node.classList.toggle('is-low-health',!enemy&&ratio<=.25);
   record.node.classList.toggle('is-hurt',(flashes.get(unit.id)?.hurt||0)>state.tick);
   record.node.classList.toggle('is-healed',(flashes.get(unit.id)?.heal||0)>state.tick);
   setText(record.label,enemy?(unit.rank==='boss'?'Boss':'先锋'):record.picture.current?'':name(unit.characterId));
  }
  function removeRecord(map,key,record){record.img?.removeEventListener('error',record.picture?.onError);record.node.remove();map.delete(key);castUntil.delete(key);}
  function updateUnits(state){
   const active=new Set();
   for(const [list,enemy] of [[state.units,false],[state.enemies,true]])for(const unit of list.filter(alive)){
    active.add(unit.id);let record=entities.get(unit.id);if(!record){record=createEntity(unit,enemy);entities.set(unit.id,record);}updateEntity(record,unit,state,enemy);
   }
   for(const [id,record]of entities)if(!active.has(id))removeRecord(entities,id,record);
   const waiting=new Set();for(const item of state.coffins){
    const id=item.characterId;waiting.add(id);let record=coffins.get(id);
    if(!record){const node=el('div','battle-coffin'),img=el('img','battle-sprite'),label=el('span','battle-coffin-time');img.alt='';img.draggable=false;node.append(img,label);layer.append(node);
     record={node,img,label,picture:imageState(img)};coffins.set(id,record);}
    record.node.style.left=`${(item.col+.5)/5*100}%`;record.node.style.top=`${(item.row+.5)/7*100}%`;
    record.picture.options=[content.coffin];record.picture.scale=2;paintImage(record.picture);setText(record.label,`${Math.max(0,Math.ceil((item.releaseAtTick-state.tick)/20))}s`);
   }
   for(const [id,record]of coffins)if(!waiting.has(id))removeRecord(coffins,id,record);
   for(const cell of cells){
    const unit=state.units.find(u=>alive(u)&&u.col===Number(cell.dataset.col)&&u.row===Number(cell.dataset.row)),coffin=state.coffins.find(c=>c.col===Number(cell.dataset.col)&&c.row===Number(cell.dataset.row));
    if(unit)cell.dataset.unitId=String(unit.id);else delete cell.dataset.unitId;
    cell.classList.toggle('is-occupied',!!unit||!!coffin);cell.classList.toggle('is-ready',!!unit&&state.tick>=unit.readyAtTick);
    attr(cell,'aria-label',`第${Number(cell.dataset.row)+1}行第${Number(cell.dataset.col)+1}列${unit?'，'+name(unit.characterId)+'，生命'+Math.ceil(unit.hp)+(state.tick>=unit.readyAtTick?'，技能就绪':''):coffin?'，'+name(coffin.characterId)+'复归中':'，空地'}`);
   }
  }
  for(let row=0;row<7;row++)for(let col=0;col<5;col++){
   const cell=el('button','battle-cell');cell.type='button';cell.dataset.col=String(col);cell.dataset.row=String(row);attr(cell,'aria-label',`第${row+1}行第${col+1}列，空地`);cells.push(cell);grid.append(cell);
  }
  function drawRoster(state){
   state.squad.forEach((id,index)=>{
    let card=cards.get(id);if(!card){
     const node=el('button','battle-roster-card'),img=el('img'),title=el('span','battle-roster-name',name(id)),hint=el('span','battle-roster-hint'),gauge=el('span','battle-card-charge'),gaugeBar=el('i');
     node.type='button';node.dataset.characterId=id;node.dataset.gesture='deploy';img.alt='';img.draggable=false;img.src=content.media[id]?.avatar||'';
     gauge.append(gaugeBar);gauge.setAttribute('role','progressbar');gauge.setAttribute('aria-label',`${name(id)}技能充能`);
     node.append(img,title,hint,gauge);if(index===0){const flag=el('span','battle-leader','⚑');flag.setAttribute('aria-label','队长');node.append(flag);}roster.append(node);card={node,hint,gauge,gaugeBar};cards.set(id,card);
    }
    const unit=state.units.find(u=>alive(u)&&u.characterId===id),coffin=state.coffins.find(c=>c.characterId===id),cost=content.characters[id]?.stats.deployCost||20;
    const reserve=state.reserves?.[id],ticks=unit?remaining(unit):reserve?.remainingTicks,percent=ticks===undefined?0:charge(id,ticks);
    const label=unit?(ticks<=0?'技能就绪':`${Math.ceil(ticks/20)}s · ${percent}%`):coffin?`${Math.max(0,Math.ceil((coffin.releaseAtTick-state.tick)/20))}s 复归`:reserve?`${cost} 部署 · 生命${Math.ceil(reserve.hp)}`:`${cost} 部署`;
    card.node.disabled=!!coffin||state.status!=='running'||(!unit&&state.energy<cost);
    if(unit){card.node.dataset.battleUnitId=String(unit.id);delete card.node.dataset.gesture;}else{delete card.node.dataset.battleUnitId;card.node.dataset.gesture='deploy';}
    card.gauge.hidden=!unit&&!reserve;card.gaugeBar.style.width=`${percent}%`;attr(card.gauge,'aria-valuemin',0);attr(card.gauge,'aria-valuemax',100);attr(card.gauge,'aria-valuenow',percent);
    attr(card.node,'title',reserve?`保留生命 ${Math.ceil(reserve.hp)}，充能剩余 ${Math.ceil(ticks/20)} 秒；待部署时停止充能。`:label);
    card.node.classList.toggle('is-deployed',!!unit);card.node.classList.toggle('is-ready',!!unit&&state.tick>=unit.readyAtTick);setText(card.hint,label);attr(card.node,'aria-label',`${index===0?'队长，':''}${name(id)}，${label}`);
   });
  }
  function size(){
   const nextWidth=Math.max(1,pendingWidth),nextDpr=Math.min(2,Math.max(1,root.devicePixelRatio||1));if(nextWidth===width&&nextDpr===dpr)return;
   width=nextWidth;height=width*7/5;dpr=nextDpr;
   for(const canvas of [ground,fx]){canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);}
   if(!groundCtx)return;groundCtx.setTransform(dpr,0,0,dpr,0,0);groundCtx.clearRect(0,0,width,height);
   const unit=width/5;for(let row=0;row<7;row++)for(let col=0;col<5;col++){
    groundCtx.fillStyle=(row+col)%2?'#466d4c':'#4c7752';groundCtx.fillRect(col*unit,row*unit,unit,unit);
    groundCtx.fillStyle='#b9d89125';groundCtx.fillRect((col+.22)*unit,(row+.67)*unit,2,5);groundCtx.fillRect((col+.76)*unit,(row+.27)*unit,2,4);
   }
   groundCtx.fillStyle='#bead7940';groundCtx.fillRect(0,height-8,width,8);
  }
  function collect(state,events){
   visual.ingest(state,events);
   for(const event of events){
    if(!Number.isFinite(event.id)||event.id<=lastEventId)continue;lastEventId=event.id;
    if(event.type==='cast'){
     const actor=state.units.find(unit=>unit.id===event.entityId),duration=content.media[actor?.characterId]?.actions?.skill_ready?.duration||.7;
     castUntil.set(event.entityId,state.tick+Math.max(1,Math.ceil(duration*20)));
    }
    if(['damage','heal'].includes(event.type)&&event.value>0&&event.targetId){const item=flashes.get(event.targetId)||{};item[event.type==='heal'?'heal':'hurt']=state.tick+4;flashes.set(event.targetId,item);}
    if(event.type==='intermission'){setText(banner,'本波已清除');bannerUntil=state.tick+30;}
    if(event.type==='rage-warning'){setText(banner,'敌人即将狂暴');bannerUntil=state.tick+50;}
   }
   for(const [id,end]of castUntil)if(end<=state.tick)castUntil.delete(id);
   for(const [id,value]of flashes)if(Math.max(value.hurt||0,value.heal||0)<=state.tick)flashes.delete(id);
   if(shownWave!==state.wave){shownWave=state.wave;setText(banner,`第 ${state.wave} 波 · ${state.enemies.some(e=>e.rank==='boss')?'Boss 来袭':'敌人来袭'}`);bannerUntil=state.tick+40;}
   banner.hidden=state.tick>=bannerUntil||['won','lost'].includes(state.status);
   const boss=state.enemies.find(e=>e.rank==='boss'&&e.hp>0);bossHud.hidden=!boss;
   if(boss){setText(bossName,`${name(boss.characterId)} · Boss`);bossBar.style.width=`${Math.max(0,boss.hp/boss.maxHp*100)}%`;setText(bossValue,`${Math.ceil(boss.hp/boss.maxHp*100)}%`);
    attr(bossTrack,'aria-label',`${name(boss.characterId)} Boss 生命`);attr(bossTrack,'aria-valuemin',0);attr(bossTrack,'aria-valuemax',boss.maxHp);attr(bossTrack,'aria-valuenow',Math.max(0,Math.ceil(boss.hp)));}
  }
  function effects(state){
   if(fxCtx)visual.draw(fxCtx,state,{width,height,dpr,selection});
  }
  function setSelection(value){
   if(dead)return;selection=value;
   const unit=lastState?.units.find(u=>u.id===value?.unitId&&u.hp>0);if(value?.unitId&&!unit)selection=null;
   for(const [id,card]of cards)attr(card.node,'aria-pressed',value?.characterId===id||unit?.characterId===id);
   board.classList.toggle('is-selecting',!!value?.characterId);actions.hidden=!unit;
   if(unit){
    const def=content.characters[unit.characterId],ticks=remaining(unit),percent=charge(unit.characterId,ticks),running=lastState.status==='running';
    setText(actionTitle,`${def.name} · ${def.skill.name}`);setText(actionHint,ticks<=0?'技能已就绪':`充能 ${percent}% · ${Math.ceil(ticks/20)} 秒`);actionBar.style.width=`${percent}%`;
    setText(castButton,ticks<=0?'发动技能':`充能 ${Math.ceil(ticks/20)}s`);castButton.disabled=!running||ticks>0;
    const cost=content.recallCost??10;setText(recallButton,`回收 ${cost}`);attr(recallButton,'aria-label',`回收${def.name}，消耗${cost}能量，保留生命与充能`);recallButton.disabled=!running||lastState.energy<cost;
   }
   for(const cell of cells){const match=value?.cell&&Number(cell.dataset.col)===value.cell.col&&Number(cell.dataset.row)===value.cell.row;
    cell.classList.toggle('is-drop-valid',!!match&&value.valid!==false);cell.classList.toggle('is-drop-invalid',!!match&&value.valid===false);cell.classList.toggle('is-selected',!!unit&&String(unit.id)===cell.dataset.unitId);}
   if(lastState)effects(lastState);
  }
  function draw(state,events=[]){
   if(dead)return;lastState=state;size();collect(state,events);updateUnits(state);drawRoster(state);setSelection(selection);
   setText(wave,`第 ${state.wave} 波`);setText(base,`据点 ${Math.max(0,Math.ceil(state.baseHp))}`);
   setText(entry,state.status==='paused'?'已暂停':state.status==='won'?'已通关':state.status==='lost'?'挑战结束':state.nextWaveTick?`${Math.max(0,Math.ceil((state.nextWaveTick-state.tick)/20))}s 后迎敌`:'↓ 敌人入口');
   setText(energyValue,`${Math.floor(state.energy)} / 120`);attr(energyDisplay,'aria-label',`公共能量 ${Math.floor(state.energy)}，只用于部署和回收；角色技能独立充能`);
   board.classList.toggle('is-paused',state.status!=='running');
  }
  function resized(value){if(dead||!value||value===pendingWidth)return;pendingWidth=value;if(lastState)draw(lastState);}
  const onResize=()=>resized(board.clientWidth);
  const observer=root.ResizeObserver?new root.ResizeObserver(entries=>resized(entries[0]?.contentRect.width)):null;
  if(observer)observer.observe(board);else root.addEventListener('resize',onResize);
  const motionChange=()=>{if(dead)return;visual.setReducedMotion(!!motion.matches);if(lastState)draw(lastState);};
  motion?.addEventListener?.('change',motionChange);
  function destroy(){if(dead)return;dead=true;observer?.disconnect();root.removeEventListener('resize',onResize);
   for(const [id,record]of entities)removeRecord(entities,id,record);for(const [id,record]of coffins)removeRecord(coffins,id,record);
   motion?.removeEventListener?.('change',motionChange);visual.clear();cards.clear();flashes.clear();selection=null;field.remove();
  }
  function retry(){if(dead)return;for(const record of [...entities.values(),...coffins.values()]){record.picture.failed.clear();record.picture.url=null;record.picture.retry=(record.picture.retry||0)+1;}if(lastState)draw(lastState);}
  return {board,roster,energyDisplay,actions,castButton,recallButton,status,draw,setSelection,retry,destroy};
 }
 const api={create};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WFBattleRender=api;
})(typeof window==='undefined'?globalThis:window);
