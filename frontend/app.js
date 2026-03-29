const DEFAULT_API_BASE = 'http://127.0.0.1:8000';

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

async function requestJson(method, url, body) {
  const response = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
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
  if (value === undefined || value === null || String(value).trim() === '') {
    throw new Error(message);
  }
  return String(value).trim();
}

function parseNonNegativeNumber(value, message) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) {
    throw new Error(message);
  }
  return number;
}

function diffDays(startValue, endValue) {
  const start = new Date(startValue);
  const end = new Date(endValue);
  const diff = Math.ceil((end - start) / (1000 * 60 * 60 * 24));
  return diff > 0 ? diff : 1;
}
