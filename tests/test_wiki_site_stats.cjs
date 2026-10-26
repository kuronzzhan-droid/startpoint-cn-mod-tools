const test=require('node:test');
const assert=require('node:assert/strict');
const {create,normalize,storageKey}=require('../wiki/site-stats.js');
const tick=()=>new Promise(setImmediate);
const epoch=Date.parse('2026-09-30T10:00:00.000Z');
const stats=(extra={})=>({totalVoters:9,ratingVoters:7,tierVoters:3,onlineVisitors:2,asOf:new Date(epoch).toISOString(),presenceWindowSeconds:1800,...extra});
function fixture({protocol='https:',hidden=false,request,config=async()=>({enabled:true}),storage,locks,clock={time:epoch}}={}) {
  let id=0;const timers=new Map(),calls=[],seen=[],events=new Map(),docEvents=new Map();
  const eventBus=map=>({addEventListener:(key,fn)=>map.set(key,fn),removeEventListener:(key)=>map.delete(key)});
  const document={visibilityState:hidden?'hidden':'visible',...eventBus(docEvents)};
  const api=create({client:{async config(){calls.push('config');return config();},async request(...args){calls.push(args);return request?request(...args):stats({asOf:new Date(clock.time).toISOString()});}},protocol,storage,locks,
    document,events:eventBus(events),now:()=>clock.time,schedule:(fn,ms)=>{timers.set(++id,{fn,ms});return id;},cancel:(key)=>timers.delete(key)});
  api.subscribe(value=>seen.push(value));
  return {api,calls,seen,timers,document,events,docEvents,time:()=>clock.time,advance(ms){clock.time+=ms;},
    hide(){document.visibilityState='hidden';docEvents.get('visibilitychange')?.();},
    show(){document.visibilityState='visible';docEvents.get('visibilitychange')?.();},
    runTimer(){const [key,value]=timers.entries().next().value;timers.delete(key);return value.fn();}};
}
function browserGroup(initial=null) {
  const clock={time:epoch},tabs=[],writes=[];let raw=initial,held=null,lockCalls=0;
  const locks={async request(_name,options,callback){
    lockCalls++;assert.deepEqual(options,{ifAvailable:true});
    if(held)return callback(null);
    const owner={};held=owner;
    try{return await callback(owner);}finally{if(held===owner)held=null;}
  }};
  const add=(options={})=>{
    let tab;
    const storage={getItem(key){assert.equal(key,storageKey);return raw;},setItem(key,value){
      assert.equal(key,storageKey);raw=value;writes.push(value);
      for(const other of tabs)if(other!==tab)queueMicrotask(()=>other.events.get('storage')?.({key}));
    }};
    tab=fixture({clock,storage,locks,...options});tabs.push(tab);return tab;
  };
  return {add,writes,clock,locks,lockCalls:()=>lockCalls,raw:()=>raw,
    setRaw(value){raw=value;for(const tab of tabs)tab.events.get('storage')?.({key:storageKey});},
    releaseCrashedLock(){held=null;}};
}
const sharedSnapshot=(extra={})=>({version:1,writtenAt:epoch,lastAttempt:epoch,retryAt:0,failures:0,errorCode:'',status:'ready',data:stats(),...extra});
test('one shared heartbeat initializes identity before presence and notifies multiple subscribers',async()=>{
  const x=fixture(),second=[];x.api.subscribe(v=>second.push(v));x.api.start();await tick();
  assert.deepEqual(x.calls,['config',['/presence',{},'POST']]);assert.equal(x.seen.at(-1).data.onlineVisitors,2);
  assert.equal(second.at(-1).data.ratingVoters,7);assert.equal(x.timers.size,1);assert.equal([...x.timers.values()][0].ms,1800000);
});
test('simultaneous refreshes share the pending request and only one timer',async()=>{
  let resolve;const x=fixture({request:()=>new Promise(done=>resolve=done)});x.api.start();await tick();
  const first=x.api.refresh(),second=x.api.refresh();assert.equal(first,second);assert.equal(x.calls.length,2);
  resolve(stats());await first;assert.equal(x.timers.size,1);
});
test('hidden pages stop polling; returning after the interval refreshes exactly once',async()=>{
  const x=fixture();x.api.start();await tick();x.hide();assert.equal(x.timers.size,0);
  x.advance(1800001);await x.api.refresh();assert.equal(x.calls.length,2);
  x.show();x.events.get('focus')();await tick();assert.equal(x.calls.length,4);assert.equal(x.timers.size,1);
});
test('background initial tabs never initialize identity or send presence until visible',async()=>{
  const x=fixture({hidden:true});x.api.start();await tick();assert.equal(x.calls.length,0);
  x.show();await tick();assert.equal(x.calls.length,2);
});
test('becoming hidden during identity setup skips presence',async()=>{
  let resolve;const x=fixture({config:()=>new Promise(done=>resolve=done)});x.api.start();await tick();x.hide();resolve({enabled:true});await tick();
  assert.deepEqual(x.calls,['config']);assert.equal(x.timers.size,0);
});
test('failures retain real last counts rather than showing invented zero and can recover',async()=>{
  let failure=false;const x=fixture({request:async()=>{if(failure)throw new Error('offline');return stats({asOf:new Date(x.time()).toISOString()});}});x.api.start();await tick();
  failure=true;x.advance(1800000);await x.runTimer();assert.equal(x.seen.at(-1).status,'error');assert.equal(x.seen.at(-1).data.tierVoters,3);
  failure=false;x.advance(1800000);await x.runTimer();assert.equal(x.seen.at(-1).status,'ready');
});
test('malformed initial data is unavailable, not a zero-player result',async()=>{
  const x=fixture({request:async()=>stats({ratingVoters:-1})});x.api.start();await tick();
  assert.equal(x.seen.at(-1).status,'error');assert.equal(x.seen.at(-1).data,null);
  for(const value of [stats({tierVoters:1.2}),stats({onlineVisitors:'7'}),stats({totalVoters:4}),stats({totalVoters:20}),stats({asOf:'bad'}),stats({presenceWindowSeconds:0})])assert.throws(()=>normalize(value));
});
test('offline files never poll and keep unavailable counts distinct from zero',async()=>{
  const x=fixture({protocol:'file:'});x.api.start();await tick();assert.equal(x.calls.length,0);assert.equal(x.seen.at(-1).status,'offline');assert.equal(x.seen.at(-1).data,null);
});
test('unsubscribe and stop release view subscriptions, timers and visibility listeners',async()=>{
  const x=fixture(),values=[];const off=x.api.subscribe(v=>values.push(v));x.api.start();await tick();off();x.advance(1800000);await x.runTimer();
  assert.equal(values.length,3);x.api.stop();assert.equal(x.timers.size,0);assert.equal(x.events.size,0);assert.equal(x.docEvents.size,0);
});
test('late responses after stop do not repaint or schedule new work',async()=>{
  let resolve;const x=fixture({request:()=>new Promise(done=>resolve=done)});x.api.start();await tick();x.api.stop();resolve(stats());await tick();
  assert.equal(x.seen.at(-1).data,null);assert.equal(x.timers.size,0);
});
test('focus storms within the interval do not send extra requests',async()=>{
  const x=fixture();x.api.start();await tick();for(let i=0;i<20;i++)x.events.get('focus')();await tick();
  assert.equal(x.calls.length,2);assert.equal(x.timers.size,1);
});

test('a slow successful response starts a full thirty-minute cooldown across tabs',async()=>{
  let resolve;const group=browserGroup(),a=group.add({request:()=>new Promise(done=>resolve=done)}),b=group.add();
  a.api.start();await tick();group.clock.time+=12000;
  resolve(stats({asOf:new Date(group.clock.time-6000).toISOString()}));await tick();
  b.api.start();await tick();
  assert.equal([...a.timers.values()][0].ms,1800000);
  assert.equal([...b.timers.values()][0].ms,1800000);
  group.clock.time+=1799999;await b.api.refresh();assert.deepEqual(b.calls,[]);
  group.clock.time++;await b.api.refresh();assert.equal(b.calls.length,2);
  a.api.stop();b.api.stop();
});

test('consecutive failures back off to four hours and a success restores thirty-minute polling',async()=>{
  let failure=true;const x=fixture({request:async()=>{if(failure)throw new Error('unavailable');return stats({asOf:new Date(x.time()).toISOString()});}});
  x.api.start();await tick();
  for(const delay of [1800000,3600000,7200000,14400000,14400000]){
    assert.equal([...x.timers.values()][0].ms,delay);x.advance(delay);await x.runTimer();
  }
  failure=false;x.advance(14400000);await x.runTimer();
  assert.equal(x.seen.at(-1).status,'ready');assert.equal([...x.timers.values()][0].ms,1800000);
  failure=true;x.advance(1800000);await x.runTimer();assert.equal([...x.timers.values()][0].ms,1800000);
});

test('server retryAfter survives focus, online, visibility, explicit refresh and restart attempts',async()=>{
  const x=fixture({request:async()=>{throw Object.assign(new Error('raw SQL detail must stay private'),{
    code:'database_quota_exceeded',retryAfter:300,data:{resetAt:'2026-10-01T00:00:00.000Z'}});}});
  x.api.start();await tick();const untilReset=14*3600000;assert.equal([...x.timers.values()][0].ms,untilReset);
  assert.equal(x.seen.at(-1).errorCode,'database_quota_exceeded');assert.equal(x.seen.at(-1).data,null);
  assert.equal(JSON.stringify(x.seen).includes('raw SQL'),false);
  x.advance(30000);
  for(let i=0;i<10;i++){x.events.get('focus')();x.events.get('online')();x.hide();x.show();await x.api.refresh();}
  x.api.stop();x.api.start();await tick();assert.equal(x.calls.length,2);assert.equal([...x.timers.values()][0].ms,untilReset-30000);
  x.advance(untilReset-30001);x.events.get('online')();await tick();assert.equal(x.calls.length,2);
  x.advance(1);x.events.get('focus')();await tick();assert.equal(x.calls.length,4);
});

test('retryAfter is bounded and invalid hints cannot disable backoff',async()=>{
  for(const [retryAfter,delay] of [[90,1800000],[999999,86400000],[-4,1800000],['bad',1800000],[Infinity,1800000]]){
    const x=fixture({config:async()=>{throw Object.assign(new Error('unavailable'),{retryAfter});}});
    x.api.start();await tick();assert.equal([...x.timers.values()][0].ms,delay);
    assert.equal(x.seen.at(-1).data,null);assert.equal(x.seen.at(-1).errorCode,'');x.api.stop();
  }
});

test('backoff starts when a slow failure finishes and quota errors preserve the last real count',async()=>{
  let reject;const y=fixture({request:()=>new Promise((resolve,no)=>reject=no)});y.api.start();await tick();
  y.advance(60000);reject(new Error('timeout'));await tick();assert.equal([...y.timers.values()][0].ms,1800000);
  const {createApi}=require('../wiki/community-client.js');
  let failed=false;const client=createApi(async url=>({ok:!failed,status:failed?503:200,json:async()=>failed?
    {error:'database_quota_exceeded',message:'raw database failure',retryAfter:300}:url.endsWith('/config')?{enabled:true}:stats()}),'https:');
  const bus={addEventListener(){},removeEventListener(){}};let delay,time=epoch;
  const api=create({client,protocol:'https:',document:{visibilityState:'visible',...bus},events:bus,now:()=>time,
    schedule:(fn,ms)=>{delay=ms;return 1;},cancel:()=>{}}),seen=[];
  api.subscribe(value=>seen.push(value));api.start();await tick();failed=true;time+=1800000;await api.refresh();
  assert.equal(seen.at(-1).data.onlineVisitors,2);assert.equal(seen.at(-1).errorCode,'database_quota_exceeded');
  assert.equal(delay,3600000);assert.equal(JSON.stringify(seen).includes('raw database'),false);api.stop();y.api.stop();
});

test('expired visitor cookies recover through fresh config, with at most one heartbeat retry',async()=>{
  const {createApi}=require('../wiki/community-client.js');
  let cookie=false,blocked=false,configs=0,presences=0;
  const client=createApi(async url=>{
    if(url.endsWith('/config')){configs++;cookie=!blocked;return {ok:true,json:async()=>({enabled:true})};}
    presences++;return cookie?{ok:true,json:async()=>stats({asOf:new Date(time).toISOString()})}:
      {ok:false,status:428,json:async()=>({error:'visitor_required'})};
  },'https:');
  const eventBus={addEventListener(){},removeEventListener(){}};let time=epoch;
  const api=create({client,protocol:'https:',document:{visibilityState:'visible',...eventBus},events:eventBus,
    now:()=>time,schedule:()=>1,cancel:()=>{}}),seen=[];
  api.subscribe(value=>seen.push(value));api.start();await tick();assert.equal(configs,1);assert.equal(seen.at(-1).status,'ready');
  cookie=false;time+=1800000;await api.refresh();assert.equal(configs,2);assert.equal(presences,3);assert.equal(seen.at(-1).status,'ready');
  cookie=false;blocked=true;time+=1800000;await api.refresh();assert.equal(configs,3);assert.equal(presences,5);
  assert.equal(seen.at(-1).status,'error');assert.equal(seen.at(-1).data.onlineVisitors,2);api.stop();
});

test('two visible tabs share one locked request and receive its result through storage',async()=>{
  let resolve;const group=browserGroup(),a=group.add({request:()=>new Promise(done=>resolve=done)}),b=group.add();
  a.api.start();b.api.start();await tick();
  assert.equal(a.calls.length+b.calls.length,2);assert.equal(group.lockCalls(),2);
  resolve(stats());await tick();
  for(const tab of [a,b]){
    assert.equal(tab.seen.at(-1).status,'ready');assert.equal(tab.seen.at(-1).data.onlineVisitors,2);
    assert.equal([...tab.timers.values()][0].ms,1800000);
  }
  group.clock.time+=1800000;
  // The follower can lead the next interval; the original tab still receives its result.
  await b.runTimer();await a.runTimer();await tick();
  assert.equal(a.calls.length+b.calls.length,4);assert.equal(a.seen.at(-1).data.asOf,new Date(group.clock.time).toISOString());
  a.api.stop();b.api.stop();
});

test('a newly opened visible tab uses a fresh shared snapshot without configuring identity',async()=>{
  const group=browserGroup(),a=group.add();a.api.start();await tick();
  const b=group.add();b.api.start();await tick();
  assert.deepEqual(b.calls,[]);assert.equal(b.seen.at(-1).status,'ready');assert.equal(b.seen.at(-1).data.totalVoters,9);
  assert.equal([...b.timers.values()][0].ms,1800000);a.api.stop();b.api.stop();
});

test('a follower takes over within thirty minutes after the previous owner closes or crashes',async()=>{
  let resolve;const group=browserGroup(),a=group.add({request:()=>new Promise(done=>resolve=done)}),b=group.add();
  a.api.start();b.api.start();await tick();a.api.stop();group.releaseCrashedLock();
  assert.equal(b.calls.length,0);group.clock.time+=1800000;await b.runTimer();await tick();
  assert.equal(b.calls.length,2);assert.equal(b.seen.at(-1).status,'ready');
  const raw=group.raw(),writes=group.writes.length;resolve(stats({onlineVisitors:99}));await tick();
  assert.equal(group.raw(),raw);assert.equal(group.writes.length,writes);assert.equal(b.seen.at(-1).data.onlineVisitors,2);b.api.stop();
});

test('shared quota failures preserve counts and cooldown across tabs, focus storms and owner shutdown',async()=>{
  const group=browserGroup(JSON.stringify(sharedSnapshot({lastAttempt:epoch-1800000}))),resetAt=new Date(epoch+7200000).toISOString();
  const a=group.add({request:async()=>{throw Object.assign(new Error('private SQL'),{code:'database_quota_exceeded',retryAfter:300,data:{resetAt}});}});
  a.api.start();await tick();const b=group.add();b.api.start();await tick();a.api.stop();
  assert.deepEqual(b.calls,[]);assert.equal(b.seen.at(-1).data.onlineVisitors,2);assert.equal(b.seen.at(-1).errorCode,'database_quota_exceeded');
  assert.equal([...b.timers.values()][0].ms,7200000);assert.equal(group.raw().includes('private SQL'),false);
  for(let i=0;i<10;i++){b.events.get('focus')();b.events.get('online')();await b.api.refresh();}
  assert.deepEqual(b.calls,[]);group.clock.time+=7200000;await b.runTimer();await tick();
  assert.equal(b.calls.length,2);assert.equal(b.seen.at(-1).status,'ready');b.api.stop();
});

test('expired saved counts do not discard a valid shared quota cooldown',async()=>{
  const group=browserGroup(JSON.stringify(sharedSnapshot({status:'error',errorCode:'database_quota_exceeded',retryAt:epoch+7200000,failures:1,
    data:stats({asOf:new Date(epoch-86400001).toISOString()})}))),x=group.add();
  x.api.start();await tick();assert.deepEqual(x.calls,[]);assert.equal(x.seen.at(-1).data,null);
  assert.equal(x.seen.at(-1).errorCode,'database_quota_exceeded');assert.equal([...x.timers.values()][0].ms,7200000);x.api.stop();
});

test('statistics-paused responses share the server cooldown without pretending it is quota exhaustion',async()=>{
  const group=browserGroup(),a=group.add({request:async()=>{throw Object.assign(new Error('paused'),{code:'statistics_paused',retryAfter:300});}});
  a.api.start();await tick();const b=group.add();b.api.start();await tick();
  assert.deepEqual(b.calls,[]);assert.equal(b.seen.at(-1).errorCode,'statistics_paused');assert.equal([...b.timers.values()][0].ms,1800000);
  a.api.stop();b.api.stop();
});

test('ordinary failure streaks follow the next leading tab instead of restarting backoff',async()=>{
  const group=browserGroup(),fail=async()=>{throw new Error('unavailable');},a=group.add({request:fail}),b=group.add({request:fail});
  a.api.start();b.api.start();await tick();assert.equal([...b.timers.values()][0].ms,1800000);
  a.hide();group.clock.time+=1800000;await b.runTimer();await tick();
  assert.equal([...b.timers.values()][0].ms,3600000);assert.equal(a.seen.at(-1).status,'error');
  a.show();assert.equal([...a.timers.values()][0].ms,3600000);
  assert.equal(a.calls.length+b.calls.length,4);a.api.stop();b.api.stop();
});

test('hidden followers consume shared results without sending or scheduling heartbeats',async()=>{
  const group=browserGroup(),a=group.add(),b=group.add({hidden:true});a.api.start();b.api.start();await tick();
  assert.deepEqual(b.calls,[]);assert.equal(b.timers.size,0);assert.equal(b.seen.at(-1).data.totalVoters,9);
  a.hide();group.clock.time+=1800000;b.show();await tick();
  assert.equal(b.calls.length,2);assert.equal(a.calls.length,2);assert.equal(a.timers.size,0);a.api.stop();b.api.stop();
});

test('corrupt, expired or future shared state cannot fake counts or prevent a legitimate refresh',async()=>{
  const bad=[null,'{bad','[]','x'.repeat(4097),JSON.stringify(sharedSnapshot({version:2})),
    JSON.stringify(sharedSnapshot({writtenAt:epoch+60000})),JSON.stringify(sharedSnapshot({writtenAt:epoch-86400001})),
    JSON.stringify(sharedSnapshot({retryAt:epoch+86400001})),JSON.stringify(sharedSnapshot({failures:99})),
    JSON.stringify(sharedSnapshot({data:stats({onlineVisitors:-1})})),JSON.stringify(sharedSnapshot({data:stats({asOf:new Date(epoch+3600000).toISOString()})}))];
  for(const raw of bad){
    const group=browserGroup(raw),x=group.add();x.api.start();await tick();
    assert.equal(x.calls.length,2);assert.equal(x.seen.at(-1).status,'ready');assert.equal(x.seen.at(-1).data.onlineVisitors,2);x.api.stop();
  }
});

test('a stale last-good snapshot is visibly stale rather than current and refreshes on schedule',async()=>{
  const group=browserGroup(JSON.stringify(sharedSnapshot({data:stats({asOf:new Date(epoch-1800001).toISOString()})}))),x=group.add();
  x.api.start();await tick();assert.deepEqual(x.calls,[]);
  assert.equal(x.seen.at(-1).status,'error');assert.equal(x.seen.at(-1).errorCode,'stale_stats');assert.equal(x.seen.at(-1).data.onlineVisitors,2);
  group.clock.time+=1800000;await x.runTimer();assert.equal(x.seen.at(-1).status,'ready');x.api.stop();
});

test('disabled storage or unavailable locks safely degrades without a rapid retry loop',async()=>{
  const broken={getItem(){throw new Error('blocked');},setItem(){throw new Error('blocked');}};
  for(const options of [{storage:broken},{storage:{getItem:()=>null,setItem(){throw new Error('full');}}},
    {storage:{getItem:()=>null,setItem(){}},locks:{request:async()=>{throw new Error('unsupported');}}}]){
    const x=fixture(options);x.api.start();await tick();assert.equal(x.calls.length,2);assert.equal(x.seen.at(-1).status,'ready');
    assert.equal([...x.timers.values()][0].ms,1800000);await x.api.refresh();assert.equal(x.calls.length,2);x.api.stop();
  }
  const group=browserGroup(),a=group.add({locks:undefined}),b=group.add({locks:undefined});
  a.api.start();b.api.start();await tick();assert.equal(a.calls.length+b.calls.length,2);a.api.stop();b.api.stop();
});

test('only public normalized counts and timing state are persisted, never extra API data',async()=>{
  const group=browserGroup(),x=group.add({request:async()=>({...stats(),visitorId:'secret-id',token:'secret-token',details:{email:'secret-email'}})});
  x.api.start();await tick();assert.equal(/secret|visitorId|token|email/.test(group.raw()),false);
  assert.equal(JSON.parse(group.raw()).data.totalVoters,9);x.api.stop();
});

test('stop before identity settles suppresses presence, shared writes and late callbacks',async()=>{
  let resolve;const group=browserGroup(),x=group.add({config:()=>new Promise(done=>resolve=done)});
  x.api.start();await tick();const writes=group.writes.length;x.api.stop();resolve({enabled:true});await tick();
  assert.deepEqual(x.calls,['config']);assert.equal(group.writes.length,writes);assert.equal(x.timers.size,0);
  group.setRaw(JSON.stringify(sharedSnapshot({data:stats({onlineVisitors:99})})));assert.equal(x.seen.at(-1).data,null);
  const y=fixture();y.api.subscribe(v=>{if(v.status==='loading')y.api.stop();});y.api.start();await tick();assert.deepEqual(y.calls,[]);
});

test('stopped generations cannot repaint after the same controller starts again',async()=>{
  let resolve;const x=fixture({request:()=>new Promise(done=>resolve=done)});x.api.start();await tick();x.api.stop();x.api.start();
  resolve(stats({onlineVisitors:99}));await tick();assert.equal(x.seen.at(-1).data,null);assert.equal(x.calls.length,2);
  assert.equal([...x.timers.values()][0].ms,1800000);x.api.stop();
});

test('normalization accepts legacy and thirty-minute presence windows and validates optional participation freshness',()=>{
  assert.equal(normalize(stats({presenceWindowSeconds:120})).presenceWindowSeconds,120);
  assert.equal(normalize(stats()).presenceWindowSeconds,1800);
  const value=stats({participationAsOf:new Date(epoch-60000).toISOString(),participationStale:true});
  assert.equal(normalize(value).participationAsOf,value.participationAsOf);assert.equal(normalize(value).participationStale,true);
  for(const patch of [{presenceWindowSeconds:180},{participationAsOf:'bad',participationStale:false},
    {participationAsOf:new Date(epoch).toISOString(),participationStale:'false'},
    {participationAsOf:new Date(epoch).toISOString()},{participationStale:true},{participationStale:false}])assert.throws(()=>normalize(stats(patch)));
});

test('site presence describes the actual returned window and stale participation separately',async()=>{
  const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
  for(const [seconds,participationStale] of [[120,false],[300,true],[1800,false]]){
    const host={children:[],dataset:{},append(...nodes){this.children.push(...nodes);},setAttribute(){}};
    const bus={addEventListener(){},removeEventListener(){}};
    const window={...bus,document:{...bus,visibilityState:'visible',getElementById:()=>host,createElement:()=>({textContent:''})},location:{protocol:'https:'},
      WFCommunity:{client:{config:async()=>({enabled:true}),request:async()=>stats({presenceWindowSeconds:seconds,
        ...(seconds===300?{participationStale,participationAsOf:new Date(epoch-60000).toISOString()}: {})})}}};
    class Clock extends Date{static now(){return epoch;}}
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../wiki/site-stats.js'),'utf8'),{window,Date:Clock,setTimeout:()=>1,clearTimeout(){}});await tick();
    assert.equal(host.dataset.status,'ready');assert.match(host.children[2].textContent,new RegExp(`最近 ${seconds/60} 分钟.*每 30 分钟更新`));
    assert.equal(host.children[2].textContent.includes('参与人数更新中'),participationStale);
    assert.match(host.title,new RegExp(`将在 ${seconds/60} 分钟内`));window.WFSiteStats.stop();
  }
});
