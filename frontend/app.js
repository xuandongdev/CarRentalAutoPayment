const DEFAULT_API_BASE = 'http://127.0.0.1:8000';
const TOKEN_KEY = 'authToken';
let sessionCache = null;

function ensureUiChrome() {
  if (!document.getElementById('noticeStack')) {
    const stack = document.createElement('div');
    stack.id = 'noticeStack';
    stack.className = 'notice-stack';
    document.body.appendChild(stack);
  }

  const main = document.querySelector('main');
  if (main && !document.getElementById('roleNotice')) {
    const section = document.createElement('section');
    section.className = 'card role-notice hidden';
    section.id = 'roleNotice';
    section.innerHTML = `
      <h3>Quyen Truy Cap</h3>
      <p id="roleNoticeText" class="note">Trang nay khong phu hop voi role hien tai.</p>
    `;
    main.prepend(section);
  }

  if (main && !document.getElementById('sessionSummary')) {
    const section = document.createElement('section');
    section.className = 'card session-card';
    section.innerHTML = `
      <h3>Tai Khoan Dang Dang Nhap</h3>
      <p class="note">Hien ten, vai tro, dia chi vi va so du hien tai cua tai khoan dang su dung token.</p>
      <div id="sessionSummary" class="session-summary">Chua dang nhap</div>
    `;
    main.prepend(section);
  }

  if (main && !document.getElementById('activityLog')) {
    const section = document.createElement('section');
    section.className = 'card';
    section.innerHTML = `
      <h3>Activity Log</h3>
      <p class="note">Lich su thao tac tren giao dien de theo doi success, error va response quan trong.</p>
      <pre id="activityLog">Chua co thao tac nao</pre>
    `;
    main.appendChild(section);
  }
}

function showNotice(message, type = 'info') {
  ensureUiChrome();
  const stack = document.getElementById('noticeStack');
  if (!stack) return;
  const item = document.createElement('div');
  item.className = `notice ${type}`;
  item.textContent = message;
  stack.prepend(item);
  window.setTimeout(() => item.remove(), 4500);
}

function appendActivityLog(action, status, detail = '') {
  ensureUiChrome();
  const target = document.getElementById('activityLog');
  if (!target) return;
  const stamp = new Date().toLocaleString('vi-VN');
  const line = `[${stamp}] ${action} | ${status}${detail ? ` | ${detail}` : ''}`;
  const current = target.textContent === 'Chua co thao tac nao' ? '' : `${target.textContent}\n`;
  target.textContent = `${line}${current}`;
}

function notifySuccess(action, detail = '') {
  showNotice(`${action} thanh cong`, 'success');
  appendActivityLog(action, 'success', detail);
}

function notifyError(action, error) {
  const message = error instanceof Error ? error.message : String(error);
  showNotice(`${action} that bai: ${message}`, 'error');
  appendActivityLog(action, 'error', message);
}

function setDefaultApiBase(inputId = 'apiBase') {
  ensureUiChrome();
  const input = document.getElementById(inputId);
  if (!input) return;
  input.value = localStorage.getItem('apiBase') || DEFAULT_API_BASE;
  input.addEventListener('change', () => {
    localStorage.setItem('apiBase', input.value.trim() || DEFAULT_API_BASE);
    appendActivityLog('api_base_change', 'info', input.value.trim() || DEFAULT_API_BASE);
    sessionCache = null;
    fetchSession().catch(() => null);
  });
  fetchSession().catch(() => null);
}

function getApiBase(inputId = 'apiBase') {
  const input = document.getElementById(inputId);
  const value = (input?.value || localStorage.getItem('apiBase') || DEFAULT_API_BASE).trim();
  localStorage.setItem('apiBase', value || DEFAULT_API_BASE);
  return (value || DEFAULT_API_BASE).replace(/\/$/, '');
}

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
  sessionCache = null;
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  sessionCache = null;
  const target = document.getElementById('sessionSummary');
  if (target) target.textContent = 'Chua dang nhap';
  applyRoleVisibility(null);
}

function currentRoleFromSession(session) {
  return String(session?.user?.vaiTro || '').trim().toLowerCase();
}

function roleMatches(allowedRoles, currentRole) {
  if (!allowedRoles) return true;
  const allowed = String(allowedRoles).split(',').map((item) => item.trim().toLowerCase()).filter(Boolean);
  if (!allowed.length) return true;
  return allowed.includes(currentRole || 'guest');
}

function applyRoleVisibility(session) {
  ensureUiChrome();
  const role = currentRoleFromSession(session) || 'guest';
  document.body.dataset.currentRole = role;

  document.querySelectorAll('[data-visible-for]').forEach((element) => {
    element.classList.toggle('hidden', !roleMatches(element.dataset.visibleFor, role));
  });

  const pageRole = document.body.dataset.pageRole;
  const roleNotice = document.getElementById('roleNotice');
  const roleNoticeText = document.getElementById('roleNoticeText');
  const unauthorized = pageRole && !roleMatches(pageRole, role);
  if (roleNotice) {
    roleNotice.classList.toggle('hidden', !unauthorized);
  }
  if (roleNoticeText && unauthorized) {
    roleNoticeText.textContent = `Role hien tai la ${role}. Trang nay phu hop cho: ${pageRole}.`; 
  }

  document.querySelectorAll('[data-page-content]').forEach((element) => {
    element.classList.toggle('hidden', unauthorized);
  });
}

async function fetchSession(force = false) {
  if (!force && sessionCache !== null) return sessionCache;
  const token = getToken();
  if (!token) {
    sessionCache = null;
    applyRoleVisibility(null);
    return null;
  }
  try {
    const data = await requestJson('GET', `${getApiBase()}/auth/me`, null, token);
    sessionCache = data;
    applyRoleVisibility(data);
    return data;
  } catch (error) {
    sessionCache = null;
    applyRoleVisibility(null);
    return null;
  }
}

function formatMoney(value) {
  const number = Number(value || 0);
  return Number.isFinite(number) ? number.toLocaleString('vi-VN', { maximumFractionDigits: 8 }) : '0';
}

async function loadSessionSummary(targetId = 'sessionSummary') {
  ensureUiChrome();
  const target = document.getElementById(targetId);
  if (!target) return null;
  const token = getToken();
  if (!token) {
    target.textContent = 'Chua dang nhap';
    return null;
  }
  try {
    const data = await requestJson('GET', `${getApiBase()}/auth/me`, null, token);
    const user = data?.user || {};
    const wallets = Array.isArray(data?.wallets) ? data.wallets : [];
    const walletLines = wallets.length
      ? wallets.map((wallet) => `- ${wallet.address || 'n/a'} | balance=${formatMoney(wallet.balance)} | locked=${formatMoney(wallet.lockedbalance || wallet.lockedBalance)}`).join('\n')
      : 'Chua lien ket vi';
    target.textContent = [
      `Ho ten: ${user.hoTen || 'n/a'}`,
      `Vai tro: ${user.vaiTro || 'n/a'}`,
      `Email: ${user.email || 'n/a'}`,
      `So dien thoai: ${user.soDienThoai || 'n/a'}`,
      'Wallets:',
      walletLines,
    ].join('\n');
    return data;
  } catch (error) {
    target.textContent = `Khong tai duoc session: ${error.message}`;
    return null;
  }
}

async function requestJson(method, url, body, token = '') {
  const headers = { 'Content-Type': 'application/json' };
  const finalToken = token || getToken();
  if (finalToken) headers.Authorization = `Bearer ${finalToken}`;
  const response = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });
  const data = await response.json().catch(() => ({ detail: 'Khong doc duoc JSON response' }));
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data, null, 2);
    throw new Error(detail);
  }
  return data;
}

function renderJson(targetId, data) {
  const target = document.getElementById(targetId);
  if (target) target.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
}

function parseTextareaUrls(value) {
  const raw = (value || '').trim();
  if (!raw) return [];
  if (raw.startsWith('[')) {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) throw new Error('Evidence URLs phai la JSON array hoac moi dong 1 URL');
    return parsed.map((item) => String(item).trim()).filter(Boolean);
  }
  return raw.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function requireValue(value, message) {
  if (value === undefined || value === null || String(value).trim() === '') throw new Error(message);
  return String(value).trim();
}

function parseNonNegativeNumber(value, message) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) throw new Error(message);
  return number;
}

function diffDays(startValue, endValue) {
  const start = new Date(startValue);
  const end = new Date(endValue);
  const diff = Math.ceil((end - start) / (1000 * 60 * 60 * 24));
  return diff > 0 ? diff : 1;
}

function compactRows(rows, fields) {
  return (rows || []).map((row) => {
    const item = {};
    fields.forEach((field) => {
      item[field] = row?.[field] ?? null;
    });
    return item;
  });
}

function renderReferenceData(targetId, overview) {
  const target = document.getElementById(targetId);
  if (!target) return;
  const snapshot = {
    users: compactRows(overview?.users, ['id', 'hoten', 'email', 'sodienthoai', 'vaitro', 'trangthai']),
    wallets: compactRows(overview?.wallets, ['id', 'address', 'nguoidungid', 'wallettype', 'status', 'balance', 'lockedbalance']),
    vehicles: compactRows(overview?.vehicles, ['id', 'bienso', 'hangxe', 'dongxe', 'loaixe', 'chuxeid', 'trangthai', 'giatheongay']),
    bookings: compactRows(overview?.bookings, ['id', 'nguoidungid', 'xeid', 'songaythue', 'tongtienthue', 'trangthai']),
    contracts: compactRows(overview?.contracts, ['id', 'dangkyid', 'nguoithueid', 'chuxeid', 'xeid', 'trangthai', 'tongtiencoc', 'danhanlaixe']),
    disputes: compactRows(overview?.disputes, ['id', 'hopdongthueid', 'trangthai', 'ketquaxuly', 'sotienphaithu']),
    finance: {
      platformFeeWalletBalance: overview?.platformFeeWalletBalance,
      escrowWalletBalance: overview?.escrowWalletBalance,
      totalWalletBalance: overview?.totalWalletBalance,
      totalLockedBalance: overview?.totalLockedBalance,
      totalFeesCollected: overview?.totalFeesCollected,
      totalGrossPayments: overview?.totalGrossPayments,
      totalNetPayouts: overview?.totalNetPayouts,
    },
    warnings: overview?.warnings || {},
  };
  target.textContent = JSON.stringify(snapshot, null, 2);
}

async function loadReferenceData(targetId = 'referenceData') {
  const data = await requestJson('GET', `${getApiBase()}/api/overview`);
  renderReferenceData(targetId, data);
  await loadSessionSummary().catch(() => null);
  return data;
}

function bindUtilityButtons(targetId = 'result', referenceTargetId = 'referenceData') {
  ensureUiChrome();
  const overviewBtn = document.getElementById('loadOverviewBtn');
  if (overviewBtn) {
    overviewBtn.addEventListener('click', async () => {
      try {
        const data = await requestJson('GET', `${getApiBase()}/api/overview`);
        renderJson(targetId, data);
        renderReferenceData(referenceTargetId, data);
        notifySuccess('load_overview', `syncStatus=${data.syncStatus}`);
      } catch (error) {
        renderJson(targetId, { error: error.message });
        notifyError('load_overview', error);
      }
    });
  }

  const chainBtn = document.getElementById('loadChainBtn');
  if (chainBtn) {
    chainBtn.addEventListener('click', async () => {
      try {
        const data = await requestJson('GET', `${getApiBase()}/api/node/chain`);
        renderJson(targetId, data);
        notifySuccess('load_chain', `latestBlockHeight=${data?.meta?.latestBlockHeight ?? 'n/a'}`);
      } catch (error) {
        renderJson(targetId, { error: error.message });
        notifyError('load_chain', error);
      }
    });
  }

  const reconcileBtn = document.getElementById('runReconcileBtn');
  if (reconcileBtn) {
    reconcileBtn.addEventListener('click', async () => {
      try {
        const data = await requestJson('POST', `${getApiBase()}/api/node/reconcile`);
        renderJson(targetId, data);
        await loadReferenceData(referenceTargetId);
        notifySuccess('run_reconcile', `mirroredNewBlocks=${data.mirroredNewBlocks}`);
      } catch (error) {
        renderJson(targetId, { error: error.message });
        notifyError('run_reconcile', error);
      }
    });
  }
}
