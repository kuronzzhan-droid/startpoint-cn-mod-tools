/* One native modal viewer shared by every character portrait. */
(() => {
  'use strict';
  const node = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text) element.textContent = text;
    return element;
  };
  let dialog, viewport, canvas, image, title, status, zoomOut, zoomIn, fit, scaleLabel;
  let zoom = 1, opener = null, locked = null, drag = null, dragged = false;
  const bodyProperties = ['position', 'top', 'left', 'width', 'overflow'];

  function release(restoreFocus = true) {
    if (!locked) return;
    const previous = locked; locked = null;
    bodyProperties.forEach((key) => {document.body.style[key] = previous.styles[key];});
    document.documentElement.style.overflow = previous.overflow;
    window.scrollTo({left: previous.x, top: previous.y, behavior: 'instant'});
    if (drag && viewport.hasPointerCapture(drag.id)) viewport.releasePointerCapture(drag.id);
    drag = null; dragged = false; viewport.classList.remove('is-panning');
    image.removeAttribute('src');
    if (restoreFocus && opener?.isConnected) opener.focus({preventScroll: true});
    opener = null;
  }
  function close(restoreFocus = true) {
    if (!dialog?.open) return;
    dialog.close();
    release(restoreFocus);
  }
  function resize(reset = false) {
    if (!dialog?.open) return;
    const ready = image.naturalWidth > 0 && !image.hidden;
    zoomOut.disabled = !ready || zoom <= 1;
    zoomIn.disabled = !ready || zoom >= 4;
    fit.disabled = !ready;
    scaleLabel.textContent = `${Math.round(zoom * 100)}%`;
    if (!ready) return;
    const width = viewport.clientWidth, height = viewport.clientHeight;
    const centerX = (viewport.scrollLeft + width / 2) / Math.max(width, canvas.offsetWidth);
    const centerY = (viewport.scrollTop + height / 2) / Math.max(height, canvas.offsetHeight);
    const fitScale = Math.min(width / image.naturalWidth, height / image.naturalHeight);
    const imageWidth = Math.max(1, Math.round(image.naturalWidth * fitScale * zoom));
    const imageHeight = Math.max(1, Math.round(image.naturalHeight * fitScale * zoom));
    image.style.width = `${imageWidth}px`; image.style.height = `${imageHeight}px`;
    canvas.style.width = `${Math.max(width, imageWidth)}px`;
    canvas.style.height = `${Math.max(height, imageHeight)}px`;
    viewport.scrollLeft = Math.max(0, (reset ? .5 : centerX) * canvas.offsetWidth - width / 2);
    viewport.scrollTop = Math.max(0, (reset ? .5 : centerY) * canvas.offsetHeight - height / 2);
    viewport.classList.toggle('can-pan', zoom > 1);
  }
  function setZoom(value) {zoom = Math.min(4, Math.max(1, value)); resize(zoom === 1);}
  function build() {
    dialog = node('dialog', 'portrait-viewer');
    dialog.setAttribute('aria-labelledby', 'portrait-viewer-title');
    dialog.setAttribute('aria-describedby', 'portrait-viewer-help');
    const header = node('header', 'portrait-viewer-header');
    title = node('h2'); title.id = 'portrait-viewer-title';
    const closeButton = node('button', 'portrait-viewer-close', '关闭 ×');
    closeButton.type = 'button'; closeButton.setAttribute('aria-label', '关闭立绘'); closeButton.autofocus = true;
    closeButton.addEventListener('click', () => close());
    header.append(title, closeButton);
    const tools = node('div', 'portrait-viewer-tools');
    zoomOut = node('button', '', '− 缩小'); zoomIn = node('button', '', '+ 放大'); fit = node('button', '', '适应窗口');
    [zoomOut, zoomIn, fit].forEach((button) => {button.type = 'button';});
    scaleLabel = node('output', 'portrait-viewer-scale'); scaleLabel.setAttribute('aria-label', '相对适应窗口的缩放比例');
    zoomOut.addEventListener('click', () => setZoom(zoom - .5));
    zoomIn.addEventListener('click', () => setZoom(zoom + .5));
    fit.addEventListener('click', () => setZoom(1));
    tools.append(zoomOut, scaleLabel, zoomIn, fit);
    viewport = node('div', 'portrait-viewer-viewport'); viewport.tabIndex = 0;
    viewport.setAttribute('role', 'region'); viewport.setAttribute('aria-label', '角色立绘，可滚动查看');
    canvas = node('div', 'portrait-viewer-canvas');
    image = node('img'); image.draggable = false;
    image.addEventListener('load', () => {
      if (!dialog.open) return;
      image.hidden = false; status.hidden = true; resize(true);
    });
    image.addEventListener('error', () => {
      if (!dialog.open) return;
      image.hidden = true; status.hidden = false; status.textContent = '立绘暂时无法载入，请关闭后重试。'; resize();
    });
    status = node('p', 'portrait-viewer-status'); status.setAttribute('role', 'status');
    canvas.append(image); viewport.append(canvas, status);
    const help = node('p', 'portrait-viewer-help', '滚动或拖动查看 · 点击空白处或按 Esc 关闭'); help.id = 'portrait-viewer-help';
    dialog.append(header, tools, viewport, help); document.body.append(dialog);
    dialog.addEventListener('cancel', (event) => {event.preventDefault(); close();});
    dialog.addEventListener('close', () => {if (!dialog.open) release();});
    dialog.addEventListener('click', (event) => {
      if (dragged) {dragged = false; return;}
      if ([dialog, viewport, canvas].includes(event.target)) close();
    });
    viewport.addEventListener('pointerdown', (event) => {
      dragged = false;
      if (event.pointerType === 'touch' || event.button !== 0 || zoom <= 1) return;
      drag = {id: event.pointerId, x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop};
    });
    viewport.addEventListener('pointermove', (event) => {
      if (!drag || drag.id !== event.pointerId) return;
      const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) {
        dragged = true; viewport.setPointerCapture(event.pointerId); viewport.classList.add('is-panning');
      }
      viewport.scrollLeft = drag.left - dx; viewport.scrollTop = drag.top - dy;
    });
    const endPan = () => {drag = null; viewport.classList.remove('is-panning');};
    viewport.addEventListener('pointerup', endPan); viewport.addEventListener('pointercancel', endPan);
    window.addEventListener('resize', () => resize());
  }
  function open({url, alt, trigger}) {
    if (typeof url !== 'string' || !url || /[\u0000-\u001f\\]/.test(url)
      || (/^[a-z][a-z\d+.-]*:/i.test(url) && !/^https?:\/\//i.test(url))) return;
    if (!dialog) build();
    close(false);
    opener = trigger || document.activeElement;
    locked = {x: window.scrollX, y: window.scrollY, overflow: document.documentElement.style.overflow,
      styles: Object.fromEntries(bodyProperties.map((key) => [key, document.body.style[key]]))};
    document.body.style.position = 'fixed'; document.body.style.top = `${-locked.y}px`;
    document.body.style.left = `${-locked.x}px`; document.body.style.width = '100%';
    document.body.style.overflow = 'hidden'; document.documentElement.style.overflow = 'hidden';
    zoom = 1; image.hidden = true; status.hidden = false; status.textContent = '正在载入立绘…';
    title.textContent = alt || '角色立绘'; image.alt = alt || '角色立绘';
    canvas.style.width = '100%'; canvas.style.height = '100%';
    dialog.showModal(); resize(); image.src = url;
  }
  window.addEventListener('hashchange', () => close(false));
  window.WFPortraitViewer = {open, close};
})();
