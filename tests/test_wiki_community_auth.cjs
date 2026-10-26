const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const base = require('../wiki/community-client.js');
class Node {
  constructor(tag, className = '', text = '') {Object.assign(this,{tag,className,ownText:String(text || ''),children:[],events:{},attributes:{},value:'',disabled:false,hidden:false});}
  append(...nodes) {for (const node of nodes) {node.parent = this; this.children.push(node);}}
  replaceChildren(...nodes) {this.children.forEach((node) => {node.parent = null;}); this.children = []; this.ownText = ''; this.append(...nodes);}
  setAttribute(key, value) {this.attributes[key] = value;}
  addEventListener(name, handler) {this.events[name] = handler;}
  focus() {this.focused = true;}
  get isConnected() {return this.root || Boolean(this.parent?.isConnected);}
  get childElementCount() {return this.children.length;}
  get textContent() {return this.ownText + this.children.map((node) => node.textContent).join('');}
  set textContent(value) {this.replaceChildren(); this.ownText = String(value);}
  all(match) {return this.children.flatMap((node) => [...(match(node) ? [node] : []), ...node.all(match)]);}
  async fire(name) {if (!this.disabled) return this.events[name]?.({preventDefault(){}});}
}
const el = (tag, cls, text) => new Node(tag, cls, text);
const find = (host, label) => host.all((node) => node.attributes['aria-label'] === label)[0];
const button = (host, label) => host.all((node) => node.tag === 'button' && node.textContent === label)[0];
const form = (host) => host.all((node) => node.tag === 'form')[0];
const secret = 'Test!123'; // Synthetic 8-character boundary; never an actual account password.
const owner = {id:'owner-1',email:'owner@example.test',role:'owner',enabled:true,revision:1,mustChangePassword:false};
const editor = {id:'editor-1',email:'editor@example.test',role:'editor',enabled:true,revision:2,mustChangePassword:false};
const deputy = {...editor,id:'deputy-1',email:'deputy@example.test',role:'deputy'};
const config = {enabled:true,authMode:'password',needsSetup:false,development:true};
function setup(handler) {
  const calls = [], challenges = [], listeners = new Map();
  const client = {request:async (...args) => {calls.push(args); return handler(...args);}};
  const window = {location:{protocol:'http:',hostname:'127.0.0.1'},fetch:async () => {},
    addEventListener:(name, fn) => listeners.set(name, fn), removeEventListener:(name, fn) => {if (listeners.get(name) === fn) listeners.delete(name);},
    WFWikiData:{loadEquipment:async () => []}, WFCommunity:{...base,client}};
  window.WFCommunity.challenge = (_host, _config, action, _ui, change) => {
    const value = {action,token:'',destroyed:false,take(){const token = this.token; this.token = ''; change(false); return token;},
      reset(){this.token = ''; change(false);},destroy(){this.destroyed = true;},ready(){this.token = 'verification-token'; change(true);}};
    challenges.push(value); return value;
  };
  for (const file of ['community-auth.js','community-accounts.js','community-admin.js']) {
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../wiki', file),'utf8'), {window,AbortController,URLSearchParams,setTimeout,clearTimeout});
  }
  const host = el('main'); host.root = true;
  return {window,host,calls,challenges,listeners,ui:{el},A:window.WFCommunityAuth,
    admin:() => window.renderWikiCommunityAdmin(host,{characters:[],equipment:[]},{el})};
}
function fail(code, status = 401, message = 'failure') {throw Object.assign(new Error(message), {code,status});}
test('verification service failures have a specific safe login message', () => {
  const x = setup();
  assert.match(x.A.message({code:'challenge_unavailable', status:503}), /验证服务暂时不可用/);
  assert.match(x.A.message({code:'challenge_failed', status:403}), /重新验证/);
});
test('password guest gets a real login form and verification before any credential request', async () => {
  let done = 0;
  const x = setup((url) => {assert.equal(url, '/auth/me'); fail('admin_auth_required');});
  assert.equal(await x.A.ensure(x.host, config, x.ui, () => done++), null);
  assert.equal(find(x.host, '登录邮箱').value, ''); assert.equal(find(x.host, '登录密码').type, 'password');
  assert.equal(button(x.host, '登录').disabled, true); assert.equal(x.challenges[0].action, 'admin_login');
  await form(x.host).fire('submit'); assert.equal(x.calls.length, 1); assert.equal(done, 0);
});
test('failed login never claims success or echoes a secret and clears password after submission', async () => {
  let done = 0;
  const x = setup((url) => url === '/auth/me' ? fail('admin_auth_required') : fail('invalid_credentials',401,secret));
  await x.A.ensure(x.host, config, x.ui, () => done++);
  find(x.host, '登录邮箱').value = 'editor@example.test'; find(x.host, '登录密码').value = secret;
  x.challenges[0].ready(); await form(x.host).fire('submit');
  assert.equal(x.calls[1][0], '/auth/login'); assert.equal(x.calls[1][1].turnstileToken, 'verification-token');
  assert.equal(find(x.host, '登录密码').value, ''); assert.equal(find(x.host, '登录邮箱').value, 'editor@example.test');
  assert.match(x.host.textContent, /邮箱或密码不正确/); assert.doesNotMatch(x.host.textContent, new RegExp(secret));
  assert.equal(button(x.host, '登录').disabled, true); assert.equal(done, 0);
});
test('successful login awaits the server then asks the caller to recheck identity', async () => {
  let done = 0, release;
  const x = setup((url) => url === '/auth/me' ? fail('admin_auth_required') : new Promise((resolve) => {release = resolve;}));
  await x.A.ensure(x.host, config, x.ui, () => done++);
  find(x.host, '登录邮箱').value = editor.email; find(x.host, '登录密码').value = secret; x.challenges[0].ready();
  const pending = form(x.host).fire('submit'); assert.equal(done, 0); release({ok:true}); await pending;
  assert.equal(done, 1); assert.equal(find(x.host, '登录密码').value, ''); assert.equal(x.challenges[0].destroyed, true);
});
test('bootstrap has no preset email or password and is unavailable without server configuration', async () => {
  const x = setup(() => {throw new Error('no request expected');});
  await x.A.ensure(x.host, {...config,needsSetup:true,bootstrapAvailable:false}, x.ui, () => {});
  assert.match(x.host.textContent, /初始化尚未配置/); assert.equal(x.host.all((node) => node.tag === 'input').length, 0);
  await x.A.ensure(x.host, {...config,needsSetup:true,bootstrapAvailable:true}, x.ui, () => {});
  for (const input of x.host.all((node) => node.tag === 'input')) assert.equal(input.value, '');
  assert.equal(find(x.host, '初始化密钥'), undefined); assert.equal(x.challenges.length, 0);
});
test('public bootstrap requires setup key while mismatched password makes no request', async () => {
  let done = 0;
  const x = setup((url) => {assert.equal(url, '/auth/bootstrap'); return {ok:true};}); x.window.location.hostname = 'wiki.example';
  await x.A.ensure(x.host, {...config,needsSetup:true,bootstrapAvailable:true}, x.ui, () => done++);
  assert.ok(find(x.host, '初始化密钥'));
  find(x.host, '站长密码').value = secret; find(x.host, '确认站长密码').value = `${secret}-different`;
  await form(x.host).fire('submit'); assert.equal(x.calls.length, 0); assert.match(x.host.textContent, /不一致/);
  find(x.host, '登录邮箱').value = owner.email; find(x.host, '站长密码').value = secret; find(x.host, '确认站长密码').value = secret;
  find(x.host, '初始化密钥').value = 'configured-private-setup-key'; await form(x.host).fire('submit');
  assert.equal(done, 1); assert.equal(x.calls[0][1].bootstrapToken, 'configured-private-setup-key');
  assert.equal(find(x.host, '初始化密钥').value, '');
});
test('temporary-password editor must change password before any administrator team request', async () => {
  const x = setup((url) => url === '/config' ? config : url === '/auth/me' ? {...editor,mustChangePassword:true} : fail('unexpected',500));
  await x.admin(); assert.match(x.host.textContent, /首次登录：修改临时密码/);
  assert.equal(button(x.host, '管理员账号'), undefined); assert.equal(x.calls.some(([url]) => url.startsWith('/admin/teams')), false);
  assert.equal(x.host.all((node) => node.tag === 'a' && node.href === '#team')[0].hidden, true);
});
test('password change keeps restricted state on server failure and clears all credential fields', async () => {
  let done = 0;
  const x = setup(() => fail('incorrect_password',400)); x.A.password(x.host, {...editor,mustChangePassword:true}, x.ui, () => done++);
  find(x.host, '当前密码').value = secret; find(x.host, '新密码').value = `${secret}-new`; find(x.host, '确认新密码').value = `${secret}-new`;
  await form(x.host).fire('submit'); assert.equal(done, 0); assert.match(x.host.textContent, /当前密码不正确/);
  assert.equal(x.host.all((node) => node.type === 'password').some((node) => node.value), false);
});
test('owner and deputy have accounts entry while an editor only has personal password and logout controls', async () => {
  for (const identity of [owner, deputy, editor]) {
    const x = setup((url) => url === '/config' ? config : url === '/auth/me' ? identity : {items:[]});
    await x.admin(); assert.equal(Boolean(button(x.host, '管理员账号')), identity.role !== 'editor');
    assert.ok(button(x.host, '修改密码')); assert.ok(button(x.host, '退出登录')); assert.match(x.host.textContent, /本机账号/);
    assert.doesNotMatch(x.host.textContent, /本机测试身份/);
  }
});
test('logout only clears administrator content after server confirms invalidation', async () => {
  let logged = true, reject = true;
  const x = setup((url) => {
    if (url === '/config') return config;
    if (url === '/auth/me') return logged ? owner : fail('admin_auth_required');
    if (url === '/auth/logout') {if (reject) fail('offline',503); logged = false; return {ok:true};}
    return {items:[]};
  });
  await x.admin(); await button(x.host, '退出登录').fire('click'); assert.ok(button(x.host, '管理员账号'));
  reject = false; await button(x.host, '退出登录').fire('click');
  assert.ok(button(x.host, '登录')); assert.equal(button(x.host, '管理员账号'), undefined);
});

test('declined account actions never log out, replace settings, or refresh the edited page',async()=>{
  let refreshed=0,checked=0;const x=setup(()=>({ok:true}));
  x.A.controls(x.host,owner,x.ui,()=>{refreshed++;},{beforeAction:async()=>{checked++;return false;}});
  for(const label of ['修改密码','退出登录','管理员账号'])await button(x.host,label).fire('click');
  assert.equal(checked,3);assert.equal(x.calls.length,0);assert.equal(refreshed,0);assert.equal(form(x.host),undefined);
});

test('password form checks newly edited drafts again before submitting, cancelling or logging out',async()=>{
  let allowed=true,done=0;const x=setup(()=>({ok:true}));
  x.A.controls(x.host,owner,x.ui,()=>{done++;},{beforeAction:async()=>allowed});await button(x.host,'修改密码').fire('click');
  find(x.host,'当前密码').value=secret;find(x.host,'新密码').value=`${secret}-new`;find(x.host,'确认新密码').value=`${secret}-new`;
  allowed=false;await form(x.host).fire('submit');await button(x.host,'取消修改').fire('click');
  const nestedLogout=form(x.host).all(n=>n.tag==='button'&&n.textContent==='退出登录')[0];await nestedLogout.fire('click');
  assert.equal(x.calls.length,0);assert.equal(done,0);assert.ok(form(x.host));
});

test('account request busy state lasts until the response and ends before refreshing the page',async()=>{
  let finish;const state=[],x=setup(()=>new Promise(resolve=>{finish=resolve;}));
  x.A.controls(x.host,owner,x.ui,()=>{state.push('refresh');},{onBusyChange:value=>state.push(value)});
  const pending=button(x.host,'退出登录').fire('click');await new Promise(setImmediate);assert.deepEqual(state,[true]);
  finish({ok:true});await pending;assert.deepEqual(state,[true,false,'refresh']);
});
test('owner account creation uses server returned identity and clears temporary password', async () => {
  let created = false;
  const x = setup((url, body, method) => {
    if (method === 'POST') {assert.equal(url, '/admin/users'); assert.equal(body.password, secret); created = true; return editor;}
    return {items:created ? [owner,editor] : [owner]};
  });
  await x.window.WFCommunityAccounts.render(x.host, x.ui, owner);
  find(x.host, '新管理员邮箱').value = editor.email; find(x.host, '临时密码').value = secret;
  await form(x.host).fire('submit'); assert.match(x.host.textContent, /管理员已创建/); assert.match(x.host.textContent, /editor@example.test/);
  assert.equal(find(x.host, '临时密码').value, ''); assert.equal(x.calls[1][1].role, 'editor');
});
test('account error does not claim creation and never reflects returned password text', async () => {
  const x = setup((_url, _body, method) => method === 'POST' ? fail('duplicate_email',409,secret) : {items:[owner]});
  await x.window.WFCommunityAccounts.render(x.host, x.ui, owner);
  find(x.host, '新管理员邮箱').value = editor.email; find(x.host, '临时密码').value = secret;
  await form(x.host).fire('submit'); assert.match(x.host.textContent, /该邮箱已经存在/);
  assert.doesNotMatch(x.host.textContent, /管理员已创建/); assert.doesNotMatch(x.host.textContent, new RegExp(secret));
  assert.equal(find(x.host, '临时密码').value, '');
});
test('enable state is not changed optimistically and PATCH supplies original revision', async () => {
  const x = setup((_url, _body, method) => method === 'PATCH' ? fail('edit_conflict',409) : {items:[owner,editor]});
  await x.window.WFCommunityAccounts.render(x.host, x.ui, owner); await button(x.host, '停用账号').fire('click');
  assert.equal(x.calls[1][0], '/admin/users/editor-1'); assert.equal(x.calls[1][1].expectedRevision, 2); assert.equal(x.calls[1][1].enabled, false);
  assert.ok(button(x.host, '停用账号')); assert.equal(button(x.host, '启用账号'), undefined); assert.match(x.host.textContent, /请刷新后再修改/);
  assert.equal(x.host.all((node) => node.tag === 'button' && node.textContent === '停用账号').length, 1);
});
test('password reset sends revision, does not publish plaintext, and needs a newer server revision', async () => {
  const x = setup((_url, _body, method) => method === 'PATCH' ? {...editor,revision:3,mustChangePassword:true} : {items:[editor]});
  await x.window.WFCommunityAccounts.render(x.host, x.ui, owner); await button(x.host, '重置临时密码').fire('click');
  find(x.host, `新临时密码：${editor.email}`).value = secret;
  const reset = x.host.all((node) => node.className === 'community-account-reset')[0]; await reset.fire('submit');
  assert.equal(x.calls[1][1].password, secret); assert.equal(x.calls[1][1].expectedRevision, 2);
  assert.match(x.host.textContent, /临时密码已重置/); assert.doesNotMatch(x.host.textContent, new RegExp(secret));
});
test('navigation clears an unfinished password form and disposes verification', async () => {
  const x = setup(() => fail('admin_auth_required'));
  await x.A.ensure(x.host, config, x.ui, () => {}); find(x.host, '登录密码').value = secret;
  x.listeners.get('wf-page-leave')(); assert.equal(find(x.host, '登录密码').value, ''); assert.equal(x.challenges[0].destroyed, true);
  assert.equal(x.listeners.has('wf-page-leave'),false);
});

test('rejected hash navigation leaves a mounted password form usable for submission',async()=>{
  let done=0;const x=setup(()=>({ok:true}));x.A.password(x.host,editor,x.ui,()=>{done++;});
  find(x.host,'当前密码').value=secret;find(x.host,'新密码').value=`${secret}-new`;find(x.host,'确认新密码').value=`${secret}-new`;
  x.listeners.get('hashchange')?.();assert.equal(find(x.host,'当前密码').value,secret);
  await form(x.host).fire('submit');assert.equal(x.calls[0][0],'/auth/password');assert.equal(done,1);
});

test('rejected navigation during a failed password request leaves retry available',async()=>{
  let reject,attempts=0;const x=setup(()=>++attempts===1?new Promise((_resolve,fail)=>{reject=fail;}):({ok:true}));
  x.A.password(x.host,editor,x.ui,()=>{});
  const fill=()=>{find(x.host,'当前密码').value=secret;find(x.host,'新密码').value=`${secret}-new`;find(x.host,'确认新密码').value=`${secret}-new`;};
  fill();const pending=form(x.host).fire('submit');await new Promise(setImmediate);x.listeners.get('hashchange')?.();
  reject(new Error('offline'));await pending;assert.equal(button(x.host,'保存新密码').disabled,false);
  fill();await form(x.host).fire('submit');assert.equal(x.calls.length,2);
});

test('account secrets survive rejected hash navigation and clear only on accepted page departure',async()=>{
  const x=setup(()=>({items:[editor]}));await x.window.WFCommunityAccounts.render(x.host,x.ui,owner);
  await button(x.host,'重置临时密码').fire('click');
  find(x.host,'临时密码').value=secret;find(x.host,`新临时密码：${editor.email}`).value=`${secret}-reset`;
  x.listeners.get('hashchange')?.();assert.equal(find(x.host,'临时密码').value,secret);
  assert.equal(find(x.host,`新临时密码：${editor.email}`).value,`${secret}-reset`);
  x.listeners.get('wf-page-leave')();assert.equal(find(x.host,'临时密码').value,'');
  assert.equal(find(x.host,`新临时密码：${editor.email}`).value,'');assert.equal(x.listeners.has('wf-page-leave'),false);
});
test('deputy cannot manipulate owner or deputy accounts and can only create ordinary editors', async () => {
  const x = setup((_url, body, method) => method === 'POST' ? {...editor,email:body.email} : {items:[owner,deputy,editor],deputySuggestion:{email:'private@example.test'}});
  await x.window.WFCommunityAccounts.render(x.host, x.ui, deputy);
  assert.equal(find(x.host, '账号权限'), undefined); assert.equal(button(x.host, '添加预设副站长').hidden, true);
  assert.equal(x.host.all((node) => node.tag === 'button' && node.textContent === '停用账号').length, 1);
  assert.equal(x.host.all((node) => node.tag === 'button' && node.textContent === '重置临时密码').length, 1);
  find(x.host, '新管理员邮箱').value = 'another@example.test'; find(x.host, '临时密码').value = secret;
  await form(x.host).fire('submit'); assert.equal(x.calls[1][1].role, 'editor');
});
test('suggested deputy is private server data and requires a password and explicit creation', async () => {
  const x = setup(() => ({items:[owner],deputySuggestion:{email:'suggested@example.test'}}));
  await x.window.WFCommunityAccounts.render(x.host, x.ui, owner);
  assert.equal(find(x.host, '新管理员邮箱').value, ''); assert.equal(find(x.host, '账号权限').value, 'editor');
  await button(x.host, '添加预设副站长').fire('click');
  assert.equal(find(x.host, '新管理员邮箱').value, 'suggested@example.test'); assert.equal(find(x.host, '账号权限').value, 'deputy');
  assert.equal(find(x.host, '临时密码').value, ''); assert.equal(find(x.host, '临时密码').focused, true); assert.equal(x.calls.length, 1);
});
test('password forms use 8–128 boundaries and reject shorter or longer values before requests', async () => {
  const x = setup(() => ({ok:true}));
  await x.A.ensure(x.host, {...config,needsSetup:true,bootstrapAvailable:true}, x.ui, () => {});
  const input = find(x.host, '站长密码'); assert.equal(input.minLength,8); assert.equal(input.maxLength,128);
  for (const length of [7,129]) {
    input.value = 'x'.repeat(length); find(x.host, '确认站长密码').value = input.value;
    await form(x.host).fire('submit'); assert.equal(x.calls.length,0); assert.match(x.host.textContent,/8–128/);
  }
  input.value = 'x'.repeat(128); find(x.host, '确认站长密码').value = input.value;
  await form(x.host).fire('submit'); assert.equal(x.calls.length,1); assert.equal(x.calls[0][1].password.length,128);
});
