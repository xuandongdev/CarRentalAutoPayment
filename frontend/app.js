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

async function requestJson(method, url, body, token = '', extraHeaders = {}) {
  const headers = { 'Content-Type': 'application/json', ...(extraHeaders || {}) };
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

function hasEthereumProvider() {
  return !!window.ethereum;
}

async function connectMetaMask() {
  if (!hasEthereumProvider()) {
    throw new Error('Không tìm thấy MetaMask. Vui lòng cài extension MetaMask trước.');
  }
  const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
  const address = String(accounts?.[0] || '').trim();
  if (!address) throw new Error('Không lấy được địa chỉ ví từ MetaMask.');
  const chainHex = await window.ethereum.request({ method: 'eth_chainId' });
  const chainId = Number.parseInt(String(chainHex || '0x1'), 16) || 1;
  return { address, chainId };
}

async function signWalletMessage(walletAddress, message) {
  if (!hasEthereumProvider()) throw new Error('Không tìm thấy MetaMask.');
  return window.ethereum.request({
    method: 'personal_sign',
    params: [message, walletAddress],
  });
}

async function startWalletChallenge({ walletAddress, chainId, purpose }) {
  return requestJson('POST', `${getApiBase()}/auth/wallet/challenge`, {
    walletAddress,
    chainId,
    purpose,
  });
}

async function verifyWalletChallenge({ challengeId, walletAddress, nonce, message, signature, purpose }) {
  return requestJson('POST', `${getApiBase()}/auth/wallet/verify`, {
    challengeId,
    walletAddress,
    nonce,
    message,
    signature,
    purpose,
  });
}

async function loginWithWallet() {
  const { address, chainId } = await connectMetaMask();
  const challenge = await startWalletChallenge({ walletAddress: address, chainId, purpose: 'login_wallet' });
  const signature = await signWalletMessage(address, challenge.message);
  return verifyWalletChallenge({
    challengeId: challenge.id || challenge.challengeId || null,
    walletAddress: challenge.walletAddress || address,
    nonce: challenge.nonce,
    message: challenge.message,
    signature,
    purpose: 'login_wallet',
  });
}

async function linkWalletForCurrentUser() {
  const { address, chainId } = await connectMetaMask();
  const challenge = await requestJson('POST', `${getApiBase()}/wallet/link/challenge`, {
    walletAddress: address,
    chainId,
    purpose: 'link_wallet',
  });
  const signature = await signWalletMessage(address, challenge.message);
  return requestJson('POST', `${getApiBase()}/wallet/link/verify`, {
    challengeId: challenge.id || challenge.challengeId || null,
    walletAddress: challenge.walletAddress || address,
    nonce: challenge.nonce,
    message: challenge.message,
    signature,
    purpose: 'link_wallet',
  });
}

async function performStepUpAuth() {
  const { address, chainId } = await connectMetaMask();
  const challenge = await requestJson('POST', `${getApiBase()}/auth/wallet/step-up/challenge`, {
    walletAddress: address,
    chainId,
    purpose: 'step_up',
  });
  const signature = await signWalletMessage(address, challenge.message);
  return requestJson('POST', `${getApiBase()}/auth/wallet/step-up/verify`, {
    challengeId: challenge.id || challenge.challengeId || null,
    walletAddress: challenge.walletAddress || address,
    nonce: challenge.nonce,
    message: challenge.message,
    signature,
    purpose: 'step_up',
  });
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
    logoutCurrentSession();
  });
}

async function logoutCurrentSession() {
  try {
    await requestJson('POST', `${getApiBase()}/auth/logout`, {});
  } catch (_error) {}
  clearToken();
  window.location.href = '/login';
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

let profileEscHandler = null;

function fallbackText(value, placeholder = 'Chưa cập nhật') {
  const text = String(value ?? '').trim();
  return text || placeholder;
}

function formatDateTime(value, placeholder = 'Chưa có dữ liệu') {
  const text = String(value ?? '').trim();
  if (!text) return placeholder;
  const formatted = formatDate(text);
  return formatted || placeholder;
}

function truncateAddress(value, start = 8, end = 6) {
  const text = String(value ?? '').trim();
  if (!text) return '';
  if (text.length <= start + end + 3) return text;
  return `${text.slice(0, start)}...${text.slice(-end)}`;
}

function roleMeta(role) {
  const key = normalizeRole(role);
  const map = {
    khach: { label: 'Khách', cls: 'neutral' },
    chuxe: { label: 'Chủ xe', cls: 'pending' },
    admin: { label: 'Admin', cls: 'ok' },
  };
  return map[key] || { label: fallbackText(role, 'Chưa cập nhật'), cls: 'neutral' };
}

function userStatusMeta(status) {
  const key = String(status || '').trim().toLowerCase();
  const map = {
    hoatdong: { label: 'Hoạt động', cls: 'ok' },
    tamkhoa: { label: 'Tạm khóa', cls: 'pending' },
    ngunghoatdong: { label: 'Ngừng hoạt động', cls: 'danger' },
  };
  return map[key] || { label: fallbackText(status, 'Chưa cập nhật'), cls: 'neutral' };
}

function walletStatusMeta(status) {
  const key = String(status || '').trim().toLowerCase();
  const map = {
    active: { label: 'Active', cls: 'ok' },
    locked: { label: 'Locked', cls: 'pending' },
    inactive: { label: 'Inactive', cls: 'danger' },
  };
  return map[key] || { label: fallbackText(status, 'Chưa cập nhật'), cls: 'neutral' };
}

function walletTypeLabel(value) {
  const key = String(value || '').trim().toLowerCase();
  if (key === 'user') return 'User';
  if (key === 'system') return 'System';
  return fallbackText(value, 'Chưa cập nhật');
}

function ensureProfileRoot() {
  let root = document.getElementById('userProfileRoot');
  if (root) return root;
  root = document.createElement('div');
  root.id = 'userProfileRoot';
  document.body.appendChild(root);
  return root;
}

function normalizePathname(pathname = window.location.pathname || '/') {
  const path = String(pathname || '/').split('?')[0].replace(/\/+$/, '');
  return path || '/';
}

function isAdminShellPage(role) {
  return role === 'admin' && !!document.querySelector('.admin-shell');
}

function sidebarActive(href) {
  const current = normalizePathname(window.location.pathname);
  const target = normalizePathname(href);
  if (target === '/finance') {
    return current === '/finance' || current.startsWith('/finance/contracts/') || current === '/admin/chain';
  }
  if (target === '/chain') {
    return current === '/chain' || current === '/blockchain' || current === '/admin/chain';
  }
  return current === target;
}

function adminPageMeta(pathname = window.location.pathname) {
  const path = normalizePathname(pathname);
  const map = {
    '/admin/dashboard': {
      topbarTitle: 'Dashboard',
      breadcrumb: 'Admin / Dashboard',
      pageTitle: 'Bảng điều khiển quản trị',
      subtitle: 'Theo dõi nhanh vận hành hệ thống thuê xe và thanh toán tự động.',
    },
    '/admin/users': {
      topbarTitle: 'Người dùng',
      breadcrumb: 'Admin / Người dùng',
      pageTitle: 'Quản lý người dùng',
      subtitle: 'Quản lý tài khoản người dùng, vai trò và trạng thái hoạt động.',
    },
    '/admin/vehicles': {
      topbarTitle: 'Xe',
      breadcrumb: 'Admin / Xe',
      pageTitle: 'Quản lý xe',
      subtitle: 'Duyệt trạng thái xe, theo dõi khả dụng và vận hành đội xe.',
    },
    '/admin/bookings': {
      topbarTitle: 'Booking',
      breadcrumb: 'Admin / Booking',
      pageTitle: 'Quản lý booking',
      subtitle: 'Theo dõi yêu cầu đặt xe và trạng thái xác nhận.',
    },
    '/admin/contracts': {
      topbarTitle: 'Hợp đồng',
      breadcrumb: 'Admin / Hợp đồng',
      pageTitle: 'Quản lý hợp đồng',
      subtitle: 'Kiểm soát vòng đời hợp đồng thuê và thanh toán liên quan.',
    },
    '/admin/disputes': {
      topbarTitle: 'Tranh chấp',
      breadcrumb: 'Admin / Tranh chấp',
      pageTitle: 'Quản lý tranh chấp',
      subtitle: 'Xử lý tình huống hư hại, kết luận và cập nhật quyết định.',
    },
    '/admin/debug': {
      topbarTitle: 'Logs',
      breadcrumb: 'Admin / Logs',
      pageTitle: 'Logs và debug',
      subtitle: 'Kiểm tra dữ liệu log nội bộ để hỗ trợ vận hành và điều tra sự cố.',
    },
    '/admin/chain': {
      topbarTitle: 'Tài chính/Chuỗi',
      breadcrumb: 'Admin / Tài chính / Chuỗi',
      pageTitle: 'Chuỗi và đồng bộ',
      subtitle: 'Theo dõi dữ liệu blockchain nội bộ và trạng thái đồng bộ hệ thống.',
    },
    '/finance': {
      topbarTitle: 'Tài chính/Chuỗi',
      breadcrumb: 'Admin / Tài chính / Chuỗi',
      pageTitle: 'Tài chính và chuỗi',
      subtitle: 'Giám sát dòng tiền, giao dịch và cảnh báo vận hành tài chính.',
    },
    '/chain': {
      topbarTitle: 'Tài chính/Chuỗi',
      breadcrumb: 'Admin / Tài chính / Chuỗi',
      pageTitle: 'Blockchain explorer nội bộ',
      subtitle: 'Quan sát dữ liệu chuỗi theo ngữ cảnh vận hành admin.',
    },
    '/blockchain': {
      topbarTitle: 'Tài chính/Chuỗi',
      breadcrumb: 'Admin / Tài chính / Chuỗi',
      pageTitle: 'Blockchain explorer nội bộ',
      subtitle: 'Quan sát dữ liệu chuỗi theo ngữ cảnh vận hành admin.',
    },
  };
  if (path.startsWith('/finance/contracts/')) return map['/finance'];
  return map[path] || {
    topbarTitle: 'Admin',
    breadcrumb: 'Admin',
    pageTitle: 'Admin workspace',
    subtitle: 'Thao tác quản trị theo module.',
  };
}

function decorateAdminTopbar(meta) {
  const topbar = document.querySelector('.admin-topbar');
  if (!topbar) return;
  const heading = topbar.querySelector('h1');
  if (heading) heading.textContent = meta.topbarTitle;
  let breadcrumb = topbar.querySelector('.topbar-breadcrumb');
  if (!breadcrumb) {
    breadcrumb = document.createElement('p');
    breadcrumb.className = 'topbar-breadcrumb';
    topbar.insertBefore(breadcrumb, heading || topbar.firstChild);
  }
  breadcrumb.textContent = meta.breadcrumb;
}

function ensureAdminPageHeader(meta) {
  const content = document.querySelector('.admin-content');
  if (!content) return;
  let header = content.querySelector('.admin-page-header');
  if (!header) {
    header = document.createElement('section');
    header.className = 'admin-page-header';
    header.innerHTML = '<h2 id="pageHeaderTitle"></h2><p id="pageHeaderSubtitle"></p>';
    content.prepend(header);
  }
  const title = header.querySelector('#pageHeaderTitle');
  const subtitle = header.querySelector('#pageHeaderSubtitle');
  if (title) title.textContent = meta.pageTitle;
  if (subtitle) subtitle.textContent = meta.subtitle;
}

function initInspectorToggle() {
  const shell = document.querySelector('.admin-shell');
  const panel = document.querySelector('.inspector-panel');
  if (!shell || !panel) return;

  let header = panel.querySelector('.inspector-header');
  if (!header) {
    const title = panel.querySelector('#inspectorTitle');
    if (!title) return;
    header = document.createElement('div');
    header.className = 'inspector-header';
    panel.insertBefore(header, title);
    header.appendChild(title);
  }

  let toggle = panel.querySelector('#inspectorToggleBtn');
  if (!toggle) {
    toggle = document.createElement('button');
    toggle.id = 'inspectorToggleBtn';
    toggle.type = 'button';
    toggle.className = 'inspector-toggle-btn';
    header.appendChild(toggle);
  }

  let hint = panel.querySelector('.inspector-hint');
  if (!hint) {
    hint = document.createElement('p');
    hint.className = 'inspector-hint';
    hint.textContent = 'Panel phụ trợ để xem JSON raw, metadata và log theo bản ghi đang chọn.';
    header.insertAdjacentElement('afterend', hint);
  }

  const updateLabel = () => {
    const collapsed = shell.classList.contains('inspector-collapsed');
    toggle.textContent = collapsed ? 'Mở' : 'Thu gọn';
    toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  };

  if (!toggle.dataset.bound) {
    toggle.addEventListener('click', () => {
      shell.classList.toggle('inspector-collapsed');
      updateLabel();
    });
    toggle.dataset.bound = '1';
  }

  updateLabel();
}

function closeProfileModal() {
  if (profileEscHandler) {
    document.removeEventListener('keydown', profileEscHandler);
    profileEscHandler = null;
  }
  const root = document.getElementById('userProfileRoot');
  if (root) root.innerHTML = '';
}

function openProfileModal(session) {
  const user = session?.user || {};
  const wallets = Array.isArray(session?.wallets) ? session.wallets : [];
  const primaryWallet = pickPrimaryWallet(wallets);
  const role = String(user?.vaiTro || '').trim() || 'guest';
  const roleInfo = roleMeta(role);
  const userStatus = userStatusMeta(user?.trangThai);
  const walletStatus = walletStatusMeta(primaryWallet?.status);
  const walletAddress = String(primaryWallet?.address || '').trim();
  const walletAddressDisplay = walletAddress ? truncateAddress(walletAddress) : 'Chưa liên kết ví';
  const walletSyncAt = primaryWallet?.syncat || primaryWallet?.syncAt || '';
  const walletType = primaryWallet?.wallettype || primaryWallet?.walletType || '';
  const profileFields = [
    { label: 'Họ tên', value: fallbackText(user?.hoTen), important: true },
    { label: 'Email', value: fallbackText(user?.email), long: true },
    { label: 'Số điện thoại', value: fallbackText(user?.soDienThoai) },
    { label: 'Địa chỉ', value: fallbackText(user?.diaChi), long: true },
    { label: 'CCCD', value: fallbackText(maskCccd(user?.cccd), 'Chưa cập nhật') },
    { label: 'Điểm đánh giá', value: fallbackText(user?.diemDanhGiaTb, '0') },
    { label: 'Lần đăng nhập cuối', value: formatDateTime(user?.lanDangNhapCuoi), long: true },
  ];
  const root = ensureProfileRoot();
  root.innerHTML = `
    <div class="profile-overlay" id="profileOverlay">
      <div class="profile-card" role="dialog" aria-modal="true" aria-labelledby="userProfileTitle">
        <div class="profile-header">
          <div>
            <h3 id="userProfileTitle">Thông tin người dùng</h3>
            <p class="profile-subtitle">Thông tin hồ sơ và ví liên kết của tài khoản hiện tại.</p>
          </div>
          <button id="profileCloseBtn" type="button" class="profile-close" aria-label="Đóng">×</button>
        </div>
        <div class="profile-body">
          <section class="profile-section">
            <h4>Hồ sơ người dùng</h4>
            <div class="profile-highlight-row">
              <div class="profile-highlight">
                <span class="info-label">Vai trò</span>
                <div class="info-value"><span class="badge ${roleInfo.cls} profile-badge">${escapeHtml(roleInfo.label)}</span></div>
              </div>
              <div class="profile-highlight">
                <span class="info-label">Trạng thái</span>
                <div class="info-value"><span class="badge ${userStatus.cls} profile-badge">${escapeHtml(userStatus.label)}</span></div>
              </div>
            </div>
            <div class="profile-grid">
              ${profileFields
                .map(
                  (field) => `
                  <div class="info-item ${field.important ? 'info-item-important' : ''}">
                    <span class="info-label">${escapeHtml(field.label)}</span>
                    <div class="info-value ${field.long ? 'text-break' : ''}" title="${escapeHtml(field.value)}">${escapeHtml(field.value)}</div>
                  </div>
                `
                )
                .join('')}
            </div>
          </section>

          <section class="profile-section">
            <h4>Ví người dùng</h4>
            ${
              primaryWallet
                ? `
                <div class="wallet-summary">
                  <span class="info-label">Số dư khả dụng</span>
                  <div class="wallet-balance">${escapeHtml(formatMoney(primaryWallet.balance || 0))}</div>
                </div>
                <div class="wallet-panel">
                  <div class="wallet-row wallet-address-row">
                    <span class="wallet-label">Địa chỉ ví</span>
                    <div class="wallet-value wallet-address">
                      <span class="wallet-address-text" title="${escapeHtml(walletAddress || 'Chưa liên kết ví')}">${escapeHtml(walletAddressDisplay)}</span>
                      <button type="button" class="wallet-copy-btn" id="copyWalletAddressBtn" aria-label="Sao chép địa chỉ ví">Copy</button>
                      <span class="wallet-copy-feedback" id="walletCopyFeedback" aria-live="polite"></span>
                    </div>
                  </div>
                  <div class="wallet-row">
                    <span class="wallet-label">Trạng thái</span>
                    <div class="wallet-value"><span class="badge ${walletStatus.cls} profile-badge">${escapeHtml(walletStatus.label)}</span></div>
                  </div>
                  <div class="wallet-row">
                    <span class="wallet-label">Loại ví</span>
                    <div class="wallet-value">${escapeHtml(walletTypeLabel(walletType))}</div>
                  </div>
                  <div class="wallet-row">
                    <span class="wallet-label">Số dư đang khóa</span>
                    <div class="wallet-value">${escapeHtml(formatMoney(primaryWallet.lockedbalance || primaryWallet.lockedBalance || 0))}</div>
                  </div>
                  <div class="wallet-row">
                    <span class="wallet-label">Lần đồng bộ gần nhất</span>
                    <div class="wallet-value text-break" title="${escapeHtml(formatDateTime(walletSyncAt))}">${escapeHtml(formatDateTime(walletSyncAt))}</div>
                  </div>
                </div>
              `
                : `
                <div class="wallet-empty-card">
                  <strong>Chưa liên kết ví</strong>
                  <p class="note">Tài khoản này chưa có ví khả dụng để hiển thị số dư và trạng thái.</p>
                </div>
              `
            }
            <div class="wallet-inline-actions">
              <button type="button" class="btn-link secondary" id="linkWalletBtn">Liên kết ví MetaMask</button>
              ${
                walletAddress
                  ? '<button type="button" class="btn-link danger" id="unlinkWalletBtn">Gỡ liên kết ví hiện tại</button>'
                  : ''
              }
            </div>
          </section>
        </div>
        <div class="profile-footer">
          <button type="button" class="btn-link secondary profile-close-btn" id="profileFooterCloseBtn">Đóng</button>
        </div>
      </div>
    </div>
  `;
  document.getElementById('profileCloseBtn')?.addEventListener('click', closeProfileModal);
  document.getElementById('profileFooterCloseBtn')?.addEventListener('click', closeProfileModal);
  document.getElementById('profileOverlay')?.addEventListener('click', (event) => {
    if (event.target === event.currentTarget) closeProfileModal();
  });
  profileEscHandler = (event) => {
    if (event.key === 'Escape') closeProfileModal();
  };
  document.addEventListener('keydown', profileEscHandler);
  document.getElementById('copyWalletAddressBtn')?.addEventListener('click', async () => {
    const address = walletAddress;
    const feedback = document.getElementById('walletCopyFeedback');
    if (!address) return;
    try {
      await navigator.clipboard.writeText(address);
      if (feedback) {
        feedback.textContent = 'Đã sao chép';
        window.setTimeout(() => { if (feedback) feedback.textContent = ''; }, 1800);
      }
      toast('Đã sao chép địa chỉ ví.', 'success');
    } catch (_error) {
      toast('Không thể copy địa chỉ ví trên trình duyệt này.', 'error');
    }
  });
  document.getElementById('linkWalletBtn')?.addEventListener('click', async () => {
    const btn = document.getElementById('linkWalletBtn');
    try {
      setLoading(btn, true);
      await linkWalletForCurrentUser();
      toast('Liên kết ví thành công.', 'success');
      closeProfileModal();
      const session = await getSession(false);
      buildNav(normalizeRole(session?.user?.vaiTro) || 'guest', session);
    } catch (error) {
      toast(error?.message || 'Liên kết ví thất bại.', 'error');
    } finally {
      setLoading(btn, false);
    }
  });
  document.getElementById('unlinkWalletBtn')?.addEventListener('click', async () => {
    const btn = document.getElementById('unlinkWalletBtn');
    try {
      setLoading(btn, true);
      await requestJson('POST', `${getApiBase()}/auth/wallet/unlink`, { walletAddress });
      toast('Đã gỡ liên kết ví.', 'success');
      closeProfileModal();
      const session = await getSession(false);
      buildNav(normalizeRole(session?.user?.vaiTro) || 'guest', session);
    } catch (error) {
      toast(error?.message || 'Không thể gỡ liên kết ví.', 'error');
    } finally {
      setLoading(btn, false);
    }
  });
}

function buildNav(role, session = null) {
  const adminShell = isAdminShellPage(role);
  const meta = adminShell ? adminPageMeta() : null;
  const nav = document.getElementById('topNav');
  if (nav && !adminShell) {
    nav.innerHTML = '';
    navLinksByRole(role).forEach((item) => {
      const a = document.createElement('a');
      a.href = item.href;
      a.textContent = item.text;
      if (item.href === '#logout') bindLogout(a);
      nav.appendChild(a);
    });
  } else if (nav && adminShell) {
    nav.remove();
  }

  const sideNav = document.getElementById('sideNav');
  if (sideNav) {
    const items = navLinksByRole(role)
      .filter((item) => item.href.startsWith('/'))
      .map((item) => `<a href="${item.href}" class="${sidebarActive(item.href) ? 'active' : ''}">${escapeHtml(item.text)}</a>`)
      .join('');
    sideNav.innerHTML = `<div class="side-title">Điều hướng</div>${items}`;
  }

  const userMeta = document.getElementById('userMeta');
  if (userMeta && session?.user) {
    const user = session.user;
    const ownerMode = role === 'chuxe';
    const roleLabel = normalizeRole(user.vaiTro) || 'guest';
    const wallets = Array.isArray(session.wallets) ? session.wallets : [];
    const primaryWallet = pickPrimaryWallet(wallets);
    userMeta.classList.toggle('user-meta-owner', ownerMode);
    userMeta.innerHTML = `
      <span>${escapeHtml(user.hoTen || 'Người dùng')}</span>
      <span class="badge neutral">${escapeHtml(roleLabel)}</span>
      <span class="badge ${user.trangThai === 'hoatDong' ? 'ok' : 'danger'}">${escapeHtml(user.trangThai || '')}</span>
      <span class="badge neutral">Ví: ${escapeHtml(formatMoney(primaryWallet?.balance || 0))}</span>
      <button type="button" class="btn-link secondary profile-btn ${ownerMode ? 'compact' : ''}" id="openUserProfileBtn">${ownerMode ? 'Hồ sơ' : 'Thông tin người dùng'}</button>
      ${adminShell ? '<button type="button" class="btn-link danger profile-btn" id="topbarLogoutBtn">Đăng xuất</button>' : ''}
    `;
    document.getElementById('openUserProfileBtn')?.addEventListener('click', () => openProfileModal(session));
    document.getElementById('topbarLogoutBtn')?.addEventListener('click', () => logoutCurrentSession());
  }

  if (adminShell && meta) {
    decorateAdminTopbar(meta);
    ensureAdminPageHeader(meta);
    initInspectorToggle();
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
  hasEthereumProvider,
  connectMetaMask,
  signWalletMessage,
  startWalletChallenge,
  verifyWalletChallenge,
  loginWithWallet,
  linkWalletForCurrentUser,
  performStepUpAuth,
};
