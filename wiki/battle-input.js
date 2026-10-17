((root)=>{
 'use strict';
 function cellAt(x,y,r){if(!r.width||!r.height||x<r.left||y<r.top||x>=r.left+r.width||y>=r.top+r.height)return null;return {col:Math.floor((x-r.left)/r.width*5),row:Math.floor((y-r.top)/r.height*7)};}
 function create({host,board,canSelect,onVoice,onSelect,onDrop,onCell,onUnit=()=>{},onPreview=()=>null,onCancel=()=>{},window=root,document=root.document}){
  let gesture=null,ghost=null,dead=false,ignorePointerClick=false;const removers=[];
  function listen(node,type,fn){node.addEventListener(type,fn);removers.push(()=>node.removeEventListener(type,fn));}
  function cancel(){const previous=gesture;gesture=null;if(previous)try{previous.source.releasePointerCapture?.(previous.id);}catch{}ghost?.remove();ghost=null;onPreview(null,null);}
  const choice=node=>({characterId:node.dataset.characterId});
  listen(host,'pointerdown',event=>{
   ignorePointerClick=false;
   if(gesture){cancel();return;}if(dead||event.button!==0)return;
   const source=event.target.closest?.('[data-gesture]');if(!source||!host.contains(source)||source.disabled||!canSelect(choice(source)))return;
   gesture={id:event.pointerId,source,x:event.clientX,y:event.clientY,drag:false,choice:choice(source)};
   try{source.setPointerCapture?.(event.pointerId);}catch{}
  });
  listen(host,'pointermove',event=>{
   if(!gesture||event.pointerId!==gesture.id)return;
   if(!gesture.drag&&Math.hypot(event.clientX-gesture.x,event.clientY-gesture.y)>=7){gesture.drag=true;
    if(gesture.choice.characterId)onVoice(gesture.choice.characterId);
    ghost=document.createElement('div');ghost.className='battle-drag-ghost';const avatar=gesture.source.querySelector?.('img');
    if(avatar)ghost.append(avatar.cloneNode());else ghost.textContent='＋';document.body.append(ghost);
   }
   if(gesture.drag){event.preventDefault();ghost.style.left=event.clientX+'px';ghost.style.top=event.clientY+'px';
    const valid=onPreview(gesture.choice,cellAt(event.clientX,event.clientY,board.getBoundingClientRect()));ghost.style.borderColor=valid?'#3bcc91':'#ff687b';}
  });
  listen(host,'pointerup',event=>{
   if(!gesture||event.pointerId!==gesture.id)return;const current=gesture;
   ignorePointerClick=true;
   if(current.drag){const cell=cellAt(event.clientX,event.clientY,board.getBoundingClientRect());if(cell)onDrop(current.choice,cell);}
   else if(canSelect(current.choice)){if(current.choice.characterId)onVoice(current.choice.characterId);onSelect(current.choice);}
   cancel();
  });
  listen(host,'pointercancel',cancel);listen(host,'lostpointercapture',cancel);listen(window,'blur',cancel);
  listen(window,'keydown',event=>{if(event.key==='Escape'){cancel();onCancel();}});
  listen(host,'click',event=>{
   if(event.detail>0&&ignorePointerClick){ignorePointerClick=false;return;}
   const deployed=event.target.closest?.('[data-battle-unit-id]');
   if(deployed?.dataset.battleUnitId&&host.contains(deployed)){if(!deployed.disabled)onUnit(Number(deployed.dataset.battleUnitId));return;}
   const source=event.target.closest?.('[data-gesture]');
   if(source&&host.contains(source)){if(event.detail===0&&!source.disabled&&canSelect(choice(source))){const c=choice(source);if(c.characterId)onVoice(c.characterId);onSelect(c);}return;}
   const cell=event.target.closest?.('[data-col][data-row]');if(cell&&host.contains(cell))onCell({col:Number(cell.dataset.col),row:Number(cell.dataset.row)});
  });
  return {cancel,destroy(){dead=true;cancel();removers.forEach(remove=>remove());}};
 }
 const api={create,cellAt};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WFBattleInput=api;
})(typeof window==='undefined'?globalThis:window);
