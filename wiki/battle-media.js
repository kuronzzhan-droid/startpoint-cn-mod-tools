/* Media randomness never enters simulation state. One voice channel per session. */
((root)=>{
 'use strict';
 function create({content,Audio=root.Audio,Image=root.Image,now=()=>Date.now(),random=Math.random,onFailure=()=>{},muted=false,volume=.65}){
  let dead=false,paused=false,current=null,queue=[],epoch=0,reusable=null,voiceToken=0;
  const recent=new Set(),lastPick=new Map(),deployAt=new Map(),failed=new Set(),images=new Map(),se=new Set(),seAt=new Map();
  const active=()=>!dead&&!paused&&!muted;
  function release(audio){audio.onended=null;audio.onerror=null;audio.pause();audio.removeAttribute?.('src');audio.load?.();}
  function stop(){epoch++;queue=[];if(current){release(current);current=null;}for(const audio of se)release(audio);se.clear();}
  function choose(id,cue,pool){const usable=(pool||[]).filter(url=>!failed.has(url));if(!usable.length)return null;
   const key=id+':'+cue,choices=usable.length>1?usable.filter(u=>u!==lastPick.get(key)):usable;
   const url=choices[Math.min(choices.length-1,Math.floor(random()*choices.length))];lastPick.set(key,url);return url;
  }
  function pump(){if(!active()||current)return;queue=queue.filter(item=>now()-item.at<=2000);const item=queue.shift();if(!item)return;
   const generation=epoch,token=++voiceToken,audio=reusable||new Audio();reusable=audio;audio.src=item.url;current=audio;audio.volume=volume;
   const done=()=>{if(dead||generation!==epoch||token!==voiceToken||current!==audio)return;release(audio);current=null;pump();};
   const fail=()=>{if(generation!==epoch||dead||token!==voiceToken)return;failed.add(item.url);onFailure('声音暂未播放，可点击「重试资源」重试');done();};
   audio.onended=done;audio.onerror=fail;try{const promise=audio.play();promise?.catch(fail);}catch{fail();}
  }
  function soundEffect(id,cue){if(!active()||!Audio)return;const url=choose(id,cue,content.media[id]?.seCues?.[cue]);if(!url||se.size>=3||now()-(seAt.get(url)??-Infinity)<250)return;
   seAt.set(url,now());const audio=new Audio(url),generation=epoch;se.add(audio);audio.volume=volume*.65;
   const done=()=>{if(generation!==epoch)return;release(audio);se.delete(audio);};audio.onended=done;audio.onerror=()=>{failed.add(url);done();};
   try{audio.play()?.catch(()=>{failed.add(url);done();});}catch{done();}
  }
  function voice(id,cue){if(!active()||!Audio)return;const url=choose(id,cue,content.media[id]?.voices?.[cue]);if(!url){soundEffect(id,cue);return;}
   queue.push({url,at:now(),priority:{cast:3,ready:2,death:2,deploy:1}[cue]||0});queue.sort((a,b)=>b.priority-a.priority||a.at-b.at);queue=queue.slice(0,2);pump();
  }
  function deploy(id){if(!active()||now()-(deployAt.get(id)??-Infinity)<3000)return;deployAt.set(id,now());voice(id,'deploy');}
  function handle(events){for(const e of events){if(recent.has(e.id))continue;recent.add(e.id);if(recent.size>256)recent.delete(recent.values().next().value);
   if(['ready','cast','death'].includes(e.type)&&e.characterId)voice(e.characterId,e.type);
   if(e.type==='attack'&&e.characterId)soundEffect(e.characterId,'attack');}}
  function preload(ids){const wanted=new Set([content.coffin?.url]);for(const id of ids){const media=content.media[id];if(media)for(const action of Object.values(media.actions||{})){wanted.add(action.url);if(action.poster)wanted.add(action.poster.url);}}
   // At most six allies and one enemy; discard references when a theme changes.
   for(const [url,entry] of images)if(!wanted.has(url)){entry.cancel();images.delete(url);}
   if(!Image)return Promise.resolve();const generation=epoch;
   return Promise.allSettled([...wanted].filter(Boolean).slice(0,30).map(url=>{if(images.has(url))return images.get(url).promise;let cancel=()=>{};const promise=new Promise(resolve=>{
    const img=new Image();const done=()=>{clearTimeout(timer);img.onload=img.onerror=null;resolve();};let timer=setTimeout(done,10000);
    cancel=()=>{done();img.removeAttribute?.('src');};img.onload=done;img.onerror=()=>{if(!dead&&generation===epoch)onFailure('部分像素图未载入，仍可继续战斗');done();};img.src=url;
   });images.set(url,{promise,cancel});return promise;}));
  }
  function unlock(){if(!Audio||dead||muted||current)return;reusable||=new Audio();
   // A silent PCM sample unlocks this same HTMLAudioElement during the user's click.
   const token=++voiceToken,audio=reusable;audio.src='data:audio/wav;base64,UklGRiYAAABXQVZFZm10IBAAAAABAAEARKwAAESsAAABAAgAZGF0YQIAAACAgA==';audio.volume=volume;
   try{audio.play()?.then(()=>{if(!dead&&token===voiceToken&&!current)release(audio);}).catch(()=>{if(!dead&&token===voiceToken)onFailure('点击「重试资源」开启播放');});}catch{onFailure('点击「重试资源」开启播放');}
  }
  return {deploy,handle,preload,stop,unlock,sprite:(id,action='idle')=>content.media[id]?.actions[action],
   setPaused(value){paused=value;if(value)stop();},setMuted(value){muted=value;if(value)stop();},setVolume(value){volume=Math.max(0,Math.min(1,Number(value)||0));if(current)current.volume=volume;},
   retry(){failed.clear();unlock();},destroy(){dead=true;stop();if(reusable)release(reusable);reusable=null;for(const entry of images.values())entry.cancel();images.clear();recent.clear();deployAt.clear();lastPick.clear();seAt.clear();},
   inspect:()=>({queued:queue.length,active:Number(!!current)+se.size,images:images.size,dead})};
 }
 const api={create};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WFBattleMedia=api;
})(typeof window==='undefined'?globalThis:window);
