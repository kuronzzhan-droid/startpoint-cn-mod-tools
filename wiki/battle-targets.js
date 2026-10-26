((root)=>{
  'use strict';
  const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
  function select(s,origin,rule={}) {
    let pool=(rule.team==='ally'?s.units:s.enemies).filter(e=>e.hp>0&&distance(origin,e)<=(rule.range??100));
    if(rule.elements?.length)pool=pool.filter(e=>rule.elements.includes(s.content?.characters[e.characterId]?.element));
    if(Number.isFinite(rule.hpBelow))pool=pool.filter(e=>e.hp/e.maxHp<rule.hpBelow);
    if(rule.kind==='self')return pool.filter(e=>e.id===origin.id);
    if(rule.kind==='leader')return pool.filter(e=>e.characterId===s.squad[0]);
    pool.sort((a,b)=>(rule.preferBoss?Number(b.rank==='boss')-Number(a.rank==='boss'):0)
      ||(rule.kind==='lowestHp'?a.hp/a.maxHp-b.hp/b.maxHp:0)||distance(origin,a)-distance(origin,b)||a.id-b.id);
    return rule.kind==='all'?pool:pool.slice(0,1);
  }
  function origin(g,caster,target) {
    const point=g.center==='self'?caster:(target||caster),d=Math.max(.0001,distance(caster,target||caster));
    return {x:point.x+(g.offsetX||0),y:point.y+(g.offsetY||0),
      dx:g.direction==='target'?((target?.x??caster.x)-caster.x)/d:0,
      dy:g.direction==='target'?((target?.y??caster.y)-caster.y)/d:g.direction==='down'?1:-1};
  }
  function contains(g,o,p) {
    const x=p.x-o.x-(o.dx===undefined?(g.offsetX||0):0),y=p.y-o.y-(o.dx===undefined?(g.offsetY||0):0),d=Math.hypot(x,y),eps=1e-8;
    const dx=o.dx??0,dy=o.dy??(g.direction==='down'?1:-1),along=x*dx+y*dy,across=Math.abs(x*dy-y*dx);
    switch(g.kind) {
      case 'all':return true;
      case 'circle':return d<=(g.radius||0)+eps;
      case 'line':return along>=-eps&&along<=(g.length||0)+eps&&across<=(g.width||1)/2+eps;
      case 'rect':return along>=.5-eps&&along<=(g.length||0)+eps&&across<=(g.width||1)/2+eps;
      case 'fan':return d<=(g.radius||0)+eps&&(d<eps||along/d>=Math.cos((g.angle||90)*Math.PI/360)-eps);
      case 'cross':return (Math.abs(x)<=.5+eps&&Math.abs(y)<=(g.length||g.radius||1)+eps)||(Math.abs(y)<=.5+eps&&Math.abs(x)<=(g.length||g.radius||1)+eps);
      default:return d<=eps;
    }
  }
  const api={distance,select,origin,contains};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WFBattleTargets=api;
})(typeof window==='undefined'?globalThis:window);
