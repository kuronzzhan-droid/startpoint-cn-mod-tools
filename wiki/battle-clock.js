((root)=>{
 'use strict';
 function create({step,render,onLag,raf=root.requestAnimationFrame.bind(root),caf=root.cancelAnimationFrame.bind(root)}){
  let handle=null,running=false,dead=false,last=null,accumulated=0;
  function frame(now){handle=null;if(!running||dead)return;
   if(last!==null)accumulated+=Math.max(0,now-last);last=now;
   if(accumulated>250){pause();onLag();return;}
   let steps=0;while(running&&accumulated>=50&&steps++<5){accumulated-=50;step();}
   if(!dead)render(accumulated/50);if(running&&!dead)handle=raf(frame);
  }
  function pause(){running=false;if(handle!==null)caf(handle);handle=null;last=null;accumulated=0;}
  return {start(){if(dead||running)return;running=true;last=null;accumulated=0;handle=raf(frame);},pause,
   destroy(){pause();dead=true;},isRunning:()=>running};
 }
 const api={create};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WFBattleClock=api;
})(typeof window==='undefined'?globalThis:window);
