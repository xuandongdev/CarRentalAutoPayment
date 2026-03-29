const DEFAULT_API_BASE = 'http://127.0.0.1:8000';
const TOKEN_KEY = 'authToken';

function setDefaultApiBase(inputId = 'apiBase') {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.value = localStorage.getItem('apiBase') || DEFAULT_API_BASE;
  input.addEventListener('change', () => localStorage.setItem('apiBase', input.value.trim() || DEFAULT_API_BASE));
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
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
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
    vehicles: compactRows(overview?.vehicles, ['id', 'bienso', 'hangxe', 'dongxe', 'loaixe', 'chuxeid', 'trangthai', 'giatheongay']),
    bookings: compactRows(overview?.bookings, ['id', 'nguoidungid', 'xeid', 'songaythue', 'tongtienthue', 'trangthai']),
    contracts: compactRows(overview?.contracts, ['id', 'dangkyid', 'nguoithueid', 'chuxeid', 'xeid', 'trangthai', 'tongtiencoc', 'danhanlaixe']),
    disputes: compactRows(overview?.disputes, ['id', 'hopdongthueid', 'trangthai', 'ketquaxuly', 'sotienphaithu']),
  };
  target.textContent = JSON.stringify(snapshot, null, 2);
}

async function loadReferenceData(targetId = 'referenceData') {
  const data = await requestJson('GET', `${getApiBase()}/api/overview`);
  renderReferenceData(targetId, data);
  return data;
}

function bindUtilityButtons(targetId = 'result', referenceTargetId = 'referenceData') {
  const overviewBtn = document.getElementById('loadOverviewBtn');
  if (overviewBtn) {
    overviewBtn.addEventListener('click', async () => {
      try {
        const data = await requestJson('GET', `${getApiBase()}/api/overview`);
        renderJson(targetId, data);
        renderReferenceData(referenceTargetId, data);
      } catch (error) {
        renderJson(targetId, { error: error.message });
      }
    });
  }

  const chainBtn = document.getElementById('loadChainBtn');
  if (chainBtn) {
    chainBtn.addEventListener('click', async () => {
      try {
        renderJson(targetId, await requestJson('GET', `${getApiBase()}/api/node/chain`));
      } catch (error) {
        renderJson(targetId, { error: error.message });
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
      } catch (error) {
        renderJson(targetId, { error: error.message });
      }
    });
  }
}
