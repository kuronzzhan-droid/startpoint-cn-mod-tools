/* A session owns every listener, clock, gesture and sound until actual page leave. */
((root)=>{
 'use strict';
 function makeGuard({getState,isConnected,pause,resume,ask}){
  return {isActive:isConnected,needsProtection:()=>['running','paused'].includes(getState()?.status),
   async canLeave(){const running=getState()?.status==='running';pause('已暂停，等待离开确认');
    const answer=await ask();if(!answer&&running&&isConnected())resume();return answer;}};
 }
 function render(host,_data,ui){
  const content=root.WF_BATTLE_CONTENT,{el}=ui,box=el('section','battle-root');
  const header=el('header','battle-heading'),back=el('a','back-button','‹ 副本');back.href='#dungeons';header.append(back,el('h1','','放置挑战'));
  const toolbar=el('div','battle-toolbar'),area=el('div','battle-area'),notice=el('p','battle-notice');notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');
  box.append(header,toolbar,notice,area);host.replaceChildren(box);
  const store=root.WFBattleStorage.create({characterIds:Object.keys(content.characters),stageIds:content.stages.map(s=>s.id)});
  let state=null,view=null,input=null,media=null,clock=null,selection=null,choice=null,dead=false,dialog=null,lastOptions=null,settled=false,lastNoticeTick=-Infinity;
  const button=(label,action,cls='secondary-button')=>{const node=el('button',cls,label);node.type='button';node.addEventListener('click',action);return node;};
  const message=(text,announce=true)=>{if(dead)return;if(notice.textContent!==text){notice.setAttribute('aria-live',announce?'polite':'off');notice.textContent=text;notice.title=text;}lastNoticeTick=state?.tick??-Infinity;};
  function eventNotice(events){
   const fallen=events.filter(e=>e.type==='death'),returned=events.filter(e=>e.type==='returned'),ready=events.filter(e=>e.type==='ready');
   const names=list=>[...new Set(list.map(e=>content.characters[e.characterId]?.name||'角色'))].join('、');
   if(fallen.length)message(`${names(fallen)}倒下 · 棺材占格20秒，复归后可再部署`);
   else if(state.tick-lastNoticeTick>=80){
    if(returned.length)message(`${names(returned)}已复归 · 选择头像重新部署`);
    else if(ready.length)message(`${names(ready)}技能就绪 · 点击头像发动`);
   }
  }
  const resourceFailure=text=>{retry.hidden=false;message(text);};
  const ask=(text,title='离开战斗？')=>root.WFCommunityAdminConfirm.ask(text,{title,confirmLabel:'确定',cancelLabel:'继续当前战斗'});
  function pause(reason='战斗已暂停'){
   if(!state||!['running','paused'].includes(state.status))return;
   root.WFBattleModel.setPaused(state,true);clock?.pause();media?.setPaused(true);input?.cancel();choice=null;view?.setSelection(null);view?.draw(state);pauseButton.textContent='继续';message(reason);
  }
  function resume(){if(dead||dialog||document.hidden||state?.status!=='paused')return;
   root.WFBattleModel.setPaused(state,false);media?.setPaused(false);clock.start();pauseButton.textContent='暂停';message('拖头像部署；点击场上角色或头像发动技能、回收。');}
  function closeDialog(){if(!dialog)return;const previous=dialog;dialog=null;previous.close?.();previous.remove();}
  function showInfo(title,lines){pause('查看资料中，关闭后点击继续');closeDialog();dialog=el('dialog','battle-dialog');const node=dialog;
   node.setAttribute('aria-label',title);node.append(el('h2','',title));lines.forEach(line=>node.append(el('p','',line)));
   node.append(button('关闭',closeDialog));node.addEventListener('cancel',event=>{event.preventDefault();closeDialog();});document.body.append(node);node.showModal();}
  function inspect(c){const mediaDef=content.media[c.id];showInfo(`${c.name} · ${c.title||c.theme}`,[
   `${root.WFBattleSelection.roles[c.role]} · 生命 ${c.stats.hp} · 射程 ${c.stats.range} 格 · 部署 ${c.stats.deployCost} 能量`,
   `${c.skill.name}：${c.skill.description}`,`独立技能槽 ${c.skill.gauge} 点 · 本玩法基准每秒 20 点${c.skill.chargeSpeed?`，充能速度 +${Math.round(c.skill.chargeSpeed*100)}%`:''} · 满槽约 ${c.skill.cooldown} 秒`,
   `按原角色技能槽与可适配充能效果换算，秒数仅用于本放置玩法。${c.skill.initial?`首次部署初始充能 ${Math.round(c.skill.initial*100)}%。`:''}技能满槽发动，不消耗公共能量。`,
   ...(c.skill.refund?[`施技后回槽 ${Math.round(c.skill.refund.ratio*100)}%${c.skill.refund.ct>0?` · 回槽触发冷却 ${c.skill.refund.ct} 秒`:''}${c.skill.refund.limit!==undefined?` · 每局最多触发 ${c.skill.refund.limit} 次`:''}`]:[]),
   (mediaDef.missingCues||[]).length?'部分场景语音尚未确认，使用视觉提示；本体音效与角色台词分别映射。':'使用本角色已核实的出战、准备和发动声音。']);}
  const pauseButton=button('暂停',()=>state?.status==='paused'?resume():pause());
  const sound=button('声音',()=>{const settings=store.read().value.settings;const result=store.writeSettings({muted:!settings.muted});applySettings(result.value.settings);media?.retry();message(result.ok?(result.value.settings.muted?'声音已关闭':'声音已开启，下次角色事件将尝试播放'):result.error);});
  const retry=button('重试资源',()=>{retry.hidden=true;media?.retry();view?.retry();message('已重试图片和声音；继续战斗时播放后续角色事件。');});retry.hidden=true;
  const volume=el('input');volume.type='range';volume.min='0';volume.max='1';volume.step='.05';volume.setAttribute('aria-label','声音音量');
  volume.addEventListener('change',()=>{const result=store.writeSettings({volume:Number(volume.value)});applySettings(result.value.settings);if(!result.ok)message(result.error);});
  function applySettings(settings){sound.textContent=settings.muted?'声音关':'声音开';sound.setAttribute('aria-pressed',String(!settings.muted));volume.value=String(settings.volume);media?.setMuted(settings.muted);media?.setVolume(settings.volume);}
  const help=button('说明',()=>showInfo('放置挑战怎么玩',[
   '选择六位 MOD 角色组成阵容。第一位是队长；拖动下方头像到草地空格，或点击头像后点击空格部署。',
   '角色自动攻击或治疗，各自的技能槽独立充能。点场上角色或已部署头像，满槽即可发动技能，不消耗公共能量。详情中可查看招牌技能和基础充能时间。',
   `公共能量每秒增加 3，击败敌人获得 10；仅用于部署和回收。花费 ${content.recallCost??10} 能量回收可立即腾格，保留剩余生命与充能；待部署时停止充能，再次部署仍需支付部署费。`,
   '阵亡后留下棺材并占格 20 秒。倒计时结束后需要重新支付部署费，不会自动复活。',
   '敌人从上方接近，攻击身边最近角色；冲到底部会攻击据点。清空一波后休息 5 秒。关卡共三波，无尽逐波增强。',
   '暂停或切到后台不会推进战斗。阵容、最佳成绩只存本机；战斗不向社区上传记录。声音和像素资源按需下载。']));
  const restart=button('重开',async()=>{more.open=false;if(!lastOptions)return;const wasRunning=state?.status==='running';pause();if(!state||state.result||await ask('放弃本场进度，使用当前六人阵容重新开始？','重新开始？'))begin(lastOptions);else if(wasRunning)resume();});
  const change=button('换阵容',async()=>{more.open=false;const wasRunning=state?.status==='running';pause();if(!state||state.result||await ask('放弃本场进度并返回选择阵容？','重新选择？'))prepare();else if(wasRunning)resume();});
  const more=el('details','battle-more'),moreTitle=el('summary','','更多'),morePanel=el('div','battle-more-panel'),volumeLabel=el('label','battle-volume','音量');volumeLabel.append(volume);morePanel.append(volumeLabel,restart,change);more.append(moreTitle,morePanel);
  toolbar.className+=' battle-main-toolbar';toolbar.append(pauseButton,sound,help,more,retry);
  function stopSession(){clock?.destroy();input?.destroy();media?.destroy();view?.destroy();selection?.destroy();clock=input=media=view=selection=null;choice=null;closeDialog();}
  function prepare(){stopSession();state=null;more.open=false;pauseButton.hidden=restart.hidden=change.hidden=true;area.replaceChildren();
   selection=root.WFBattleSelection.mount({host:area,content,ui,store,onStart:begin,onInspect:inspect});applySettings(store.read().value.settings);message('选择六位角色，守住草地尽头的据点。');}
  function select(value){choice=choice?.characterId===value.characterId?null:value;view.setSelection(choice);message(choice?`选择空格部署 ${content.characters[choice.characterId].name}`:'已取消选择');}
  function selectUnit(unitId){if(state?.status!=='running')return;const unit=state.units.find(u=>u.id===unitId&&u.hp>0);if(!unit)return;
   choice=choice?.unitId===unitId?null:{unitId};view.setSelection(choice);message(choice?'满槽后点发动技能；回收保留生命和剩余充能。':'已取消选择');}
  function command(action,text){if(state?.status!=='running')return;
   const result=root.WFBattleModel.dispatch(state,{id:state.lastCommandId+1,...action});
   if(result.ok){if(action.type!=='cast')choice=null;view.setSelection(choice);media.handle(result.events);view.draw(state,result.events);message(text);}else message(result.reason);
  }
  function execute(value,cell){command({type:'deploy',characterId:value.characterId,...cell},'部署完成');
  }
  function cellClick(cell){if(state?.status!=='running')return;if(choice?.characterId){execute(choice,cell);return;}
   const unit=state.units.find(u=>u.col===cell.col&&u.row===cell.row&&u.hp>0);if(unit){selectUnit(unit.id);return;}
   const coffin=state.coffins.find(c=>c.col===cell.col&&c.row===cell.row);message(coffin?`复归剩余 ${Math.ceil((coffin.releaseAtTick-state.tick)/20)} 秒`:'先选择下方头像，再选择空格。');}
  function finish(){if(settled)return;settled=true;clock.pause();media.stop();input.cancel();pauseButton.hidden=true;
   const saved=store.record(state.result),result=el('section','battle-result');result.setAttribute('aria-label','战斗结果');
   result.append(el('h2','',state.result.won?'守住了据点！':'挑战结束'),el('p','',`第 ${state.wave} 波 · 击败 ${state.kills} · ${state.time.toFixed(1)} 秒`));
   if(state.mode==='endless')result.append(el('p','',`本机最高：第 ${saved.value.endless.bestWave} 波`));
   result.append(button('再来一次',()=>begin(lastOptions),'primary-button'),button('选择阵容',prepare));area.prepend(result);message(saved.ok?'成绩已保存在本机':saved.error);}
  function begin(options){if(dead)return;stopSession();lastOptions={...options,squad:[...options.squad]};state=root.WFBattleModel.create({content,...lastOptions});settled=false;
   area.replaceChildren();more.open=false;pauseButton.hidden=restart.hidden=change.hidden=false;pauseButton.textContent='暂停';
   media=root.WFBattleMedia.create({content,...store.read().value.settings,onFailure:resourceFailure});media.unlock();
   view=root.WFBattleRender.create({host:area,content,ui,onFailure:resourceFailure,onCast:unitId=>command({type:'cast',unitId},'技能已发动 · 不消耗公共能量'),
    onRecall:unitId=>command({type:'recall',unitId},'已回收 · 保留生命与充能，再部署时继续'),onInspect:unitId=>{const unit=state.units.find(u=>u.id===unitId&&u.hp>0);if(unit)inspect(content.characters[unit.characterId]);}});view.draw(state);
   const loadCurrent=()=>media.preload([...state.squad,...new Set(state.enemies.map(e=>e.characterId))]);loadCurrent();
   input=root.WFBattleInput.create({host:area,board:view.board,canSelect:value=>state.status==='running'&&!state.units.some(u=>u.characterId===value.characterId)&&!state.coffins.some(c=>c.characterId===value.characterId),
    onVoice:id=>media.deploy(id),onSelect:select,onDrop:execute,onCell:cellClick,onUnit:selectUnit,onCancel:()=>{choice=null;view.setSelection(null);},onPreview:(value,cell)=>{
     if(!value||!cell){view.setSelection(choice);return false;}const reason=root.WFBattleModel.canDeploy(state,value.characterId,cell.col,cell.row);
     view.setSelection({...value,cell,valid:!reason});message(reason||'松手部署',false);return !reason;
    }});
   clock=root.WFBattleClock.create({step:()=>{const events=root.WFBattleModel.advance(state);media.handle(events);view.draw(state,events);eventNotice(events);
    if(events.some(e=>e.type==='wave'))loadCurrent();if(events.some(e=>e.type==='rage-warning'))message('敌人即将狂暴，攻击会逐渐增强');if(state.result)finish();},
    // Native WebP animates independently. Tick/input/resize draws avoid duplicate work at 120+ Hz.
    render:()=>{},onLag:()=>pause('运行出现延迟，已自动暂停。点击继续。')});
   clock.start();applySettings(store.read().value.settings);message('拖头像部署；也可点击头像后点击草地。');
  }
  const guard=makeGuard({getState:()=>state,isConnected:()=>!dead&&box.isConnected,pause,resume,ask:()=>ask('离开会结束本场战斗，阵容与历史成绩仍保存在本机。')});
  const unregister=root.WFNavigationGuard.register(guard);
  function visibility(){if(document.hidden)pause('已切到后台，战斗暂停。回来后点击继续。');}
  function pageHide(){pause('页面已离开，战斗暂停。回来后点击继续。');}
  function storage(event){if(event.key===root.WFBattleStorage.key&&event.newValue){const result=store.mergeExternal(event.newValue);applySettings(result.value.settings);}}
  function destroy(){if(dead)return;dead=true;stopSession();store.destroy();unregister();root.removeEventListener('wf-page-leave',destroy);root.removeEventListener('storage',storage);document.removeEventListener('visibilitychange',visibility);root.removeEventListener('pagehide',pageHide);}
  root.addEventListener('wf-page-leave',destroy);root.addEventListener('storage',storage);document.addEventListener('visibilitychange',visibility);root.addEventListener('pagehide',pageHide);prepare();
  return {destroy};
 }
 const api={makeGuard,render};if(typeof module!=='undefined'&&module.exports)module.exports=api;else {root.WFBattlePage=api;root.renderWikiBattle=render;}
})(typeof window==='undefined'?globalThis:window);
