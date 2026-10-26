/* Load only rendered, public animation media when the preview tab is opened. */
(() => {
  'use strict';
  let pending;
  function load() {
    if (window.WF_PIXEL_PREVIEWS?.format === 1) return Promise.resolve(window.WF_PIXEL_PREVIEWS);
    if (pending) return pending;
    pending = new Promise((resolve, reject) => {
      const script = document.createElement('script'); script.src = 'data/pixel-previews.js'; script.async = true;
      const fail = () => {script.remove(); pending = null; reject(new Error('像素预览暂时无法载入，请重试。'));};
      script.onerror = fail;
      script.onload = () => {
        script.remove();
        if (window.WF_PIXEL_PREVIEWS?.format !== 1) {fail(); return;}
        resolve(window.WF_PIXEL_PREVIEWS);
      };
      document.head.append(script);
    });
    return pending;
  }
  function mediaUrl(value) {return typeof value === 'string' && /^media\/pixels\/[a-f0-9]{64}\.webp$/.test(value) ? value : '';}
  let activeStop;
  function stop() {activeStop?.(); activeStop = null;}
  window.addEventListener('hashchange', stop);
  document.addEventListener('visibilitychange', () => {if (document.hidden) stop();});
  async function mount(host, character, ui) {
    const {el} = ui;
    const status = el('p', 'panel-note', '正在载入像素预览…'); status.setAttribute('role', 'status'); host.append(status);
    try {
      const index = await load(); if (!host.isConnected) return;
      const entry = index.characters?.[character.id];
      const actions = (entry?.actions || []).filter((item) => mediaUrl(item.url) && mediaUrl(item.poster?.url));
      if (!entry || !actions.length) {status.textContent = '当前资料尚未收录这位角色的像素动作。'; return;}
      status.remove();
      const stage = el('div', 'pixel-preview-stage');
      const image = el('img', 'pixel-preview-image'); image.decoding = 'async'; image.draggable = false;
      const state = el('p', 'pixel-preview-status'); state.setAttribute('role', 'status');
      const toolbar = el('div', 'pixel-preview-tools'); toolbar.setAttribute('role', 'group'); toolbar.setAttribute('aria-label', '像素动作');
      const play = el('button', 'primary-button', '播放动作'); play.type = 'button';
      const reset = el('button', 'secondary-button', '停止'); reset.type = 'button'; reset.disabled = true;
      const controls = el('div', 'pixel-preview-playback'); controls.append(play, reset);
      let chosen = 0, playing = false;
      const buttons = [];
      function showStatic() {
        playing = false; const action = actions[chosen], poster = action.poster;
        image.src = mediaUrl(poster?.url); image.alt = `${character.name} · ${action.label} · 静态预览`;
        state.textContent = `${action.label} · 静态预览`; play.disabled = !action.animated; reset.disabled = true;
        if (activeStop === showStatic) activeStop = null;
      }
      function select(i) {
        stop(); chosen = i;
        const action = actions[i];
        image.style.setProperty('--pixel-width', `${Math.max(64, Math.min(448, Number(action.width) * 3 || 192))}px`);
        buttons.forEach((button, n) => button.setAttribute('aria-pressed', String(i === n)));
        showStatic();
      }
      actions.forEach((action, i) => {
        const button = el('button', '', action.label); button.type = 'button';
        button.addEventListener('click', () => select(i)); toolbar.append(button); buttons.push(button);
      });
      play.addEventListener('click', () => {
        if (playing) return; stop(); const action = actions[chosen];
        image.src = mediaUrl(action.url); image.alt = `${character.name} · ${action.label} · 动画`;
        playing = true; activeStop = showStatic; play.disabled = true; reset.disabled = false;
        state.textContent = `${action.label} · 播放中`;
      });
      reset.addEventListener('click', showStatic);
      image.addEventListener('error', () => {
        playing = false; reset.disabled = true; play.disabled = !actions[chosen].animated;
        if (activeStop === showStatic) activeStop = null;
        state.textContent = '此动作图片加载失败，请重新选择或重试。';
      });
      stage.append(image); host.append(toolbar, stage, controls, state);
      host.append(el('p', 'panel-note', entry.note || '预览为角色自身的像素动作；技能准备与特殊动作不等于完整技能战斗演示，不含战斗场景、弹道及命中效果。'));
      (entry.unavailable || []).forEach((item) => host.append(el('p', 'panel-note', `${item.label}：${item.reason}`)));
      select(0);
    } catch (error) {
      if (!host.isConnected) return;
      status.textContent = error.message;
      const retry = el('button', 'secondary-button', '重新加载像素预览'); retry.type = 'button';
      retry.addEventListener('click', () => {host.replaceChildren(); mount(host, character, ui);}); host.append(retry);
    }
  }
  window.WFPixelPreviews = {mount, stop};
})();
