((root)=>{
 'use strict';
 const roles={melee:'近战',ranged:'远程',healer:'治疗',support:'增益'},elements={fire:'火',water:'水',thunder:'雷',wind:'风',light:'光',dark:'暗'};
 function toggle(squad,id,characters){if(!characters[id])return [...squad];return squad.includes(id)?squad.filter(v=>v!==id):squad.length<6?[...squad,id]:[...squad];}
 function matches(c,query,element,role){const hay=[c.name,c.title,c.theme,...(c.aliases||[])].join(' ').toLowerCase();return (!element||c.element===element)&&(!role||c.role===role)&&query.toLowerCase().trim().split(/\s+/).every(word=>hay.includes(word));}
 function mount({host,content,ui,store,onStart,onInspect}){
  const {el}=ui,box=el('section','battle-selection'),toolbar=el('div','battle-toolbar'),squadView=el('div','battle-squad'),pool=el('div','battle-pool');
  let squad=store.read().value.squad,mode='campaign',stageId=content.stages[0].id,selected=Object.values(content.characters)[0];
  const status=el('p','battle-notice'),count=el('strong',''),search=el('input','battle-search');search.type='search';search.placeholder='查找名字、版本或别名';search.setAttribute('aria-label','查找 MOD 角色');
  const element=el('select'),role=el('select');element.setAttribute('aria-label','角色属性');role.setAttribute('aria-label','角色定位');
  for(const [value,label]of [['','全部属性'],...Object.entries(elements)]){const opt=el('option','',label);opt.value=value;element.append(opt);}
  for(const [value,label]of [['','全部定位'],...Object.entries(roles)]){const opt=el('option','',label);opt.value=value;role.append(opt);}
  const modeSelect=el('select'),stageSelect=el('select');modeSelect.setAttribute('aria-label','挑战模式');stageSelect.setAttribute('aria-label','挑战关卡');
  for(const [v,label]of [['campaign','关卡挑战'],['endless','无尽模式']]){const opt=el('option','',label);opt.value=v;modeSelect.append(opt);}
  const records=store.read().value;for(const stage of content.stages){const opt=el('option','',stage.name+(records.campaign[stage.id]?' · 已通关':''));opt.value=stage.id;stageSelect.append(opt);}
  const start=el('button','primary-button','选择六位角色'),description=el('div','battle-character-summary'),inspect=el('button','secondary-button','技能详情');start.type=inspect.type='button';
  const choices=new Map();
  function describe(c){selected=c;description.textContent=`${c.name} · ${c.title||c.theme} · ${roles[c.role]}｜${c.skill.name}：${c.skill.description}`;}
  function drawSquad(){squadView.replaceChildren();squad.forEach((id,index)=>{const c=content.characters[id],slot=el('div','battle-squad-slot'),button=el('button','battle-choice');button.type='button';button.setAttribute('aria-label',`移出${c.name}`);
   const img=el('img');img.src=content.media[id].avatar;img.alt='';img.draggable=false;button.append(img,el('span','',`${index===0?'⚑':index+1} ${c.name}`));button.addEventListener('click',()=>choose(c));slot.append(button);
   if(index>0){const move=el('button','battle-order-button','← 前移');move.type='button';move.setAttribute('aria-label',`将${c.name}前移一位`);move.addEventListener('click',()=>{
    [squad[index-1],squad[index]]=[squad[index],squad[index-1]];const saved=store.writeSquad(squad);if(!saved.ok)status.textContent=saved.error;drawSquad();});slot.append(move);}squadView.append(slot);});
   for(let i=squad.length;i<6;i++)squadView.append(el('span','battle-empty-slot',String(i+1)));
   count.textContent=`出战 ${squad.length}/6`;start.disabled=squad.length!==6;start.textContent=squad.length===6?'开始战斗':'选择六位角色';
   for(const [id,node]of choices)node.setAttribute('aria-pressed',String(squad.includes(id)));
  }
  function choose(c){if(!squad.includes(c.id)&&squad.length===6){status.textContent='阵容已满，点击上方头像移出后再选择。';describe(c);return;}
   squad=toggle(squad,c.id,content.characters);const result=store.writeSquad(squad);status.textContent=result.ok?'第一位为队长；再次点击头像可移出。':result.error;describe(c);drawSquad();}
  for(const c of Object.values(content.characters)){
   const node=el('button','battle-choice');node.type='button';node.dataset.characterId=c.id;node.title=`${c.name} · ${c.title} · ${c.skill.name}`;node.setAttribute('aria-label',`${c.name} ${c.title} ${roles[c.role]}`);
   const img=el('img');img.src=content.media[c.id].avatar;img.alt='';img.loading='lazy';img.decoding='async';img.draggable=false;
   node.append(img,el('b','battle-mod-tag',c.tag||'MOD'),el('span','',c.name));node.addEventListener('click',()=>choose(c));choices.set(c.id,node);pool.append(node);
  }
  function filter(){let found=0;for(const [id,node]of choices){node.hidden=!matches(content.characters[id],search.value,element.value,role.value);if(!node.hidden)found++;}status.textContent=`${found} 位可选角色 · 仅本机保存阵容和战果`;}
  search.addEventListener('input',filter);element.addEventListener('change',filter);role.addEventListener('change',filter);
  modeSelect.addEventListener('change',()=>{mode=modeSelect.value;stageSelect.hidden=mode==='endless';status.textContent=mode==='endless'?`个人最高：第 ${store.read().value.endless.bestWave} 波`:'每关三波，清除敌人保护据点。';});
  stageSelect.addEventListener('change',()=>stageId=stageSelect.value);inspect.addEventListener('click',()=>onInspect(selected));start.addEventListener('click',()=>{if(squad.length===6)onStart({squad:[...squad],mode,stageId});});
  toolbar.append(modeSelect,stageSelect);const filters=el('div','battle-toolbar');filters.append(search,element,role);
  box.append(toolbar,count,squadView,start,description,inspect,filters,status,pool);host.replaceChildren(box);describe(selected);drawSquad();filter();
  return {destroy(){box.remove();}};
 }
 const api={mount,toggle,matches,roles,elements};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WFBattleSelection=api;
})(typeof window==='undefined'?globalThis:window);
