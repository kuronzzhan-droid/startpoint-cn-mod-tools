/* Optional paid placement: no tracking, polling, script injection or impression writes. */
((root) => {
  'use strict';
  const cacheKey = 'wf-wiki-sponsor-v1', cacheMs = 1800000;
  function safeUrl(value, image = false) {
    if (typeof value !== 'string' || value.length > 2048 || /[\u0000-\u001f\u007f]/.test(value)) return null;
    value=value.trim();
    if (/[\s\\]/.test(value)) return null;
    if (image && /^\/?media\/[a-f0-9]{64}\.(png|jpe?g|webp)$/.test(value)) return '/' + value.replace(/^\//,'');
    try {
      const url = new URL(value), host = url.hostname.toLowerCase(), labels=host.split('.'), pathname=decodeURIComponent(url.pathname);
      if (url.protocol !== 'https:' || url.username || url.password || url.port || url.href.length>2048 || labels.length<2
        || labels.some(label=>!/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label)) || !/^[a-z]/.test(labels.at(-1))
        || /(?:^|\.)(localhost|local|localdomain|internal|intranet|lan|home|test|invalid|onion)$/.test(host)
        || /[\u0000-\u001f\u007f]/.test(pathname) || (image && !/\.(png|jpe?g|webp)$/i.test(pathname))) return null;
      return url.href;
    } catch {return null;}
  }
  function normalize(value) {
    if (!value || typeof value.enabled !== 'boolean') return null;
    const fields = {};
    for (const [key,limit] of [['title',60],['description',160]]) {
      if (typeof value[key] !== 'string') return null;
      fields[key] = value[key].trim().normalize('NFC');
      if ([...fields[key]].length > limit || /[\u0000-\u001f\u007f]/.test(fields[key])) return null;
    }
    if (typeof value.targetUrl !== 'string' || typeof value.imageUrl !== 'string') return null;
    const targetUrl = value.targetUrl ? safeUrl(value.targetUrl) : '', imageUrl = value.imageUrl ? safeUrl(value.imageUrl,true) : '';
    if (targetUrl === null || imageUrl === null || (value.enabled && (!fields.title || !targetUrl))) return null;
    return {enabled:value.enabled,...fields,targetUrl,imageUrl};
  }
  function createCard(document, input, {preview = false} = {}) {
    const value = normalize(input);
    if (!value || (!value.enabled && !preview) || !value.title || !value.targetUrl) return null;
    const el = (tag,cls,text) => {const node=document.createElement(tag); node.className=cls || ''; if(text) node.textContent=text; return node;};
    const card = el('article','wiki-sponsor-card'), label = el('small','wiki-sponsor-label','广告 · 赞助');
    const link = el(preview ? 'div' : 'a','wiki-sponsor-content');
    if (!preview) {link.href=value.targetUrl; link.target='_blank'; link.rel='sponsored noopener noreferrer';}
    if (value.imageUrl) {
      const media = el('div','wiki-sponsor-media'), image=el('img');
      image.alt=value.title; image.loading='lazy'; image.decoding='async'; image.referrerPolicy='no-referrer'; image.src=value.imageUrl;
      image.addEventListener('error',()=>media.remove()); media.append(image); link.append(media);
    }
    const copy = el('div','wiki-sponsor-copy'); copy.append(el('h2','',value.title));
    if (value.description) copy.append(el('p','',value.description));
    copy.append(el('span','wiki-sponsor-action',preview ? '广告预览' : '了解详情 ↗'));
    link.append(copy); card.append(label,link); return card;
  }
  function mount({document,host,footer,location,events,request,storage,Observer,now=Date.now}) {
    let loaded=false, pending=null, value=null, observer, nearFooter=false;
    const privatePage = () => /^#community\/(admin|accounts)(?:\/|$)/.test(location.hash);
    host.hidden=true;
    function paint() {
      host.replaceChildren(); host.hidden=true;
      if (privatePage()) return;
      const card=createCard(document,value);
      if (card) {host.append(card); host.hidden=false;}
    }
    function cached() {
      try {
        const raw=storage?.getItem(cacheKey); if (!raw || raw.length>10000) return null;
        const record=JSON.parse(raw), time=now();
        return Number.isSafeInteger(record.at) && record.at<=time && Math.floor(record.at/cacheMs)===Math.floor(time/cacheMs)
          ? normalize(record.value) : null;
      } catch {return null;}
    }
    function load() {
      if (privatePage() || !/^https?:$/.test(location.protocol)) return Promise.resolve();
      if (pending) return pending;
      if (loaded) return Promise.resolve();
      loaded=true; observer?.disconnect();
      pending=Promise.resolve().then(async()=>{
        value=cached();
        if (!value) {
          value=normalize(await request('/sponsorship'));
          if (value) {try {storage?.setItem(cacheKey,JSON.stringify({at:now(),value}));} catch { /* Storage is optional. */ }}
        }
        paint();
      }).catch(()=>{value=null;paint();}).finally(()=>{pending=null;});
      return pending;
    }
    if (Observer && footer) {
      observer=new Observer(entries=>{nearFooter=entries.some(entry=>entry.isIntersecting);if(nearFooter) load();},{rootMargin:'160px'});
      observer.observe(footer);
    } else load();
    events.addEventListener('hashchange',()=>{paint(); if (!loaded && (nearFooter || !observer)) load();});
    return {load};
  }
  const api = {safeUrl,normalize,createCard,mount};
  if (typeof module !== 'undefined') module.exports=api;
  if (!root?.document) return;
  root.WFSponsor=api;
  const host=root.document.getElementById('site-sponsor');
  if (!host || !root.WFCommunity?.client) return;
  let storage; try {storage=root.sessionStorage;} catch { /* Blocked storage keeps one request per document. */ }
  mount({document:root.document,host,footer:root.document.querySelector('.site-footer'),location:root.location,events:root,
    request:path=>root.WFCommunity.client.request(path),storage,Observer:root.IntersectionObserver});
})(typeof window === 'undefined' ? null : window);
