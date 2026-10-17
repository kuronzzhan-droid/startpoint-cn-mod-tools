const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const C = require('../wiki/community-client.js');
const source = fs.readFileSync(require.resolve('../wiki/community-auth.js'), 'utf8');
const owner = {id:'test-owner', email:'owner@example.test', role:'owner', enabled:true, mustChangePassword:false};
const response = (value, status = 200) => ({ok:status < 400, status, json:async () => value, headers:{get:() => null}});
const settle = () => new Promise(setImmediate);
function setup(handler, existingClient) {
  const calls = [], link = {attributes:{}, setAttribute(key, value) {this.attributes[key] = value;},
    set textContent(_) {throw new Error('Updating identity must preserve the account icon.');}};
  const client = existingClient || C.createApi(async (url, options) => {
    const path = url.slice('/api/community'.length); calls.push({path, method:options.method});
    return handler(path, options);
  }, 'http:');
  const window = {WFCommunity:{...C,client}};
  vm.runInNewContext(source, {window,document:{getElementById:(id) => id === 'site-admin' ? link : null}});
  return {calls,client,link,A:window.WFCommunityAuth};
}

test('the shared header keeps the home logo first and a separate management link immediately after it', () => {
  const html = fs.readFileSync(require.resolve('../wiki/index.html'),'utf8');
  const left = html.match(/<div class="masthead-left">([\s\S]*?)<\/div>/)?.[1];
  assert.ok(left);
  const links = [...left.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/g)];
  assert.equal(links.length,2);
  assert.match(links[0][1],/class="brand"/); assert.match(links[0][1],/href="#"/);
  assert.match(links[0][2],/class="brand-logo"/);
  assert.match(links[1][1],/id="site-admin"/); assert.match(links[1][1],/href="#community\/admin"/);
  assert.match(links[1][2],/<svg[^>]*aria-hidden="true"/);
  assert.doesNotMatch(links[1][2],/管理|邮箱|@/);
  assert.equal((html.match(/id="site-admin"/g) || []).length,1);
});

test('global header checks identity once, then follows server-confirmed login and logout without polling', async () => {
  let logged = false;
  const x = setup((path) => {
    if (path === '/config') return response({enabled:true,authMode:'password'});
    if (path === '/auth/me') return logged ? response(owner) : response({error:'admin_auth_required'},401);
    if (path === '/auth/login') {logged = true; return response(owner);}
    if (path === '/auth/logout') {logged = false; return response({ok:true});}
  });
  await settle(); assert.equal(x.link.title,'管理员登录');
  assert.deepEqual(x.calls.map(x => x.path),['/config','/auth/me']);
  x.A.header(x.link); x.A.header(x.link); await settle(); assert.equal(x.calls.length,2);
  await x.client.request('/auth/login',{email:owner.email,password:'synthetic-only'});
  assert.match(x.link.title,/已登录/); assert.ok(x.link.title.includes(owner.email));
  assert.equal(x.link.attributes['aria-label'],x.link.title); assert.equal(x.link.attributes['data-authenticated'],'true');
  await x.client.request('/auth/logout',{});
  assert.equal(x.link.title,'管理员登录'); assert.equal(x.link.attributes['data-authenticated'],'false');
  assert.equal(x.calls.filter(x => x.path.endsWith('/me')).length,1);
});

test('header reuses observed identity, retains full email for accessible labels, and never writes credentials into its cache', async () => {
  let calls = 0;
  const client = C.createApi(async () => {calls++; return response({...owner,password:'not-for-cache',token:'not-for-cache'});},'https:');
  await client.request('/auth/login',{password:'synthetic-only'});
  const x = setup(null,client); await settle();
  assert.equal(calls,1); assert.ok(x.link.attributes['aria-label'].includes(owner.email));
  assert.equal(x.link.title,`已登录：${owner.email} · 打开管理`);
  assert.deepEqual(Object.keys(client.identity()),['id','email','role','mustChangePassword']);
  assert.ok(Object.isFrozen(client.identity()));
});

test('Access login is observed once and offline/unconfigured sites keep the management link usable', async () => {
  const access = setup(path => path === '/config' ? response({enabled:true,authMode:'access'}) : response(owner));
  await settle(); assert.ok(access.link.title.includes(owner.email));
  assert.deepEqual(access.calls.map(x => x.path),['/config','/admin/me']);
  for (const config of [{enabled:false},{enabled:true,authMode:'password',needsSetup:true}]) {
    const x = setup(() => response(config)); await settle();
    assert.equal(x.link.title,'管理员登录'); assert.deepEqual(x.calls.map(x => x.path),['/config']);
  }
});

test('concurrent identity reads are shared but completed checks are never reused to authorize subsequent actions', async () => {
  let calls = 0, resolve;
  const client = C.createApi(async () => {calls++; return new Promise(done => {resolve = done;});},'https:');
  const a = client.request('/auth/me'), b = client.request('/auth/me');
  assert.equal(calls,1); resolve(response(owner)); await Promise.all([a,b]);
  const c = client.request('/auth/me'); assert.equal(calls,2);
  resolve(response({error:'admin_auth_required'},401)); await assert.rejects(c,{status:401});
  assert.equal(client.identity(),null);
});

test('delayed identity response cannot restore a logged-out identity or overwrite a new login', async () => {
  for (const mutation of ['/auth/logout','/auth/login']) {
    let resolve;
    const current = {...owner,id:'new-owner',email:'new@example.test'};
    const client = C.createApi(async url => url.endsWith('/auth/me') ? new Promise(done => {resolve = done;})
      : response(mutation.endsWith('/logout') ? {ok:true} : current),'https:');
    const stale = client.request('/auth/me');
    await client.request(mutation,{}); resolve(response(owner)); await stale;
    assert.equal(client.identity()?.email,mutation.endsWith('/logout') ? undefined : current.email);
  }
});

test('failed logout and role errors preserve identity; expired admin session clears it without confusing required password change', async () => {
  let status = 200, code = '';
  const client = C.createApi(async url => url.endsWith('/auth/login') ? response({...owner,mustChangePassword:true}) : response({error:code},status),'https:');
  await client.request('/auth/login',{}); assert.equal(client.identity().mustChangePassword,true);
  for (const [path,nextStatus,nextCode] of [['/auth/logout',503,'offline'],['/admin/accounts',403,'role_forbidden'],['/admin/me',403,'password_change_required']]) {
    status=nextStatus;code=nextCode;
    await assert.rejects(client.request(path,path.endsWith('/logout')?{}:undefined)); assert.equal(client.identity().email,owner.email);
  }
  status=401;code='admin_auth_required';await assert.rejects(client.request('/admin/teams'));assert.equal(client.identity(),null);
});
