/* KnowTaxx AP Suite: UI behaviour, offline queue and sync. No dependencies. */
(function () {
  'use strict';

  /* ---------- Toast ---------- */
  function toast(message, kind) {
    let host = document.getElementById('toast-host');
    if (!host) {
      host = document.createElement('div');
      host.id = 'toast-host';
      host.setAttribute('role', 'status');
      document.body.appendChild(host);
    }
    const el = document.createElement('div');
    el.className = 'toast toast-' + (kind || 'info');
    el.textContent = message;
    host.appendChild(el);
    setTimeout(() => el.remove(), 6000);
  }

  /* ---------- IndexedDB ---------- */
  const DB_NAME = 'ktap-offline';
  function openDb() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains('queue')) db.createObjectStore('queue', { keyPath: 'uuid' });
        if (!db.objectStoreNames.contains('cache')) db.createObjectStore('cache', { keyPath: 'key' });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  async function store(name, mode, fn) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(name, mode);
      const result = fn(tx.objectStore(name));
      tx.oncomplete = () => { db.close(); resolve(result && 'result' in result ? result.result : undefined); };
      tx.onerror = () => { db.close(); reject(tx.error); };
    });
  }
  const queueAll = () => store('queue', 'readonly', s => s.getAll());
  const queuePut = item => store('queue', 'readwrite', s => s.put(item));
  const queueDelete = uuid => store('queue', 'readwrite', s => s.delete(uuid));
  const cacheGet = async key => { const row = await store('cache', 'readonly', s => s.get(key)); return row ? row.value : null; };
  const cachePut = (key, value) => store('cache', 'readwrite', s => s.put({ key, value }));
  const cacheDelete = key => store('cache', 'readwrite', s => s.delete(key));

  function uuid4() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, c =>
      (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
  }
  function deviceId() {
    let id = null;
    try { id = localStorage.getItem('ktap-device'); } catch (e) { /* private mode */ }
    if (!id) {
      id = uuid4();
      try { localStorage.setItem('ktap-device', id); } catch (e) { /* private mode */ }
    }
    return id;
  }

  /* ---------- Queue API used by the offline page ---------- */
  async function enqueue(actionType, payload, extra) {
    const user = await cacheGet('user');
    const item = Object.assign({
      uuid: uuid4(), action_type: actionType, payload, created_at: new Date().toISOString(),
      user_id: user ? user.id : null, state: 'queued', detail: null
    }, extra || {});
    await queuePut(item);
    return item;
  }

  const blobToBase64 = blob => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });

  async function serverReachable() {
    try {
      const response = await fetch('/api/health', { cache: 'no-store' });
      return response.ok;
    } catch (e) { return false; }
  }

  let syncing = false;
  async function syncQueue(options) {
    const silent = options && options.silent;
    if (syncing) return null;
    syncing = true;
    try {
      const items = (await queueAll()).filter(i => i.state === 'queued');
      if (!items.length) return null;
      if (!(await serverReachable())) {
        if (!silent) toast('Server not reachable. Your items stay queued on this device.', 'warning');
        return null;
      }
      const tokenResponse = await fetch('/api/csrf', { credentials: 'same-origin' });
      if (tokenResponse.status === 401 || tokenResponse.redirected) {
        toast('Sign in to sync ' + items.length + ' queued item(s).', 'warning');
        return null;
      }
      if (!tokenResponse.ok) return null;
      const token = (await tokenResponse.json()).csrf_token;
      const me = await cacheGet('user');
      const totals = { synced: 0, conflict: 0, failed: 0 };

      for (const item of items) {
        if (item.user_id && me && item.user_id !== me.id) continue; // belongs to another signed-in user
        const payload = Object.assign({}, item.payload);
        if (item.blob) {
          payload.image_base64 = await blobToBase64(item.blob);
          payload.filename = item.filename;
        }
        const response = await fetch('/api/sync', {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
          body: JSON.stringify({
            device_id: deviceId(),
            items: [{ uuid: item.uuid, action_type: item.action_type, payload, created_at: item.created_at }]
          })
        });
        if (!response.ok) continue; // left queued for the next attempt
        const result = (await response.json()).results[0];
        if (result.status === 'synced') {
          totals.synced++;
          await queueDelete(item.uuid);
        } else {
          totals[result.status === 'conflict' ? 'conflict' : 'failed']++;
          item.state = result.status;
          item.detail = result.detail;
          delete item.blob;
          await queuePut(item);
        }
      }
      const done = totals.synced + totals.conflict + totals.failed;
      if (done) {
        const parts = [totals.synced + ' item' + (totals.synced === 1 ? '' : 's') + ' synced'];
        if (totals.conflict) parts.push(totals.conflict + ' conflict' + (totals.conflict === 1 ? '' : 's'));
        if (totals.failed) parts.push(totals.failed + ' failed');
        toast(parts.join(', '), totals.conflict || totals.failed ? 'warning' : 'success');
      }
      document.dispatchEvent(new CustomEvent('ktap:queue-changed'));
      return totals;
    } finally {
      syncing = false;
    }
  }

  /* ---------- Cache for offline use, and new-approval alerts ---------- */
  async function refreshCache() {
    if (!document.body.dataset.userId) return;
    try {
      const response = await fetch('/api/bootstrap', { credentials: 'same-origin' });
      if (!response.ok) return;
      const data = await response.json();
      await cachePut('user', data.user);
      await cachePut('clients', data.clients);
      await cachePut('pending', data.pending);
      await cachePut('cached_at', new Date().toISOString());

      const previous = await cacheGet('my_pending_count');
      await cachePut('my_pending_count', data.my_pending_count);
      if (previous !== null && data.my_pending_count > previous) notifyNewApprovals(data.my_pending_count - previous);
    } catch (e) { /* offline: keep the last snapshot */ }
  }

  async function notifyNewApprovals(count) {
    toast(count + ' new invoice(s) awaiting your approval.', 'info');
    if (!('Notification' in window) || Notification.permission !== 'granted' || !navigator.serviceWorker) return;
    const registration = await navigator.serviceWorker.getRegistration();
    if (registration) {
      registration.showNotification('KnowTaxx AP Suite', {
        body: count + ' new invoice(s) awaiting your approval', icon: '/static/icons/icon-192.png', tag: 'ktap-approvals'
      });
    }
  }

  async function clearCachedData() {
    for (const key of ['user', 'clients', 'pending', 'cached_at', 'my_pending_count']) await cacheDelete(key);
  }

  /* ---------- Sidebar ---------- */
  function initSidebar() {
    const toggle = document.getElementById('sidebar-toggle');
    const scrim = document.getElementById('sidebar-scrim');
    if (!toggle) return;
    const close = () => { document.body.classList.remove('sidebar-open'); toggle.setAttribute('aria-expanded', 'false'); };
    toggle.addEventListener('click', () => {
      const open = document.body.classList.toggle('sidebar-open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    if (scrim) scrim.addEventListener('click', close);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  }

  /* ---------- Decision dialog + swipe on approval cards ---------- */
  function initApprovals() {
    const dialog = document.getElementById('decision-dialog');
    if (!dialog) return;
    const form = dialog.querySelector('form');
    const title = dialog.querySelector('[data-title]');
    const label = dialog.querySelector('[data-label]');
    const box = dialog.querySelector('textarea');
    const confirmButton = dialog.querySelector('[data-confirm]');
    const config = {
      approve: { title: 'Approve invoice', label: 'Comment (optional)', required: false, button: 'Approve', cls: 'btn-success' },
      reject: { title: 'Reject invoice', label: 'Reason for rejection (required)', required: true, button: 'Reject', cls: 'btn-danger' },
      query: { title: 'Query to accountant', label: 'Your question (required)', required: true, button: 'Send query', cls: 'btn-warning' }
    };
    function open(card, action) {
      const c = config[action];
      form.action = card.dataset.base + '/' + action;
      title.textContent = c.title + ': ' + card.dataset.vendor;
      label.textContent = c.label;
      box.required = c.required;
      box.value = '';
      confirmButton.textContent = c.button;
      confirmButton.className = 'btn ' + c.cls;
      dialog.showModal();
      box.focus();
    }
    dialog.querySelector('[data-cancel]').addEventListener('click', () => dialog.close());
    document.querySelectorAll('.approval-card').forEach(card => {
      card.querySelectorAll('[data-action]').forEach(button => {
        button.addEventListener('click', () => open(card, button.dataset.action));
      });
      let startX = null, startY = null, dx = 0;
      card.addEventListener('touchstart', e => {
        if (e.target.closest('button, a')) return;
        startX = e.touches[0].clientX; startY = e.touches[0].clientY; dx = 0;
      }, { passive: true });
      card.addEventListener('touchmove', e => {
        if (startX === null) return;
        dx = e.touches[0].clientX - startX;
        if (Math.abs(e.touches[0].clientY - startY) > 40) { startX = null; card.style.transform = ''; return; }
        card.style.transform = 'translateX(' + dx * 0.6 + 'px)';
        card.dataset.swipe = dx > 50 ? 'approve' : (dx < -50 ? 'reject' : '');
      }, { passive: true });
      card.addEventListener('touchend', () => {
        if (startX === null) return;
        card.style.transform = '';
        card.dataset.swipe = '';
        if (dx > 90) open(card, 'approve');
        else if (dx < -90) open(card, 'reject');
        startX = null;
      });
    });
    const alerts = document.getElementById('enable-alerts');
    if (alerts && 'Notification' in window && Notification.permission === 'default') {
      alerts.hidden = false;
      alerts.addEventListener('click', async () => {
        const result = await Notification.requestPermission();
        alerts.hidden = true;
        toast(result === 'granted' ? 'Alerts on for this device.' : 'Alerts stay off.', 'info');
      });
    }
  }

  /* ---------- Upload page ---------- */
  function initUpload() {
    const form = document.getElementById('upload-form');
    if (!form) return;
    const zone = document.getElementById('drop-zone');
    const picker = document.getElementById('file-picker');
    const camera = document.getElementById('camera-input');
    const list = document.getElementById('upload-results');
    const bar = document.getElementById('upload-progress');
    const barFill = bar.querySelector('span');
    const barText = document.getElementById('upload-status');

    function send(files, captured) {
      if (!files.length) return;
      const body = new FormData();
      body.append('csrf_token', form.querySelector('[name=csrf_token]').value);
      if (captured) body.append('captured', '1');
      Array.from(files).forEach(f => body.append('files', f));
      const xhr = new XMLHttpRequest();
      xhr.open('POST', form.action);
      xhr.setRequestHeader('Accept', 'application/json');
      bar.hidden = false;
      barFill.style.width = '0';
      barText.textContent = 'Uploading ' + files.length + ' file(s)...';
      xhr.upload.onprogress = e => {
        if (e.lengthComputable) barFill.style.width = Math.round(e.loaded * 100 / e.total) + '%';
      };
      xhr.upload.onload = () => { barText.textContent = 'Reading the documents with OCR. This can take a few seconds per page...'; };
      xhr.onerror = () => { barText.textContent = 'Upload failed. Check the connection and try again.'; };
      xhr.onload = () => {
        bar.hidden = true;
        barText.textContent = '';
        if (xhr.status !== 200) { toast('Upload failed (' + xhr.status + ').', 'danger'); return; }
        JSON.parse(xhr.responseText).results.forEach(renderResult);
      };
      xhr.send(body);
    }
    function renderResult(result) {
      const li = document.createElement('li');
      li.className = 'upload-result ' + (result.ok ? 'ok' : 'bad');
      const name = document.createElement('strong');
      name.textContent = result.file;
      li.appendChild(name);
      const info = document.createElement('span');
      if (result.ok) {
        info.textContent = result.vendor + ' · ' + Math.round(result.confidence * 100) + '% confidence' + (result.duplicate ? ' · possible duplicate' : '');
        li.appendChild(info);
        const link = document.createElement('a');
        link.href = result.url;
        link.className = 'btn btn-sm btn-primary';
        link.textContent = 'Review';
        li.appendChild(link);
      } else {
        info.textContent = result.error;
        li.appendChild(info);
      }
      list.appendChild(li);
    }
    picker.addEventListener('change', () => { send(picker.files, false); picker.value = ''; });
    if (camera) camera.addEventListener('change', () => { send(camera.files, true); camera.value = ''; });
    form.addEventListener('submit', e => { e.preventDefault(); send(picker.files, false); });
    ['dragenter', 'dragover'].forEach(t => zone.addEventListener(t, e => { e.preventDefault(); zone.classList.add('drag'); }));
    ['dragleave', 'drop'].forEach(t => zone.addEventListener(t, e => { e.preventDefault(); zone.classList.remove('drag'); }));
    zone.addEventListener('drop', e => send(e.dataTransfer.files, false));
  }

  /* ---------- Small helpers ---------- */
  function initCopyButtons() {
    document.querySelectorAll('[data-copy]').forEach(button => {
      button.addEventListener('click', async () => {
        const input = document.getElementById(button.dataset.copy);
        input.select();
        try {
          await navigator.clipboard.writeText(input.value);
        } catch (e) {
          document.execCommand('copy');
        }
        toast('Link copied.', 'success');
      });
    });
  }
  function initConfirms() {
    document.querySelectorAll('form[data-confirm-text]').forEach(form => {
      form.addEventListener('submit', e => { if (!confirm(form.dataset.confirmText)) e.preventDefault(); });
    });
    document.querySelectorAll('form[data-clear-offline]').forEach(form => {
      form.addEventListener('submit', async e => {
        e.preventDefault();
        await clearCachedData().catch(() => {});
        form.submit();
      });
    });
  }

  /* ---------- iOS install guide ---------- */
  function initIosGuide() {
    const overlay = document.getElementById('ios-install');
    if (!overlay) return;
    const ua = navigator.userAgent;
    const isIos = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    const isSafari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
    const standalone = window.navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches;
    let dismissed = false;
    try { dismissed = localStorage.getItem('ktap-ios-dismissed') === '1'; } catch (e) { /* private mode */ }
    if (isIos && isSafari && !standalone && !dismissed) overlay.hidden = false;
    overlay.querySelector('[data-dismiss]').addEventListener('click', () => {
      overlay.hidden = true;
      try { localStorage.setItem('ktap-ios-dismissed', '1'); } catch (e) { /* private mode */ }
    });
  }

  /* ---------- Connectivity ---------- */
  function initConnectivity() {
    const signedIn = !!document.body.dataset.userId;
    window.addEventListener('online', () => { if (signedIn) { syncQueue(); refreshCache(); } });
    if (signedIn) {
      refreshCache().then(() => syncQueue({ silent: true }));
      setInterval(() => { refreshCache(); syncQueue({ silent: true }); }, 60000);
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initApprovals();
    initUpload();
    initCopyButtons();
    initConfirms();
    initIosGuide();
    if ('indexedDB' in window) initConnectivity();
  });

  window.KTAP = { toast, enqueue, queueAll, queueDelete, queuePut, cacheGet, syncQueue, serverReachable, uuid4 };
})();
