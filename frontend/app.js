const TOKEN_KEY = 'authToken';
const API_BASE_KEY = 'apiBase';
const DEFAULT_API_BASE = 'http://127.0.0.1:8000';

function getApiBase() {
  return (localStorage.getItem(API_BASE_KEY) || DEFAULT_API_BASE).replace(/\/$/, '');
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

function normalizeRole(role) {
  return String(role || '').trim().toLowerCase();
}

function redirectByRole(role) {
  const normalized = normalizeRole(role);
  if (normalized === 'admin') return (window.location.href = '/admin/dashboard');
  if (normalized === 'chuxe') return (window.location.href = '/owner/dashboard');
  return (window.location.href = '/renter/dashboard');
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function statusBadge(status) {
  const text = String(status || 'unknown');
  const normalized = text.toLowerCase();
  let cls = 'neutral';
  if (['pending', 'choxacnhan', 'choduyet', 'dangxuLy', 'dangmo', 'đang chờ', 'dangcho'].includes(normalized)) cls = 'pending';
  if (['confirmed', 'hoatdong', 'sansang', 'hoanthanh', 'active', 'dakhoa', 'daduyet', 'dagiaiquyet', 'đang cho thuê', 'dangchothue'].includes(normalized)) cls = 'ok';
  if (['failed', 'cancelled', 'dahuy', 'tamkhoa', 'ngunghoatdong', 'bảo trì', 'ngừng hoạt động'].includes(normalized)) cls = 'danger';
  return `<span class="badge ${cls}">${escapeHtml(text)}</span>`;
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

  const data = await response.json().catch(() => ({ detail: 'Không đọc được JSON response' }));
  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data));
  }
  return data;
}

function showMessage(targetId, text, type = 'info') {
  const el = document.getElementById(targetId);
  if (el) {
    el.textContent = text || '';
    el.className = `message ${type}`;
  }
  toast(text || '', type);
}

function requireValue(value, message) {
  if (value === undefined || value === null || String(value).trim() === '') {
    throw new Error(message);
  }
  return String(value).trim();
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('vi-VN');
}

function formatMoney(value) {
  const n = Number(value || 0);
  if (Number.isNaN(n)) return String(value || 0);
  return new Intl.NumberFormat('vi-VN').format(n);
}

async function getSession(forceRedirect = false) {
  const token = getToken();
  if (!token) {
    if (forceRedirect) window.location.href = '/login';
    return null;
  }

  try {
    return await requestJson('GET', `${getApiBase()}/auth/me`);
  } catch (_error) {
    clearToken();
    if (forceRedirect) window.location.href = '/login';
    return null;
  }
}

function navLinksByRole(role) {
  const links = {
    guest: [
      { href: '/', text: 'Trang chủ' },
      { href: '/vehicles', text: 'Xe công khai' },
      { href: '/login', text: 'Đăng nhập' },
      { href: '/register', text: 'Đăng ký' },
    ],
    khach: [
      { href: '/renter/dashboard', text: 'Tổng quan' },
      { href: '/renter/vehicles', text: 'Đặt xe' },
      { href: '/renter/bookings', text: 'Booking' },
      { href: '/renter/contracts', text: 'Hợp đồng' },
      { href: '/renter/deposits', text: 'Tiền cọc' },
      { href: '/vehicles', text: 'Xe công khai' },
      { href: '#logout', text: 'Đăng xuất' },
    ],
    chuxe: [
      { href: '/owner/dashboard', text: 'Tổng quan' },
      { href: '/owner/vehicles', text: 'Xe của tôi' },
      { href: '/owner/availability', text: 'Lịch trống' },
      { href: '/owner/contracts', text: 'Hợp đồng' },
      { href: '/owner/disputes', text: 'Tranh chấp' },
      { href: '#logout', text: 'Đăng xuất' },
    ],
    admin: [
      { href: '/admin/dashboard', text: 'Dashboard' },
      { href: '/admin/users', text: 'Người dùng' },
      { href: '/admin/vehicles', text: 'Xe' },
      { href: '/admin/bookings', text: 'Booking' },
      { href: '/admin/contracts', text: 'Hợp đồng' },
      { href: '/admin/disputes', text: 'Tranh chấp' },
      { href: '/finance', text: 'Tài chính/Chuỗi' },
      { href: '/admin/debug', text: 'Logs' },
      { href: '#logout', text: 'Đăng xuất' },
    ],
  };
  return links[role] || links.guest;
}

function bindLogout(anchor) {
  anchor.addEventListener('click', async (e) => {
    e.preventDefault();
    try {
      await requestJson('POST', `${getApiBase()}/auth/logout`, {});
    } catch (_error) {}
    clearToken();
    window.location.href = '/login';
  });
}

function maskCccd(cccd) {
  const value = String(cccd || '').trim();
  if (!value) return '';
  if (value.length <= 4) return value;
  return `${'*'.repeat(Math.max(value.length - 4, 0))}${value.slice(-4)}`;
}

function pickPrimaryWallet(wallets) {
  const list = Array.isArray(wallets) ? wallets : [];
  if (!list.length) return null;
  return list.find((w) => String(w?.status || '').toLowerCase() === 'active') || list[0];
}

function ensureProfileRoot() {
  let root = document.getElementById('userProfileRoot');
  if (root) return root;
  root = document.createElement('div');
  root.id = 'userProfileRoot';
  document.body.appendChild(root);
  return root;
}

function closeProfileModal() {
  const root = document.getElementById('userProfileRoot');
  if (root) root.innerHTML = '';
}

function openProfileModal(session) {
  const user = session?.user || {};
  const wallets = Array.isArray(session?.wallets) ? session.wallets : [];
  const primaryWallet = pickPrimaryWallet(wallets);
  const role = String(user?.vaiTro || '').trim() || 'guest';
  const root = ensureProfileRoot();
  root.innerHTML = `
    <div class="profile-overlay">
      <div class="profile-card">
        <div class="profile-header">
          <h3>Thông tin người dùng</h3>
          <button id="profileCloseBtn" type="button" class="profile-close" aria-label="Đóng">×</button>
        </div>
        <div class="profile-grid">
          <div class="kv"><span>Họ tên</span><strong>${escapeHtml(user?.hoTen || '')}</strong></div>
          <div class="kv"><span>Email</span><strong>${escapeHtml(user?.email || '')}</strong></div>
          <div class="kv"><span>Số điện thoại</span><strong>${escapeHtml(user?.soDienThoai || '')}</strong></div>
          <div class="kv"><span>Vai trò</span><strong>${statusBadge(role)}</strong></div>
          <div class="kv"><span>Trạng thái</span><strong>${statusBadge(user?.trangThai || '')}</strong></div>
          <div class="kv"><span>Địa chỉ</span><strong>${escapeHtml(user?.diaChi || '')}</strong></div>
          <div class="kv"><span>CCCD</span><strong>${escapeHtml(maskCccd(user?.cccd))}</strong></div>
          <div class="kv"><span>Điểm đánh giá</span><strong>${escapeHtml(String(user?.diemDanhGiaTb ?? '0'))}</strong></div>
          <div class="kv"><span>Lần đăng nhập cuối</span><strong>${escapeHtml(formatDate(user?.lanDangNhapCuoi || ''))}</strong></div>
        </div>
        <h4>Ví người dùng</h4>
        ${
          primaryWallet
            ? `
              <div class="wallet-panel">
                <div class="wallet-row"><span>Địa chỉ</span><strong>${escapeHtml(primaryWallet.address || '')}</strong></div>
                <div class="wallet-row"><span>Trạng thái</span><strong>${statusBadge(primaryWallet.status || '')}</strong></div>
                <div class="wallet-row"><span>Loại ví</span><strong>${escapeHtml(primaryWallet.wallettype || primaryWallet.walletType || '')}</strong></div>
                <div class="wallet-row"><span>Số dư</span><strong>${escapeHtml(formatMoney(primaryWallet.balance || 0))}</strong></div>
                <div class="wallet-row"><span>Đang khóa</span><strong>${escapeHtml(formatMoney(primaryWallet.lockedbalance || primaryWallet.lockedBalance || 0))}</strong></div>
                <div class="wallet-row"><span>Lần sync</span><strong>${escapeHtml(formatDate(primaryWallet.syncat || primaryWallet.syncAt || ''))}</strong></div>
                <button type="button" class="btn-link secondary" id="copyWalletAddressBtn">Copy địa chỉ ví</button>
              </div>
            `
            : '<p class="note">Chưa có ví liên kết cho tài khoản này.</p>'
        }
      </div>
    </div>
  `;
  document.getElementById('profileCloseBtn')?.addEventListener('click', closeProfileModal);
  document.getElementById('copyWalletAddressBtn')?.addEventListener('click', async () => {
    const address = primaryWallet?.address || '';
    if (!address) return;
    try {
      await navigator.clipboard.writeText(address);
      toast('Đã copy địa chỉ ví.', 'success');
    } catch (_error) {
      toast('Không thể copy địa chỉ ví trên trình duyệt này.', 'error');
    }
  });
}

function buildNav(role, session = null) {
  const nav = document.getElementById('topNav');
  if (nav) {
    nav.innerHTML = '';
    navLinksByRole(role).forEach((item) => {
      const a = document.createElement('a');
      a.href = item.href;
      a.textContent = item.text;
      if (item.href === '#logout') bindLogout(a);
      nav.appendChild(a);
    });
  }

  const sideNav = document.getElementById('sideNav');
  if (sideNav) {
    const items = navLinksByRole(role)
      .filter((item) => item.href.startsWith('/'))
      .map((item) => `<a href="${item.href}">${escapeHtml(item.text)}</a>`)
      .join('');
    sideNav.innerHTML = `<div class="side-title">Điều hướng</div>${items}`;
  }

  const userMeta = document.getElementById('userMeta');
  if (userMeta && session?.user) {
    const user = session.user;
    const roleLabel = normalizeRole(user.vaiTro) || 'guest';
    const wallets = Array.isArray(session.wallets) ? session.wallets : [];
    const primaryWallet = pickPrimaryWallet(wallets);
    userMeta.innerHTML = `
      <span>${escapeHtml(user.hoTen || 'Người dùng')}</span>
      <span class="badge neutral">${escapeHtml(roleLabel)}</span>
      <span class="badge ${user.trangThai === 'hoatDong' ? 'ok' : 'danger'}">${escapeHtml(user.trangThai || '')}</span>
      <span class="badge neutral">Ví: ${escapeHtml(formatMoney(primaryWallet?.balance || 0))}</span>
      <button type="button" class="btn-link secondary profile-btn" id="openUserProfileBtn">Thông tin người dùng</button>
    `;
    document.getElementById('openUserProfileBtn')?.addEventListener('click', () => openProfileModal(session));
  }
}

async function guardPage({ guestOnly = false, roles = [] } = {}) {
  const session = await getSession(false);
  const role = normalizeRole(session?.user?.vaiTro) || 'guest';
  buildNav(role, session);

  if (guestOnly && role !== 'guest') {
    redirectByRole(role);
    return null;
  }

  if (!guestOnly && roles.length && !roles.includes(role)) {
    if (role === 'guest') {
      window.location.href = '/login';
      return null;
    }
    redirectByRole(role);
    return null;
  }

  return session;
}

function renderSelect(targetId, items, valueKey, labelBuilder, placeholder = 'Chọn') {
  const select = document.getElementById(targetId);
  if (!select) return;
  const options = [`<option value="">${escapeHtml(placeholder)}</option>`];
  (items || []).forEach((item) => {
    const value = item?.[valueKey] ?? '';
    const label = labelBuilder ? labelBuilder(item) : String(value);
    options.push(`<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`);
  });
  select.innerHTML = options.join('');
}

function renderTable(targetId, items, columns, options = {}) {
  const target = document.getElementById(targetId);
  if (!target) return;

  if (!Array.isArray(items) || !items.length) {
    target.innerHTML = '<div class="empty-state">Chưa có dữ liệu.</div>';
    return;
  }

  const head = columns.map((col) => `<th>${escapeHtml(col.label)}</th>`).join('');
  const rows = items
    .map((item, index) => {
      const cells = columns
        .map((col) => {
          const val = col.render ? col.render(item, index) : item[col.key];
          return `<td>${val ?? ''}</td>`;
        })
        .join('');
      return `<tr data-index="${index}">${cells}</tr>`;
    })
    .join('');

  target.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>`;

  if (options.onRowClick) {
    target.querySelectorAll('tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const idx = Number(row.getAttribute('data-index') || '-1');
        if (idx >= 0 && items[idx]) options.onRowClick(items[idx], idx);
      });
    });
  }
}

function setRequiredMarkers() {
  document.querySelectorAll('label').forEach((label) => {
    const input = label.querySelector('[data-required="true"]');
    if (!input || label.querySelector('.required-mark')) return;
    const mark = document.createElement('span');
    mark.className = 'required-mark';
    mark.textContent = ' *';
    label.insertBefore(mark, input);
  });
}

function setLoading(button, loading) {
  if (!button) return;
  if (loading) {
    button.setAttribute('data-original-text', button.textContent || '');
    button.disabled = true;
    button.textContent = 'Đang xử lý...';
  } else {
    button.disabled = false;
    button.textContent = button.getAttribute('data-original-text') || button.textContent;
  }
}

function ensureToastRoot() {
  let root = document.getElementById('appToastRoot');
  if (root) return root;
  root = document.createElement('div');
  root.id = 'appToastRoot';
  root.className = 'toast-root';
  document.body.appendChild(root);
  return root;
}

function toast(text, type = 'info', timeoutMs = 2600) {
  if (!text) return;
  const root = ensureToastRoot();
  const node = document.createElement('div');
  node.className = `toast ${type}`;
  node.innerHTML = `
    <span class="toast-label">${escapeHtml(type.toUpperCase())}</span>
    <span class="toast-text">${escapeHtml(text)}</span>
    <button type="button" class="toast-close" aria-label="Đóng">×</button>
  `;
  root.appendChild(node);
  node.querySelector('.toast-close')?.addEventListener('click', () => node.remove());
  window.setTimeout(() => {
    node.classList.add('hide');
    window.setTimeout(() => node.remove(), 180);
  }, timeoutMs);
}

window.App = {
  getApiBase,
  getToken,
  setToken,
  clearToken,
  requestJson,
  showMessage,
  requireValue,
  getSession,
  guardPage,
  renderTable,
  renderSelect,
  redirectByRole,
  normalizeRole,
  formatDate,
  formatMoney,
  statusBadge,
  escapeHtml,
  setRequiredMarkers,
  setLoading,
  toast,
};
