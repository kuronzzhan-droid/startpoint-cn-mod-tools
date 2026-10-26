/* Original, locally hosted QQ cards load only when the visitor opens this dialog. */
(() => {
  'use strict';
  const tools = document.querySelector('.masthead-tools');
  if (!tools) return;
  const groups = [
    {name:'Reborn 二群', number:'1074605834', image:'reborn-group-2.jpg'},
    {name:'Reborn 一群', number:'753220321', image:'reborn-group-1.jpg'},
  ];
  const node = (tag, className, text) => {
    const element = document.createElement(tag); element.className = className;
    if (text) element.textContent = text;
    return element;
  };
  const trigger = node('button', 'reborn-join', 'Reborn 加群'); trigger.type = 'button';
  trigger.setAttribute('aria-label', 'Reborn 服加群'); trigger.setAttribute('aria-haspopup', 'dialog');
  // theme.js runs first, so the entry stays immediately to the right of the theme toggle.
  tools.append(trigger);
  let dialog, image, title, number, page, save, previous, next, status, index = 0, lock = null, opener;
  function lockScroll(button) {
    opener = button; lock = {body:document.body.style.overflow, root:document.documentElement.style.overflow};
    document.body.style.overflow = document.documentElement.style.overflow = 'hidden';
  }
  function release() {
    if (!lock) return;
    const old = lock; lock = null;
    document.body.style.overflow = old.body;
    document.documentElement.style.overflow = old.root;
    if (opener?.isConnected) opener.focus({preventScroll:true});
  }
  function close() {if (!dialog?.open) return; dialog.close(); release();}
  function render(value) {
    index = Math.max(0, Math.min(groups.length - 1, value));
    const group = groups[index];
    title.textContent = group.name; number.textContent = `群号 ${group.number}`;
    page.textContent = `${index + 1} / ${groups.length}`;
    previous.disabled = index === 0; next.disabled = index === groups.length - 1;
    status.textContent = '正在加载二维码…'; image.hidden = true;
    image.alt = `${group.name}加群二维码，群号 ${group.number}`;
    image.src = group.image; save.href = group.image;
    save.download = `${group.name}-${group.number}.jpg`;
    save.setAttribute('aria-label', `保存${group.name}二维码图片`);
  }
  function build() {
    dialog = node('dialog', 'reborn-dialog'); dialog.setAttribute('aria-labelledby', 'reborn-dialog-title');
    const header = node('header', 'reborn-dialog-header'), heading = node('div', '');
    title = node('h2', ''); title.id = 'reborn-dialog-title'; number = node('p', 'reborn-group-number');
    heading.append(title, number);
    const dismiss = node('button', 'reborn-close', '关闭 ×'); dismiss.type = 'button'; dismiss.autofocus = true;
    dismiss.setAttribute('aria-label', '关闭加群二维码'); dismiss.addEventListener('click', close);
    header.append(heading, dismiss);
    const frame = node('div', 'reborn-qr-frame'); image = node('img', 'reborn-qr-image');
    image.width = 1284; image.height = 2280; image.decoding = 'async';
    image.addEventListener('load', () => {image.hidden = false; status.textContent = '';});
    image.addEventListener('error', () => {image.hidden = true; status.textContent = '二维码暂未加载成功，可翻页重试或按群号搜索。';});
    frame.append(image); status = node('p', 'reborn-qr-status'); status.setAttribute('role', 'status');
    const footer = node('footer', 'reborn-dialog-footer');
    const pager = node('div', 'reborn-pager'); pager.setAttribute('aria-label', '二维码翻页');
    previous = node('button', '', '‹ 上一页'); next = node('button', '', '下一页 ›');
    previous.type = next.type = 'button';
    previous.addEventListener('click', () => render(index - 1)); next.addEventListener('click', () => render(index + 1));
    page = node('span', 'reborn-page'); page.setAttribute('aria-live', 'polite');
    pager.append(previous, page, next);
    save = node('a', 'reborn-save', '保存图片'); footer.append(pager, save);
    const help = node('p', 'reborn-help', '用 QQ 扫码加群 · 手机也可长按图片保存');
    dialog.append(header, frame, status, footer, help); document.body.append(dialog);
    dialog.addEventListener('cancel', event => {event.preventDefault(); close();});
    dialog.addEventListener('close', () => {if (!dialog.open && opener === trigger) release();});
    dialog.addEventListener('click', event => {
      if (event.target !== dialog) return;
      const rect = dialog.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) close();
    });
    dialog.addEventListener('keydown', event => {
      // Keep catalogue shortcuts and page navigation out of the modal.
      event.stopPropagation();
      if (event.key === 'ArrowLeft' && index > 0) {event.preventDefault(); render(index - 1);}
      if (event.key === 'ArrowRight' && index < groups.length - 1) {event.preventDefault(); render(index + 1);}
    });
  }
  trigger.addEventListener('click', () => {
    if (!dialog) build(); if (dialog.open) return;
    lockScroll(trigger);
    render(0); dialog.showModal();
  });
  window.addEventListener('hashchange', close);

  const publicUrl = 'https://wf-mod-wiki.pages.dev/';
  const share = node('button', 'wiki-share-trigger', '分享'); share.type = 'button';
  share.setAttribute('aria-label', '分享 Wiki 网站'); share.setAttribute('aria-haspopup', 'dialog'); tools.append(share);
  let shareDialog, poster, posterStatus, download, retryPoster;
  const posterUrl = 'wiki-share-poster.png';
  const closeShare = () => {if (!shareDialog?.open) return; shareDialog.close(); release();};
  function loadPoster() {
    if (poster.getAttribute('src') && retryPoster.hidden) return;
    retryPoster.hidden = true; posterStatus.textContent = '正在加载宣传图…';
    poster.src = posterUrl;
  }
  function buildShare() {
    shareDialog = node('dialog', 'reborn-dialog wiki-share-dialog'); shareDialog.setAttribute('aria-labelledby', 'wiki-share-title');
    const header = node('header', 'reborn-dialog-header'), heading = node('h2', '', '分享星见图鉴'); heading.id = 'wiki-share-title';
    const dismiss = node('button', 'reborn-close', '关闭 ×'); dismiss.type = 'button'; dismiss.autofocus = true;
    dismiss.setAttribute('aria-label', '关闭分享'); dismiss.addEventListener('click', closeShare); header.append(heading,dismiss);
    const row = node('div', 'wiki-share-url-row'), address = node('input', 'wiki-share-url');
    address.type = 'text'; address.value = publicUrl; address.readOnly = true; address.spellcheck = false;
    address.setAttribute('aria-label', 'Wiki 公网网站地址'); address.addEventListener('click', () => address.select());
    const copy = node('button', 'wiki-share-copy', '复制地址'); copy.type = 'button'; row.append(address,copy);
    const feedback = node('p', 'reborn-help'); feedback.setAttribute('role', 'status');
    copy.addEventListener('click', async () => {
      copy.disabled = true;
      try {await navigator.clipboard.writeText(publicUrl); feedback.textContent = '网站地址已复制。';}
      catch {address.focus(); address.select(); feedback.textContent = '请复制上方已选中的网站地址。';}
      finally {copy.disabled = false;}
    });
    poster = node('img', 'wiki-share-poster'); poster.alt = '星见图鉴角色宣传图，含 Wiki 网站二维码'; poster.hidden = true;
    poster.width = 960; poster.height = 1280; poster.decoding = 'async';
    poster.addEventListener('load', () => {poster.hidden = false; download.hidden = false; posterStatus.textContent = '';});
    poster.addEventListener('error', () => {
      poster.hidden = true; download.hidden = true; retryPoster.hidden = false;
      posterStatus.textContent = '宣传图暂未加载成功，仍可复制网站地址。';
    });
    posterStatus = node('p', 'reborn-qr-status'); posterStatus.setAttribute('role', 'status');
    download = node('a', 'reborn-save wiki-share-download', '保存二维码宣传图'); download.download = '星见图鉴-Wiki宣传图.png'; download.hidden = true;
    download.href = posterUrl;
    retryPoster = node('button', 'wiki-share-retry', '重新加载'); retryPoster.type = 'button'; retryPoster.hidden = true;
    retryPoster.addEventListener('click', loadPoster);
    shareDialog.append(header,row,feedback,poster,posterStatus,download,retryPoster,
      node('p','reborn-help','扫码打开 Wiki · 手机也可长按宣传图保存'));
    document.body.append(shareDialog);
    shareDialog.addEventListener('cancel', event => {event.preventDefault(); closeShare();});
    shareDialog.addEventListener('close', () => {if (!shareDialog.open && opener === share) release();});
    shareDialog.addEventListener('keydown', event => event.stopPropagation());
    shareDialog.addEventListener('click', event => {
      const rect = shareDialog.getBoundingClientRect();
      if (event.target === shareDialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) closeShare();
    });
  }
  share.addEventListener('click', () => {
    if (!shareDialog) buildShare(); if (shareDialog.open) return;
    lockScroll(share); shareDialog.showModal(); loadPoster();
  });
  window.addEventListener('hashchange', closeShare);
})();
