/* Recoverable cloud-team actions use a visible, keyboard-friendly confirmation. */
(() => {
  'use strict';
  let serial = 0, active;
  window.WFCommunityAdminConfirm = {ask(message, {restore = false, title, confirmLabel, cancelLabel = '取消'} = {}) {
    active?.();
    return new Promise(resolve => {
      const origin = document.activeElement, dialog = document.createElement('dialog');
      dialog.className = 'admin-action-dialog';
      const heading = document.createElement('h2'), description = document.createElement('p');
      heading.id = `admin-action-title-${++serial}`; heading.textContent = title || (restore ? '恢复队伍' : '删除队伍');
      description.textContent = message; dialog.setAttribute('aria-labelledby', heading.id);
      const actions = document.createElement('div'); actions.className = 'admin-action-dialog-buttons';
      const cancel = document.createElement('button'), confirm = document.createElement('button');
      cancel.type = confirm.type = 'button'; cancel.textContent = cancelLabel; cancel.className = 'secondary-button';
      confirm.textContent = confirmLabel || (restore ? '确认恢复' : '移到回收站'); confirm.className = restore ? 'primary-button' : 'admin-delete-button';
      let settled = false;
      function finish(value) {
        if (settled) return; settled = true;
        if (active === dismiss) active = null;
        window.removeEventListener('hashchange', dismiss);
        dialog.close?.(); dialog.remove();
        if (origin?.isConnected) origin.focus();
        resolve(value);
      }
      const dismiss = () => finish(false);
      active = dismiss;
      cancel.addEventListener('click', dismiss); confirm.addEventListener('click', () => finish(true));
      dialog.addEventListener('cancel', event => {event.preventDefault(); dismiss();});
      dialog.addEventListener('close', dismiss);
      window.addEventListener('hashchange', dismiss);
      actions.append(cancel, confirm); dialog.append(heading, description, actions);
      document.body.append(dialog);
      try {dialog.showModal(); cancel.focus();} catch {dismiss();}
    });
  }};
})();
