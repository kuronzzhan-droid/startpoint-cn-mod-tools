const character = (id, role='melee') => ({id,name:id,title:'测试',theme:'通常版',aliases:[],element:'火',role,
  stats:{hp:900,basicAmount:60,skillPower:60,interval:1,range:1.1,deployCost:20},
  skill:{name:'测试技',description:'测试',cost:15,cooldown:20,phases:[{offset:0,
    selector:{team:'enemy',kind:'nearest',range:3},geometry:{kind:'single',center:'target'},
    effects:[{type:'damage',amount:300}]}]}});
const content = () => ({schema:1,characters:Object.fromEntries(Array.from({length:6},(_,i)=>['c'+i,character('c'+i)])),
  stages:[{id:'fire',name:'火',bossId:'c0',theme:'fire',difficulty:1}],endless:{hpBase:2000,attackBase:70,vanguardHp:450,vanguardAttack:30},media:{}});
const options = () => {const c=content();return {content:c,squad:Object.keys(c.characters),mode:'campaign',stageId:'fire'};};
const enemy = (id=100,x=2.5,y=3.5,hp=10000) => ({id,themeId:'fire',rank:'vanguard',characterId:'c0',x,y,hp,maxHp:hp,attack:35,nextActionTick:999999,speed:0,range:1.1,interval:1.5,siege:false,statuses:[]});
module.exports={character,content,options,enemy};
