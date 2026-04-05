const $ = (id) => document.getElementById(id);
const arr = (v) => (Array.isArray(v) ? v : []);
const gv = (r, ...k) => { for (const x of k) { if (r && r[x] !== undefined && r[x] !== null) return r[x]; } return ''; };
const j = (v) => { try { return JSON.stringify(v ?? {}, null, 2); } catch { return String(v ?? ''); } };

const vehicleDisplayStatus = (row) => gv(row, 'displaytrangthailabel', 'displayTrangThaiLabel', 'trangthai');
const vehicleCanBook = (row) => {
  const value = gv(row, 'canbook', 'canBook', null);
  return value === true || value === 'true';
};
const contractFlowStatus = (row) => gv(row, 'trangthailogical', 'trangthaihienthi', 'trangthai');

function disputePriority(row) {
  const status = String(gv(row, 'trangthai') || '');
  const amount = Number(gv(row, 'sotienphaithu') || 0);
  if (status === 'dangMo' || status === 'dangXuLy') return { label: 'Cao', cls: 'danger' };
  if (amount > 0) return { label: 'Trung bình', cls: 'pending' };
  return { label: 'Th?p', cls: 'ok' };
}

function ensureModalRoot() {
  let root = document.getElementById('appModalRoot');
  if (root) return root;
  root = document.createElement('div');
  root.id = 'appModalRoot';
  document.body.appendChild(root);
  return root;
}

function closeModal() {
  const root = document.getElementById('appModalRoot');
  if (root) root.innerHTML = '';
}

function confirmModal({ title, message, confirmText = 'Xác nh?n', danger = false }) {
  return new Promise((resolve) => {
    const root = ensureModalRoot();
    root.innerHTML = `
      <div class="modal-overlay">
        <div class="modal-card">
          <h3>${App.escapeHtml(title || 'Xác nh?n thao tác')}</h3>
          <p>${App.escapeHtml(message || '')}</p>
          <div class="modal-actions">
            <button type="button" id="modalCancelBtn" class="btn-link secondary">H?y</button>
            <button type="button" id="modalConfirmBtn" class="btn-link ${danger ? 'danger' : ''}">${App.escapeHtml(confirmText)}</button>
          </div>
        </div>
      </div>
    `;
    const done = (ok) => { closeModal(); resolve(ok); };
    document.getElementById('modalCancelBtn')?.addEventListener('click', () => done(false));
    document.getElementById('modalConfirmBtn')?.addEventListener('click', () => done(true));
  });
}

function disputeDecisionModal({ row, mode }) {
  return new Promise((resolve) => {
    const root = ensureModalRoot();
    const isDamage = mode === 'damage';
    root.innerHTML = `
      <div class="modal-overlay">
        <div class="modal-card">
          <h3>${isDamage ? 'Xác nh?n có hu h?i' : 'Xác nh?n không hu h?i'}</h3>
          <p>Tranh ch?p: <strong>${App.escapeHtml(gv(row, 'id'))}</strong></p>
          ${isDamage ? `
            <label>Chi phí duy?t
              <input id="modalApprovedCost" type="number" min="0" step="0.01" data-required="true">
            </label>
          ` : ''}
          <label>K?t lu?n
            <textarea id="modalDecisionNote" data-required="true" placeholder="Nh?p k?t lu?n x? lý"></textarea>
          </label>
          <div class="modal-actions">
            <button type="button" id="modalCancelBtn" class="btn-link secondary">H?y</button>
            <button type="button" id="modalConfirmBtn" class="btn-link ${isDamage ? 'danger' : ''}">Xác nh?n</button>
          </div>
        </div>
      </div>
    `;
    App.setRequiredMarkers();
    const done = (val) => { closeModal(); resolve(val); };
    document.getElementById('modalCancelBtn')?.addEventListener('click', () => done(null));
    document.getElementById('modalConfirmBtn')?.addEventListener('click', () => {
      try {
        const decisionNote = App.requireValue(document.getElementById('modalDecisionNote')?.value, 'Thi?u k?t lu?n');
        if (!isDamage) return done({ decisionNote });
        const approvedCost = Number(App.requireValue(document.getElementById('modalApprovedCost')?.value, 'Thi?u chi phí duy?t'));
        done({ decisionNote, approvedCost });
      } catch (e) {
        alert(e.message);
      }
    });
  });
}

function setInspectorEmpty(message = 'Ch?n m?t b?n ghi d? xem JSON và metadata.') {
  if ($('inspectorTitle')) $('inspectorTitle').textContent = 'JSON Inspector';
  if ($('inspectorTabs')) $('inspectorTabs').innerHTML = '';
  if ($('inspectorBody')) $('inspectorBody').innerHTML = `<div class="empty-state inspector-empty">${App.escapeHtml(message)}</div>`;
}

function setInspector(title, data, events = [], tx = []) {
  if (!data) return setInspectorEmpty();
  if ($('inspectorTitle')) $('inspectorTitle').textContent = title || 'JSON Inspector';
  if ($('inspectorTabs')) {
    $('inspectorTabs').innerHTML = '<button class="tab-btn active" data-t="raw">Raw JSON</button><button class="tab-btn" data-t="events">Events</button><button class="tab-btn" data-t="tx">Transactions</button>';
    const render = (t) => {
      if (!$('inspectorBody')) return;
      if (t === 'events') return ($('inspectorBody').innerHTML = `<pre>${App.escapeHtml(j(events))}</pre>`);
      if (t === 'tx') return ($('inspectorBody').innerHTML = `<pre>${App.escapeHtml(j(tx))}</pre>`);
      $('inspectorBody').innerHTML = `<pre>${App.escapeHtml(j(data))}</pre>`;
    };
    render('raw');
    $('inspectorTabs').querySelectorAll('.tab-btn').forEach((b) => b.onclick = () => {
      $('inspectorTabs').querySelectorAll('.tab-btn').forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      render(b.getAttribute('data-t'));
    });
  }
}

function setDetail(id, row) {
  if (!$(id)) return;
  if (!row) return ($(id).innerHTML = '<div class="empty-state">Ch?n b?n ghi d? xem chi ti?t.</div>');
  const html = Object.entries(row).slice(0, 18).map(([k, v]) => `<div class="kv"><span>${App.escapeHtml(k)}</span><strong>${App.escapeHtml(typeof v === 'object' ? JSON.stringify(v) : String(v))}</strong></div>`).join('');
  $(id).innerHTML = `<div class="detail-grid">${html}</div>`;
}

async function initLanding() {
  await App.guardPage();
  try {
    const data = await App.requestJson('GET', `${App.getApiBase()}/api/vehicles/public`, null, '');
    const all = arr(data.items);
    const ready = all.filter((r) => vehicleCanBook(r));
    const sorted = [...ready, ...all.filter((r) => !vehicleCanBook(r))];
    const path = String(window.location.pathname || '/').split('?')[0];
    const isHome = path === '/' || path === '/home' || path === '/frontend/index.html';
    const prioritized = isHome ? sorted.slice(0, 6) : sorted;
    const root = $('featuredVehicles');
    if (root) {
      if (!prioritized.length) {
        root.innerHTML = '<div class="empty-state">Hi?n chua có xe công khai n?i b?t. Vui lòng quay l?i sau.</div>';
      } else {
        root.innerHTML = prioritized.map((row) => {
          const brand = App.escapeHtml(gv(row, 'hangxe') || 'Chua c?p nh?t');
          const model = App.escapeHtml(gv(row, 'dongxe') || 'Chua c?p nh?t');
          const plate = App.escapeHtml(gv(row, 'bienso') || gv(row, 'id') || 'Chua c?p nh?t');
          const description = App.escapeHtml(gv(row, 'mota') || `${gv(row, 'hangxe') || 'Xe'} ${gv(row, 'dongxe') || ''}`.trim());
          const statusHtml = App.statusBadge(vehicleDisplayStatus(row) || 'Chua c?p nh?t');
          const price = App.escapeHtml(App.formatMoney(gv(row, 'giatheongay') || 0));
          const imageUrl = gv(row, 'image', 'imageurl', 'thumbnail', 'photo', 'anhxe');
          const imageHtml = imageUrl
            ? `<img src="${App.escapeHtml(String(imageUrl))}" alt="${brand} ${model}" loading="lazy" onerror="this.parentElement.innerHTML='<div class=&quot;vehicle-image-fallback&quot;>Không có ?nh</div>';">`
            : '<div class="vehicle-image-fallback">Không có ?nh</div>';
          return `
            <article class="vehicle-card">
              <div class="vehicle-image">${imageHtml}</div>
              <div class="vehicle-card-body">
                <div class="vehicle-top-row">
                  <h4>${brand} ${model}</h4>
                  ${statusHtml}
                </div>
                <p class="vehicle-ident">Bi?n s?: <strong>${plate}</strong></p>
                <p class="vehicle-desc">${description}</p>
                <div class="vehicle-bottom-row">
                  <div class="vehicle-price">${price} / ngày</div>
                  <a class="vehicle-link" href="/vehicles">Xem công khai</a>
                </div>
              </div>
            </article>
          `;
        }).join('');
      }
    }
  } catch (e) { App.showMessage('landingMessage', e.message, 'error'); }
}

async function requireStepUpChallengeHeader() {
  const verified = await App.performStepUpAuth();
  const challengeId = verified?.challenge?.id || verified?.challengeId;
  if (!challengeId) throw new Error('Không l?y du?c step-up challenge id sau khi xác th?c ví.');
  return { 'X-Step-Up-Challenge-Id': challengeId };
}

async function initLogin() {
  await App.guardPage({ guestOnly: true });
  const tabs = Array.from(document.querySelectorAll('[data-auth-tab]'));
  const panes = Array.from(document.querySelectorAll('[data-auth-pane]'));
  const switchTab = (target) => {
    tabs.forEach((tab) => {
      const active = tab.getAttribute('data-auth-tab') === target;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    panes.forEach((pane) => pane.classList.toggle('active', pane.getAttribute('data-auth-pane') === target));
  };
  tabs.forEach((tab) => tab.addEventListener('click', () => switchTab(tab.getAttribute('data-auth-tab'))));

  const passwordInput = $('password');
  $('togglePasswordBtn')?.addEventListener('click', () => {
    if (!passwordInput) return;
    passwordInput.type = passwordInput.type === 'password' ? 'text' : 'password';
  });

  const form = $('loginForm');
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    try {
      App.setLoading(btn, true);
      const data = await App.requestJson('POST', `${App.getApiBase()}/auth/login`, {
        identifier: App.requireValue($('identifier')?.value, 'Thi?u identifier'),
        password: App.requireValue($('password')?.value, 'Thi?u password'),
      }, '');
      App.setToken(data.accessToken);
      App.redirectByRole(data?.user?.vaiTro);
    } catch (e2) { App.showMessage('loginMessage', e2.message, 'error'); } finally { App.setLoading(btn, false); }
  });

  let connectedWallet = null;
  const setWalletState = (text) => {
    const box = $('walletConnectedInfo');
    if (box) box.textContent = text;
  };
  if (!App.hasEthereumProvider()) {
    setWalletState('Không phát hi?n MetaMask trên trình duy?t này.');
    App.showMessage('walletLoginMessage', 'B?n c?n cài MetaMask d? dùng dang nh?p b?ng ví.', 'error');
  }
  $('walletConnectBtn')?.addEventListener('click', async () => {
    const btn = $('walletConnectBtn');
    try {
      App.setLoading(btn, true);
      const { address, chainId } = await App.connectMetaMask();
      connectedWallet = { address, chainId };
      setWalletState(`Ðã k?t n?i: ${address} | chainId: ${chainId}`);
      $('walletSignInBtn').disabled = false;
      App.showMessage('walletLoginMessage', 'Ðã k?t n?i ví thành công. B?m "Ký d? dang nh?p".', 'success');
    } catch (error) {
      connectedWallet = null;
      $('walletSignInBtn').disabled = true;
      setWalletState('Chua k?t n?i ví.');
      App.showMessage('walletLoginMessage', error.message, 'error');
    } finally {
      App.setLoading(btn, false);
    }
  });
  $('walletSignInBtn')?.addEventListener('click', async () => {
    const btn = $('walletSignInBtn');
    try {
      if (!connectedWallet) throw new Error('Vui lòng k?t n?i MetaMask tru?c khi ký dang nh?p.');
      App.setLoading(btn, true);
      const challenge = await App.startWalletChallenge({
        walletAddress: connectedWallet.address,
        chainId: connectedWallet.chainId,
        purpose: 'login_wallet',
      });
      const signature = await App.signWalletMessage(connectedWallet.address, challenge.message);
      const verified = await App.verifyWalletChallenge({
        challengeId: challenge.id || challenge.challengeId || null,
        walletAddress: connectedWallet.address,
        nonce: challenge.nonce,
        message: challenge.message,
        signature,
        purpose: 'login_wallet',
      });
      if (!verified?.accessToken) throw new Error('Ðang nh?p ví th?t b?i, không nh?n du?c session.');
      App.setToken(verified.accessToken);
      App.redirectByRole(verified?.user?.vaiTro);
    } catch (error) {
      const message = String(error?.message || 'Ðang nh?p ví th?t b?i.');
      if (message.toLowerCase().includes('lien ket')) {
        App.showMessage('walletLoginMessage', `${message} Hãy dang nh?p tài kho?n d? liên k?t ví tru?c.`, 'error');
      } else {
        App.showMessage('walletLoginMessage', message, 'error');
      }
    } finally {
      App.setLoading(btn, false);
    }
  });
}

async function initRegister() {
  await App.guardPage({ guestOnly: true });
  const form = $('registerForm');
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    try {
      App.setLoading(btn, true);
      const password = App.requireValue($('password')?.value, 'Thi?u m?t kh?u');
      if (password !== App.requireValue($('confirmPassword')?.value, 'Thi?u xác nh?n m?t kh?u')) throw new Error('M?t kh?u không kh?p');
      await App.requestJson('POST', `${App.getApiBase()}/auth/register`, {
        hoTen: App.requireValue($('hoTen')?.value, 'Thi?u h? tên'), email: $('email')?.value?.trim() || '', soDienThoai: $('soDienThoai')?.value?.trim() || '', password,
      }, '');
      App.showMessage('registerMessage', 'Ðang ký thành công, vui lòng dang nh?p.', 'success');
    } catch (e2) { App.showMessage('registerMessage', e2.message, 'error'); } finally { App.setLoading(btn, false); }
  });
}

async function initAdminDashboard() {
  await App.guardPage({ roles: ['admin'] });
  try {
    const [overview, finance] = await Promise.all([
      App.requestJson('GET', `${App.getApiBase()}/api/overview`),
      App.requestJson('GET', `${App.getApiBase()}/api/finance/summary`),
    ]);
    $('kpiVehiclesPending').textContent = arr(overview.vehicles).filter((v) => gv(v, 'trangthai') === 'choDuyet').length;
    $('kpiBookingsPending').textContent = arr(overview.bookings).filter((v) => gv(v, 'trangthai') === 'choXacNhan').length;
    $('kpiContractsActive').textContent = arr(overview.contracts).filter((v) => gv(v, 'trangthai') === 'dangThue').length;
    $('kpiDisputesOpen').textContent = arr(overview.disputes).filter((v) => ['dangMo', 'dangXuLy'].includes(gv(v, 'trangthai'))).length;
    $('kpiTxTotal').textContent = finance.totalTransactions ?? 0;
    $('kpiSync').textContent = gv(overview, 'syncStatus') || 'unknown';

    const work = [
      ...arr(overview.vehicles).filter((v) => gv(v, 'trangthai') === 'choDuyet').map((x) => ({ type: 'vehicle', id: x.id, label: `Duy?t xe ${gv(x, 'bienso')}`, row: x })),
      ...arr(overview.disputes).filter((v) => ['dangMo', 'dangXuLy'].includes(gv(v, 'trangthai'))).map((x) => ({ type: 'dispute', id: x.id, label: `X? lý tranh ch?p ${x.id}`, row: x })),
    ];
    App.renderTable('adminWorkbenchTable', work, [
      { key: 'type', label: 'Lo?i' }, { key: 'label', label: 'Công vi?c' }, { key: 'id', label: 'ID' },
    ], { onRowClick: (x) => { setDetail('adminEntityDetail', x.row); setInspector(`Workbench ${x.type}`, x.row); } });
  } catch (e) { App.showMessage('adminDashboardMessage', e.message, 'error'); }
}

async function initAdminList(title, endpoint, cols, getContractId = null, onSelect = null) {
  await App.guardPage({ roles: ['admin'] });
  try {
    const res = await App.requestJson('GET', `${App.getApiBase()}${endpoint}`);
    const rows = arr(res.items);
    $('adminListCounter').textContent = rows.length;
    App.renderTable('adminListTable', rows, cols, {
      onRowClick: async (row) => {
        setDetail('adminEntityDetail', row);
        let events = [], tx = [];
        const cid = getContractId ? getContractId(row) : null;
        if (cid) { try { const flow = await App.requestJson('GET', `${App.getApiBase()}/api/contracts/${cid}/money-flow`); events = arr(flow.events); tx = arr(flow.transactions); } catch {} }
        setInspector(`${title} ${gv(row, 'id')}`, row, events, tx);
        if (typeof onSelect === 'function') onSelect(row, rows);
      },
    });
  } catch (e) { App.showMessage('adminListMessage', e.message, 'error'); }
}

async function initAdminUsers() { return initAdminList('Ngu?i dùng', '/api/admin/users', [
  { key: 'hoten', label: 'H? tên' }, { key: 'email', label: 'Email' }, { key: 'sodienthoai', label: 'Ði?n tho?i' },
  { key: 'vaitro', label: 'Vai trò', render: (r) => App.statusBadge(gv(r, 'vaitro')) }, { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
]); }

async function initAdminVehicles() {
  await App.guardPage({ roles: ['admin'] });
  const updateStatus = async (row, trangThai) => {
    const ok = await confirmModal({
      title: 'Xác nh?n c?p nh?t tr?ng thái xe',
      message: `Xe ${gv(row, 'bienso')} s? chuy?n sang tr?ng thái ${trangThai}.`,
      confirmText: 'C?p nh?t',
    });
    if (!ok) return;
    await App.requestJson('PATCH', `${App.getApiBase()}/api/admin/vehicles/${gv(row, 'id')}/status`, { trangThai });
    App.showMessage('adminListMessage', `Ðã c?p nh?t xe ${gv(row, 'bienso')} -> ${trangThai}.`, 'success');
    await initAdminVehicles();
  };

  try {
    const res = await App.requestJson('GET', `${App.getApiBase()}/api/admin/vehicles`);
    const rows = arr(res.items);
    $('adminListCounter').textContent = rows.length;
    App.renderTable('adminListTable', rows, [
      { key: 'bienso', label: 'Bi?n s?' },
      { key: 'hangxe', label: 'Hãng xe' },
      { key: 'dongxe', label: 'Dòng xe' },
      { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
      { key: 'giatheongay', label: 'Giá/ngày', render: (r) => App.formatMoney(gv(r, 'giatheongay')) },
      {
        key: 'actions',
        label: 'Thao tác nhanh',
        render: (_r, idx) => `
          <div class="table-actions">
            <button type="button" class="table-action-btn ok" data-admin-action="vehicle-approve" data-row="${idx}">Duy?t</button>
            <button type="button" class="table-action-btn pending" data-admin-action="vehicle-maintain" data-row="${idx}">B?o trì</button>
            <button type="button" class="table-action-btn danger" data-admin-action="vehicle-stop" data-row="${idx}">Ng?ng</button>
          </div>
        `,
      },
    ], {
      onRowClick: async (row) => {
        setDetail('adminEntityDetail', row);
        setInspector(`Xe ${gv(row, 'bienso')}`, row);
        if ($('adminModuleActions')) {
          $('adminModuleActions').innerHTML = `
            <label>Tr?ng thái m?i
              <select id="adminVehicleStatusSelect">
                <option value="choDuyet">choDuyet</option>
                <option value="sanSang">sanSang</option>
                <option value="dangThue">dangThue</option>
                <option value="baoTri">baoTri</option>
                <option value="ngungHoatDong">ngungHoatDong</option>
              </select>
            </label>
            <button id="adminApproveVehicleBtn" type="button">C?p nh?t tr?ng thái xe dang ch?n</button>
          `;
          $('adminVehicleStatusSelect').value = gv(row, 'trangthai') || 'choDuyet';
          $('adminApproveVehicleBtn').onclick = async () => {
            try {
              const btn = $('adminApproveVehicleBtn');
              App.setLoading(btn, true);
              await updateStatus(row, App.requireValue($('adminVehicleStatusSelect')?.value, 'Thi?u tr?ng thái'));
            } catch (er) {
              App.showMessage('adminListMessage', er.message, 'error');
            } finally {
              App.setLoading($('adminApproveVehicleBtn'), false);
            }
          };
        }
      },
    });

    const table = $('adminListTable');
    if (table) {
      table.onclick = async (e) => {
        const btn = e.target.closest('[data-admin-action]');
        if (!btn) return;
        e.preventDefault();
        e.stopPropagation();
        const row = rows[Number(btn.getAttribute('data-row') || -1)];
        if (!row) return;
        const action = btn.getAttribute('data-admin-action');
        try {
          if (action === 'vehicle-approve') await updateStatus(row, 'sanSang');
          if (action === 'vehicle-maintain') await updateStatus(row, 'baoTri');
          if (action === 'vehicle-stop') await updateStatus(row, 'ngungHoatDong');
        } catch (er) {
          App.showMessage('adminListMessage', er.message, 'error');
        }
      };
    }
  } catch (e) {
    App.showMessage('adminListMessage', e.message, 'error');
  }
}

async function initAdminBookings() { return initAdminList('Booking', '/api/admin/bookings', [
  { key: 'id', label: 'Mã booking' }, { key: 'xeid', label: 'Xe' }, { key: 'nguoidungid', label: 'Khách thuê' },
  { key: 'songaythue', label: 'S? ngày' }, { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
], (r) => gv(r, 'hopdongthueid')); }

async function initAdminContracts() { return initAdminList('H?p d?ng', '/api/admin/contracts', [
  { key: 'id', label: 'Mã h?p d?ng' }, { key: 'xeid', label: 'Xe' }, { key: 'nguoithueid', label: 'Khách thuê' },
  { key: 'chuxeid', label: 'Ch? xe' }, { key: 'tongtiencoc', label: 'Ti?n c?c', render: (r) => App.formatMoney(gv(r, 'tongtiencoc')) },
  { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
], (r) => gv(r, 'id')); }

async function initAdminDisputes() {
  await App.guardPage({ roles: ['admin'] });
  const applyNoDamage = async (row) => {
    const data = await disputeDecisionModal({ row, mode: 'no-damage' });
    if (!data) return;
    const stepUpHeaders = await requireStepUpChallengeHeader();
    await App.requestJson('POST', `${App.getApiBase()}/api/disputes/${gv(row, 'id')}/admin-confirm-no-damage`, {
      decisionNote: data.decisionNote,
    }, '', stepUpHeaders);
    App.showMessage('adminListMessage', `Ðã x? lý tranh ch?p ${gv(row, 'id')} (không hu h?i).`, 'success');
    await initAdminDisputes();
  };
  const applyDamage = async (row) => {
    const data = await disputeDecisionModal({ row, mode: 'damage' });
    if (!data) return;
    const stepUpHeaders = await requireStepUpChallengeHeader();
    await App.requestJson('POST', `${App.getApiBase()}/api/disputes/${gv(row, 'id')}/admin-confirm-damage`, {
      approvedCost: data.approvedCost,
      decisionNote: data.decisionNote,
    }, '', stepUpHeaders);
    App.showMessage('adminListMessage', `Ðã x? lý tranh ch?p ${gv(row, 'id')} (có hu h?i).`, 'success');
    await initAdminDisputes();
  };
  try {
    const res = await App.requestJson('GET', `${App.getApiBase()}/api/admin/disputes`);
    const rows = arr(res.items);
    $('adminListCounter').textContent = rows.length;
    App.renderTable('adminListTable', rows, [
      { key: 'id', label: 'Mã tranh ch?p' },
      { key: 'hopdongthueid', label: 'H?p d?ng' },
      { key: 'lydo', label: 'Lý do' },
      {
        key: 'priority',
        label: 'Uu tiên',
        render: (r) => {
          const p = disputePriority(r);
          return `<span class="badge ${p.cls}">${p.label}</span>`;
        },
      },
      { key: 'sotienphaithu', label: 'S? ti?n', render: (r) => App.formatMoney(gv(r, 'sotienphaithu')) },
      { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
      {
        key: 'actions',
        label: 'Thao tác nhanh',
        render: (_r, idx) => `
          <div class="table-actions">
            <button type="button" class="table-action-btn ok" data-admin-action="dispute-no-damage" data-row="${idx}">Không hu h?i</button>
            <button type="button" class="table-action-btn danger" data-admin-action="dispute-damage" data-row="${idx}">Có hu h?i</button>
          </div>
        `,
      },
    ], {
      onRowClick: async (row) => {
        setDetail('adminEntityDetail', row);
        let flow = { events: [], transactions: [] };
        try {
          if (gv(row, 'hopdongthueid')) {
            flow = await App.requestJson('GET', `${App.getApiBase()}/api/contracts/${gv(row, 'hopdongthueid')}/money-flow`);
          }
        } catch {}
        setInspector(`Tranh ch?p ${gv(row, 'id')}`, row, arr(flow.events), arr(flow.transactions));
        if ($('adminModuleActions')) {
          $('adminModuleActions').innerHTML = `
            <div class="table-actions">
              <button id="adminNoDamageBtn" type="button" class="table-action-btn ok">Xác nh?n không hu h?i</button>
              <button id="adminDamageBtn" type="button" class="table-action-btn danger">Xác nh?n có hu h?i</button>
            </div>
          `;
          $('adminNoDamageBtn').onclick = async () => {
            try { await applyNoDamage(row); } catch (er) { App.showMessage('adminListMessage', er.message, 'error'); }
          };
          $('adminDamageBtn').onclick = async () => {
            try { await applyDamage(row); } catch (er) { App.showMessage('adminListMessage', er.message, 'error'); }
          };
        }
      },
    });

    const table = $('adminListTable');
    if (table) {
      table.onclick = async (e) => {
        const btn = e.target.closest('[data-admin-action]');
        if (!btn) return;
        e.preventDefault();
        e.stopPropagation();
        const row = rows[Number(btn.getAttribute('data-row') || -1)];
        if (!row) return;
        try {
          if (btn.getAttribute('data-admin-action') === 'dispute-no-damage') await applyNoDamage(row);
          if (btn.getAttribute('data-admin-action') === 'dispute-damage') await applyDamage(row);
        } catch (er) {
          App.showMessage('adminListMessage', er.message, 'error');
        }
      };
    }
  } catch (e) {
    App.showMessage('adminListMessage', e.message, 'error');
  }
}

const OWNER_ACTIVE_CONTRACT_STATUSES = new Set(['choChuXacNhanGiaoXe', 'choKhachNhanXe', 'dangThue', 'choChuXacNhanTraXe', 'choTatToan', 'dangTranhChap']);
const OWNER_OPEN_DISPUTE_STATUSES = new Set(['moiTao', 'choAdminXacMinh', 'dangMo', 'dangXuLy']);

function ownerShortId(value, size = 6) {
  const text = String(value || '').trim();
  if (!text) return '---';
  return text.length <= size ? text : text.slice(-size).toUpperCase();
}

function ownerContractCode(value) {
  return `HD-${ownerShortId(value, 8)}`;
}

function ownerCustomerCode(value) {
  return `KH-${ownerShortId(value, 6)}`;
}

function ownerFriendlyError(error, fallback = 'Không th? x? lý yêu c?u lúc này, vui lòng th? l?i.') {
  const message = String(error?.message || '').trim();
  if (!message) return fallback;
  const lowered = message.toLowerCase();
  const technical = ['winerror', 'socket', 'econn', 'timed out', 'network', 'fetch failed', 'connection', 'traceback', '[errno'];
  if (technical.some((x) => lowered.includes(x))) return fallback;
  if (message.length > 180) return fallback;
  return message;
}

function ownerShowError(targetId, error, fallback) {
  console.error(error);
  App.showMessage(targetId, ownerFriendlyError(error, fallback), 'error');
}

function ownerTogglePanel(panelId, show) {
  const el = $(panelId);
  if (!el) return;
  el.classList.toggle('owner-hide', !show);
}

function ownerVehicleLabel(row) {
  const plate = gv(row, 'bienso') || ownerShortId(gv(row, 'id'));
  const brand = gv(row, 'hangxe') || 'Xe';
  const model = gv(row, 'dongxe') || '';
  return `${plate} - ${brand} ${model}`.trim();
}

function ownerDetailHtml(row) {
  if (!row) return '<div class="empty-state">Ch?n m?t b?n ghi d? xem chi ti?t.</div>';
  const entries = Object.entries(row).map(([k, v]) => {
    const display = typeof v === 'object' ? JSON.stringify(v) : String(v ?? '');
    return `<div class="kv"><span>${App.escapeHtml(k)}</span><strong class="text-break">${App.escapeHtml(display)}</strong></div>`;
  }).join('');
  return `<div class="detail-grid">${entries}</div>`;
}

async function ownerCopy(text, success = 'Ðã sao chép') {
  try {
    await navigator.clipboard.writeText(String(text || ''));
    App.toast(success, 'success');
  } catch {
    App.toast('Không th? sao chép trên trình duy?t này.', 'error');
  }
}

function ownerRenderQueue(targetId, items) {
  const root = $(targetId);
  if (!root) return;
  root.innerHTML = (items || []).map((item) => `
    <div class="queue-block">
      <h4>${App.escapeHtml(item.label)}</h4>
      <div class="queue-count">${App.escapeHtml(String(item.value ?? 0))}</div>
      ${item.hint ? `<p class="note">${App.escapeHtml(item.hint)}</p>` : ''}
    </div>
  `).join('');
}

async function initOwnerDashboard() {
  const session = await App.guardPage({ roles: ['chuxe', 'admin'] });
  if (session && $('welcomeUser')) $('welcomeUser').textContent = `Xin chào, ${session?.user?.hoTen || 'ch? xe'}`;
  if ($('ownerQuickActions')) {
    $('ownerQuickActions').innerHTML = `
      <a href="/owner/vehicles">Thêm xe m?i</a>
      <a href="/owner/availability">T?o l?ch tr?ng</a>
      <a href="/owner/contracts">Xem h?p d?ng</a>
      <a href="/owner/disputes">Báo cáo hu h?i</a>
    `;
  }
  try {
    const [dash, vehiclesRes, disputesRes, contractsRes, availabilityRes] = await Promise.all([
      App.requestJson('GET', `${App.getApiBase()}/api/dashboard`),
      App.requestJson('GET', `${App.getApiBase()}/api/owner/vehicles`),
      App.requestJson('GET', `${App.getApiBase()}/api/owner/disputes`),
      App.requestJson('GET', `${App.getApiBase()}/api/owner/contracts`),
      App.requestJson('GET', `${App.getApiBase()}/api/owner/availability`),
    ]);

    const vehicles = arr(vehiclesRes.items);
    const disputes = arr(disputesRes.items);
    const contracts = arr(contractsRes.items);
    const slots = arr(availabilityRes.items);
    const activeContracts = contracts.filter((r) => OWNER_ACTIVE_CONTRACT_STATUSES.has(String(contractFlowStatus(r))));
    const openDisputes = disputes.filter((r) => OWNER_OPEN_DISPUTE_STATUSES.has(String(gv(r, 'trangthai'))));
    const pendingVehicles = vehicles.filter((r) => gv(r, 'trangthai') === 'choDuyet');
    const rentingVehicles = vehicles.filter((r) => gv(r, 'trangthai') === 'dangThue');
    const waitingReturn = contracts.filter((r) => String(contractFlowStatus(r)) === 'choChuXacNhanTraXe');
    const slotVehicleIds = new Set(slots.map((x) => gv(x, 'xeid')).filter(Boolean));
    const noSchedule = vehicles.filter((v) => !slotVehicleIds.has(gv(v, 'id')));

    $('kpiVehicles').textContent = String(vehicles.length);
    $('kpiPending').textContent = String(pendingVehicles.length);
    $('kpiActiveRent').textContent = String(rentingVehicles.length);
    $('kpiContracts').textContent = String(dash?.stats?.contracts || activeContracts.length);
    $('kpiDisputes').textContent = String(openDisputes.length);

    ownerRenderQueue('ownerActionQueue', [
      { label: 'Xe ch? duy?t', value: pendingVehicles.length, hint: 'Theo dõi d? d?m b?o xe s?m s?n sàng.' },
      { label: 'H?p d?ng dang thuê', value: activeContracts.length, hint: 'C?n giám sát ti?n d? thuê và hoàn c?c.' },
      { label: 'Tranh ch?p dang m?', value: openDisputes.length, hint: 'Uu tiên x? lý d? gi?m th?i gian treo c?c.' },
      { label: 'H?p d?ng ch? ki?m tra tr? xe', value: waitingReturn.length, hint: 'Ki?m tra xe d? hoàn t?t t?t toán.' },
      { label: 'Xe chua có l?ch tr?ng', value: noSchedule.length, hint: 'Nên t?o l?ch d? tang kh? nang du?c d?t.' },
    ]);

    App.renderTable('ownerRecentVehicles', vehicles.slice(0, 6), [
      { key: 'bienso', label: 'Bi?n s?' }, { key: 'hangxe', label: 'Hãng xe' }, { key: 'dongxe', label: 'Dòng xe' }, { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(vehicleDisplayStatus(r)) },
    ]);

    App.renderTable('ownerActiveContracts', activeContracts.slice(0, 6), [
      { key: 'id', label: 'Mã HÐ', render: (r) => ownerContractCode(gv(r, 'id')) },
      { key: 'xeid', label: 'Xe', render: (r) => ownerShortId(gv(r, 'xeid')) },
      { key: 'nguoithueid', label: 'Khách thuê', render: (r) => ownerCustomerCode(gv(r, 'nguoithueid')) },
      { key: 'tongtiencoc', label: 'Ti?n c?c', render: (r) => App.formatMoney(gv(r, 'tongtiencoc')) },
      { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(contractFlowStatus(r)) },
    ]);

    App.renderTable('ownerRecentDisputes', disputes.slice(0, 6), [
      { key: 'id', label: 'Mã TC', render: (r) => `TC-${ownerShortId(gv(r, 'id'))}` },
      { key: 'hopdongthueid', label: 'H?p d?ng', render: (r) => ownerContractCode(gv(r, 'hopdongthueid')) },
      { key: 'lydo', label: 'Lý do', render: (r) => App.escapeHtml(String(gv(r, 'lydo') || '').slice(0, 70) || 'Chua c?p nh?t') },
      { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
    ]);
  } catch (e) {
    ownerShowError('ownerDashboardMessage', e, 'Không th? t?i dashboard ch? xe lúc này.');
  }
}

async function initRenterDashboard() {
  const session = await App.guardPage({ roles: ['khach', 'admin'] });
  if (session && $('welcomeUser')) $('welcomeUser').textContent = `Xin chào, ${session?.user?.hoTen || 'khách thuê'}`;
  try {
    const [bookings, contracts, deposits] = await Promise.all([
      App.requestJson('GET', `${App.getApiBase()}/api/renter/bookings`),
      App.requestJson('GET', `${App.getApiBase()}/api/renter/contracts`),
      App.requestJson('GET', `${App.getApiBase()}/api/renter/deposits`),
    ]);
    $('kpiBookings').textContent = arr(bookings.items).length;
    $('kpiContracts').textContent = arr(contracts.items).length;
    $('kpiDeposits').textContent = arr(deposits.items).length;
    $('kpiActive').textContent = arr(contracts.items).filter((c) => contractFlowStatus(c) === 'dangThue').length;
    App.renderTable('renterRecentBookings', arr(bookings.items).slice(0, 6), [
      { key: 'id', label: 'Booking' }, { key: 'xeid', label: 'Xe' }, { key: 'songaythue', label: 'S? ngày' },
      { key: 'tongtienthue', label: 'T?ng ti?n', render: (r) => App.formatMoney(gv(r, 'tongtienthue')) }, { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
    ]);
  } catch (e) { App.showMessage('renterDashboardMessage', e.message, 'error'); }
}

async function initFinance() {
  await App.guardPage({ roles: ['admin'] });
  const load = async () => {
    const [summary, data] = await Promise.all([
      App.requestJson('GET', `${App.getApiBase()}/api/finance/summary`),
      App.requestJson('GET', `${App.getApiBase()}/api/finance/transactions`),
    ]);
    $('kpiFee').textContent = App.formatMoney(summary?.totalPlatformFeesCollected ?? 0);
    $('kpiGross').textContent = App.formatMoney(summary?.totalGrossPayments ?? 0);
    $('kpiNet').textContent = App.formatMoney(summary?.totalNetPayouts ?? 0);
    $('kpiTxToday').textContent = summary?.totalTransactions ?? 0;
    $('kpiTxPending').textContent = summary?.warnings && Object.keys(summary.warnings).length ? Object.keys(summary.warnings).length : 0;
    $('chainSyncStatus').textContent = summary?.latestBlock?.hash ? `Ð?ng b? d?n block #${summary.latestBlock.blockheight}` : 'Chua có d? li?u block';

    App.renderTable('financeTransactionsTable', arr(data.transactions), [
      { key: 'txHash', label: 'Tx hash' }, { key: 'txType', label: 'Lo?i giao d?ch' }, { key: 'amount', label: 'S? ti?n', render: (r) => App.formatMoney(gv(r, 'amount')) },
      { key: 'fromAddress', label: 'T?' }, { key: 'toAddress', label: 'Ð?n' },
      { key: 'status', label: 'Tr?ng thái', render: (r) => App.statusBadge(gv(r, 'status') || 'pending') },
      { key: 'timestamp', label: 'Th?i gian', render: (r) => App.formatDate(gv(r, 'timestamp')) },
    ], { onRowClick: async (row) => {
      setDetail('financeTxDetail', row);
      let flow = { events: [], transactions: [] };
      if (gv(row, 'contractId')) { try { flow = await App.requestJson('GET', `${App.getApiBase()}/api/contracts/${gv(row, 'contractId')}/money-flow`); } catch {} }
      setInspector(`Giao d?ch ${gv(row, 'txHash')}`, row, arr(flow.events), arr(flow.transactions));
    }});
  };

  $('financeFiltersForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const q = new URLSearchParams();
      ['walletAddress', 'txType', 'contractId', 'disputeId'].forEach((id) => { const v = $(id)?.value?.trim(); if (v) q.set(id, v); });
      const data = await App.requestJson('GET', `${App.getApiBase()}/api/finance/transactions${q.toString() ? '?' + q.toString() : ''}`);
      App.renderTable('financeTransactionsTable', arr(data.transactions), [
        { key: 'txHash', label: 'Tx hash' }, { key: 'txType', label: 'Lo?i giao d?ch' }, { key: 'amount', label: 'S? ti?n', render: (r) => App.formatMoney(gv(r, 'amount')) },
        { key: 'fromAddress', label: 'T?' }, { key: 'toAddress', label: 'Ð?n' }, { key: 'status', label: 'Tr?ng thái', render: (r) => App.statusBadge(gv(r, 'status') || 'pending') },
      ], { onRowClick: (row) => { setDetail('financeTxDetail', row); setInspector(`Giao d?ch ${gv(row, 'txHash')}`, row); } });
    } catch (er) { App.showMessage('financeMessage', er.message, 'error'); }
  });

  try { await load(); } catch (e) { App.showMessage('financeMessage', e.message, 'error'); }
}

async function initChain() {
  await App.guardPage({ roles: ['admin'] });
  try {
    const chain = await App.requestJson('GET', `${App.getApiBase()}/api/node/chain`);
    if ($('chainJson')) $('chainJson').textContent = j(chain);
    setInspector('D? li?u chu?i', chain);
  } catch (e) { App.showMessage('chainMessage', e.message, 'error'); }
}

const PAGE_INIT = {
  landing: initLanding, login: initLogin, register: initRegister,
  admin_dashboard: initAdminDashboard, admin_users: initAdminUsers, admin_vehicles: initAdminVehicles, admin_bookings: initAdminBookings, admin_contracts: initAdminContracts, admin_disputes: initAdminDisputes,
  owner_dashboard: initOwnerDashboard, renter_dashboard: initRenterDashboard,
  finance: initFinance, chain: initChain,
};

document.addEventListener('DOMContentLoaded', async () => {
  App.setRequiredMarkers();
  if ($('inspectorBody')) setInspectorEmpty();
  const fn = PAGE_INIT[document.body?.dataset?.page];
  if (!fn) return;
  try { await fn(); } catch (e) { if ($('pageMessage')) { $('pageMessage').textContent = e.message; $('pageMessage').className = 'message error'; } }
});

async function initOwnerVehiclesSimple() {
  await App.guardPage({ roles: ['chuxe', 'admin'] });
  const form = $('vehicleForm');
  const formPanelId = 'ownerVehicleFormPanel';
  const detailPanelId = 'ownerVehicleDetailPanel';
  const rowsState = { all: [], filtered: [] };

  const applyFilter = () => {
    const q = String($('ownerVehicleSearch')?.value || '').trim().toLowerCase();
    const status = String($('ownerVehicleStatusFilter')?.value || '').trim();
    rowsState.filtered = rowsState.all.filter((row) => {
      const text = `${gv(row, 'bienso')} ${gv(row, 'hangxe')} ${gv(row, 'dongxe')}`.toLowerCase();
      const matchQ = !q || text.includes(q);
      const rowStatus = String(gv(row, 'displaytrangthai') || gv(row, 'trangthai') || '').trim();
      const matchStatus = !status || rowStatus === status;
      return matchQ && matchStatus;
    });
  };

  const render = () => {
    applyFilter();
    ownerTogglePanel('ownerVehiclesEmpty', rowsState.filtered.length === 0);
    App.renderTable('ownerVehiclesTable', rowsState.filtered, [
      { key: 'bienso', label: 'Bi?n s?' },
      { key: 'hangxe', label: 'Hãng xe' },
      { key: 'dongxe', label: 'Dòng xe' },
      { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(vehicleDisplayStatus(r)) },
      { key: 'giatheongay', label: 'Giá/ngày', render: (r) => App.formatMoney(gv(r, 'giatheongay')) },
      { key: 'actions', label: 'Thao tác', render: (_r, idx) => `
        <div class="table-actions">
          <button type="button" class="table-action-btn" data-owner-vehicle-action="view" data-row="${idx}">Chi ti?t</button>
          <button type="button" class="table-action-btn pending" data-owner-vehicle-action="schedule" data-row="${idx}">L?ch tr?ng</button>
          <button type="button" class="table-action-btn ok" data-owner-vehicle-action="copy" data-row="${idx}">Copy ID</button>
        </div>
      ` },
    ], {
      onRowClick: (row) => {
        ownerTogglePanel(detailPanelId, true);
        if ($('ownerVehicleDetail')) $('ownerVehicleDetail').innerHTML = ownerDetailHtml(row);
      },
    });
  };

  const load = async () => {
    const data = await App.requestJson('GET', `${App.getApiBase()}/api/owner/vehicles`);
    rowsState.all = arr(data.items);
    render();
  };

  $('toggleOwnerVehicleFormBtn')?.addEventListener('click', () => ownerTogglePanel(formPanelId, true));
  $('closeOwnerVehicleFormBtn')?.addEventListener('click', () => ownerTogglePanel(formPanelId, false));
  $('ownerVehicleSearch')?.addEventListener('input', render);
  $('ownerVehicleStatusFilter')?.addEventListener('change', render);
  $('ownerVehiclesTable')?.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-owner-vehicle-action]');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const row = rowsState.filtered[Number(btn.getAttribute('data-row') || -1)];
    if (!row) return;
    const action = btn.getAttribute('data-owner-vehicle-action');
    if (action === 'view') {
      ownerTogglePanel(detailPanelId, true);
      if ($('ownerVehicleDetail')) $('ownerVehicleDetail').innerHTML = ownerDetailHtml(row);
    }
    if (action === 'schedule') window.location.href = `/owner/availability?xeId=${encodeURIComponent(gv(row, 'id'))}`;
    if (action === 'copy') await ownerCopy(gv(row, 'id'), 'Ðã sao chép mã xe.');
  });

  try {
    await load();
  } catch (e) {
    ownerShowError('ownerVehicleMessage', e, 'Không th? t?i danh sách xe lúc này.');
  }

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    try {
      App.setLoading(btn, true);
      const dailyPrice = Number(App.requireValue($('giaTheoNgay')?.value, 'Thi?u giá theo ngày'));
      if (!Number.isFinite(dailyPrice)) throw new Error('Giá theo ngày không h?p l?.');
      if (dailyPrice < 10000) throw new Error('Giá theo ngày t?i thi?u là 10.000.');
      if (dailyPrice % 10000 !== 0) throw new Error('Giá theo ngày ph?i tang theo bu?c 10.000.');
      await App.requestJson('POST', `${App.getApiBase()}/api/vehicles`, {
        bienSo: App.requireValue($('bienSo')?.value, 'Thi?u bi?n s?'),
        hangXe: App.requireValue($('hangXe')?.value, 'Thi?u hãng xe'),
        dongXe: App.requireValue($('dongXe')?.value, 'Thi?u dòng xe'),
        loaiXe: App.requireValue($('loaiXe')?.value, 'Thi?u lo?i xe'),
        namSanXuat: $('namSanXuat')?.value ? Number($('namSanXuat')?.value) : null,
        moTa: $('moTa')?.value?.trim() || null,
        giaTheoNgay: dailyPrice,
        giaTheoGio: Number($('giaTheoGio')?.value || 0),
        baoHiem: $('baoHiem')?.value?.trim() || null,
        dangKiem: $('dangKiem')?.value?.trim() || null,
        dangKyXe: $('dangKyXe')?.value?.trim() || null,
        ngayHetHanDangKiem: $('ngayHetHanDangKiem')?.value || null,
      });
      App.showMessage('ownerVehicleMessage', 'Ðã luu xe thành công.', 'success');
      form.reset();
      ownerTogglePanel(formPanelId, false);
      await load();
    } catch (er) {
      ownerShowError('ownerVehicleMessage', er, 'Không th? luu xe lúc này, vui lòng th? l?i.');
    } finally {
      App.setLoading(btn, false);
    }
  });
}

async function initOwnerAvailabilitySimple() {
  await App.guardPage({ roles: ['chuxe', 'admin'] });
  const form = $('availabilityForm');
  const formPanelId = 'ownerAvailabilityFormPanel';
  const detailPanelId = 'ownerAvailabilityDetailPanel';
  const vehicleMap = new Map();
  const state = { all: [], filtered: [] };
  const presetXeId = new URLSearchParams(window.location.search).get('xeId');

  const applyFilter = () => {
    const q = String($('ownerAvailabilitySearch')?.value || '').trim().toLowerCase();
    const status = String($('ownerAvailabilityStatusFilter')?.value || '').trim();
    state.filtered = state.all.filter((row) => {
      const vehicleText = (vehicleMap.get(gv(row, 'xeid')) || gv(row, 'xeid')).toLowerCase();
      const matchQ = !q || vehicleText.includes(q);
      const matchStatus = !status || String(Boolean(gv(row, 'controng'))) === status;
      return matchQ && matchStatus;
    });
  };

  const render = () => {
    applyFilter();
    ownerTogglePanel('ownerAvailabilityEmpty', state.filtered.length === 0);
    App.renderTable('ownerAvailabilityTable', state.filtered, [
      { key: 'xeid', label: 'Xe', render: (r) => App.escapeHtml(vehicleMap.get(gv(r, 'xeid')) || ownerShortId(gv(r, 'xeid'))) },
      { key: 'ngaybatdau', label: 'B?t d?u', render: (r) => App.formatDate(gv(r, 'ngaybatdau')) },
      { key: 'ngayketthuc', label: 'K?t thúc', render: (r) => App.formatDate(gv(r, 'ngayketthuc')) },
      { key: 'controng', label: 'Tr?ng thái', render: (r) => App.statusBadge(gv(r, 'controng') ? 'Còn tr?ng' : 'Không tr?ng') },
      { key: 'ghichu', label: 'Ghi chú', render: (r) => App.escapeHtml(gv(r, 'ghichu') || '—') },
      { key: 'actions', label: 'Thao tác', render: (_r, idx) => `
        <div class="table-actions">
          <button type="button" class="table-action-btn" data-owner-slot-action="view" data-row="${idx}">Chi ti?t</button>
          <button type="button" class="table-action-btn ok" data-owner-slot-action="copy" data-row="${idx}">Copy ID</button>
        </div>
      ` },
    ], {
      onRowClick: (row) => {
        ownerTogglePanel(detailPanelId, true);
        if ($('ownerAvailabilityDetail')) $('ownerAvailabilityDetail').innerHTML = ownerDetailHtml(row);
      },
    });
  };

  const load = async () => {
    const [vehicles, slots] = await Promise.all([
      App.requestJson('GET', `${App.getApiBase()}/api/owner/vehicles`),
      App.requestJson('GET', `${App.getApiBase()}/api/owner/availability`),
    ]);
    vehicleMap.clear();
    arr(vehicles.items).forEach((v) => vehicleMap.set(gv(v, 'id'), ownerVehicleLabel(v)));
    App.renderSelect('xeId', arr(vehicles.items), 'id', ownerVehicleLabel);
    if (presetXeId && $('xeId')) {
      $('xeId').value = presetXeId;
      ownerTogglePanel(formPanelId, true);
    }
    state.all = arr(slots.items);
    render();
  };

  $('toggleOwnerAvailabilityFormBtn')?.addEventListener('click', () => ownerTogglePanel(formPanelId, true));
  $('closeOwnerAvailabilityFormBtn')?.addEventListener('click', () => ownerTogglePanel(formPanelId, false));
  $('ownerAvailabilitySearch')?.addEventListener('input', render);
  $('ownerAvailabilityStatusFilter')?.addEventListener('change', render);
  $('ownerAvailabilityTable')?.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-owner-slot-action]');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const row = state.filtered[Number(btn.getAttribute('data-row') || -1)];
    if (!row) return;
    const action = btn.getAttribute('data-owner-slot-action');
    if (action === 'view') {
      ownerTogglePanel(detailPanelId, true);
      if ($('ownerAvailabilityDetail')) $('ownerAvailabilityDetail').innerHTML = ownerDetailHtml(row);
    }
    if (action === 'copy') await ownerCopy(gv(row, 'id'), 'Ðã sao chép mã l?ch tr?ng.');
  });

  try {
    await load();
  } catch (e) {
    ownerShowError('ownerAvailabilityMessage', e, 'Không th? t?i l?ch tr?ng lúc này.');
  }
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    try {
      App.setLoading(btn, true);
      await App.requestJson('POST', `${App.getApiBase()}/api/owner/availability`, {
        xeId: App.requireValue($('xeId')?.value, 'Chua ch?n xe'),
        ngayBatDau: App.requireValue($('ngayBatDau')?.value, 'Thi?u ngày b?t d?u'),
        ngayKetThuc: App.requireValue($('ngayKetThuc')?.value, 'Thi?u ngày k?t thúc'),
        conTrong: $('conTrong')?.value !== 'false',
        ghiChu: $('ghiChu')?.value?.trim() || null,
      });
      App.showMessage('ownerAvailabilityMessage', 'Ðã luu l?ch tr?ng.', 'success');
      form.reset();
      ownerTogglePanel(formPanelId, false);
      await load();
    } catch (er) {
      ownerShowError('ownerAvailabilityMessage', er, 'Không th? luu l?ch tr?ng lúc này, vui lòng th? l?i.');
    } finally {
      App.setLoading(btn, false);
    }
  });
}

async function initOwnerContractsSimple() {
  await App.guardPage({ roles: ['chuxe', 'admin'] });
  const state = { all: [], filtered: [] };
  const vehicleMap = new Map();

  const applyFilter = () => {
    const q = String($('ownerContractSearch')?.value || '').trim().toLowerCase();
    const status = String($('ownerContractStatusFilter')?.value || '').trim();
    state.filtered = state.all.filter((row) => {
      const text = `${ownerContractCode(gv(row, 'id'))} ${vehicleMap.get(gv(row, 'xeid')) || gv(row, 'xeid')} ${ownerCustomerCode(gv(row, 'nguoithueid'))}`.toLowerCase();
      const matchQ = !q || text.includes(q);
      const matchStatus = !status || String(contractFlowStatus(row)) === status;
      return matchQ && matchStatus;
    });
  };

  const renderDetail = (row) => {
    ownerTogglePanel('ownerContractDetailPanel', true);
    if (!$('ownerContractDetail')) return;
    $('ownerContractDetail').innerHTML = `
      <div class="detail-grid">
        <div class="kv"><span>Mã h?p d?ng</span><strong>${App.escapeHtml(gv(row, 'id'))}</strong></div>
        <div class="kv"><span>Xe</span><strong>${App.escapeHtml(vehicleMap.get(gv(row, 'xeid')) || gv(row, 'xeid'))}</strong></div>
        <div class="kv"><span>Mã khách thuê</span><strong>${App.escapeHtml(gv(row, 'nguoithueid'))}</strong></div>
        <div class="kv"><span>Ti?n c?c</span><strong>${App.escapeHtml(App.formatMoney(gv(row, 'tongtiencoc') || 0))}</strong></div>
        <div class="kv"><span>Tr?ng thái</span><strong>${App.escapeHtml(String(contractFlowStatus(row) || ''))}</strong></div>
        <div class="kv"><span>T?o lúc</span><strong>${App.escapeHtml(App.formatDate(gv(row, 'taoluc')) || 'Chua c?p nh?t')}</strong></div>
      </div>
      <div class="table-actions" style="margin-top:10px">
        <button type="button" class="table-action-btn ok" data-owner-copy-contract="${App.escapeHtml(gv(row, 'id'))}">Copy Contract ID</button>
        <button type="button" class="table-action-btn" data-owner-copy-vehicle="${App.escapeHtml(gv(row, 'xeid'))}">Copy Vehicle ID</button>
      </div>
    `;
  };

  const render = () => {
    applyFilter();
    ownerTogglePanel('ownerContractsEmpty', state.filtered.length === 0);
    App.renderTable('ownerContractsTable', state.filtered, [
      { key: 'id', label: 'Mã h?p d?ng', render: (r) => ownerContractCode(gv(r, 'id')) },
      { key: 'xeid', label: 'Xe', render: (r) => App.escapeHtml(vehicleMap.get(gv(r, 'xeid')) || ownerShortId(gv(r, 'xeid'))) },
      { key: 'nguoithueid', label: 'Khách thuê', render: (r) => ownerCustomerCode(gv(r, 'nguoithueid')) },
      { key: 'tongtiencoc', label: 'Ti?n c?c', render: (r) => App.formatMoney(gv(r, 'tongtiencoc')) },
      { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(contractFlowStatus(r)) },
      { key: 'taoluc', label: 'Ngày t?o', render: (r) => App.formatDate(gv(r, 'taoluc')) || '—' },
      { key: 'actions', label: 'Thao tác', render: (_r, idx) => `
        <div class="table-actions">
          <button type="button" class="table-action-btn" data-owner-contract-action="view" data-row="${idx}">Chi ti?t</button>
          <button type="button" class="table-action-btn ok" data-owner-contract-action="copy" data-row="${idx}">Copy ID</button>
        </div>
      ` },
    ], { onRowClick: renderDetail });
  };

  const load = async () => {
    const [contracts, vehicles] = await Promise.all([
      App.requestJson('GET', `${App.getApiBase()}/api/owner/contracts`),
      App.requestJson('GET', `${App.getApiBase()}/api/owner/vehicles`),
    ]);
    vehicleMap.clear();
    arr(vehicles.items).forEach((v) => vehicleMap.set(gv(v, 'id'), ownerVehicleLabel(v)));
    state.all = arr(contracts.items);
    const label = (c) => `${ownerContractCode(gv(c, 'id'))} - ${contractFlowStatus(c)}`;
    App.renderSelect('ownerHandoverContractId', state.all, 'id', label, 'Ch?n h?p d?ng');
    App.renderSelect('ownerReturnContractId', state.all, 'id', label, 'Ch?n h?p d?ng');
    render();
  };

  $('ownerContractSearch')?.addEventListener('input', render);
  $('ownerContractStatusFilter')?.addEventListener('change', render);
  $('ownerContractsTable')?.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-owner-contract-action]');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const row = state.filtered[Number(btn.getAttribute('data-row') || -1)];
    if (!row) return;
    if (btn.getAttribute('data-owner-contract-action') === 'view') renderDetail(row);
    if (btn.getAttribute('data-owner-contract-action') === 'copy') await ownerCopy(gv(row, 'id'), 'Ðã sao chép mã h?p d?ng.');
  });
  $('ownerContractDetailPanel')?.addEventListener('click', async (e) => {
    const contractBtn = e.target.closest('[data-owner-copy-contract]');
    if (contractBtn) return ownerCopy(contractBtn.getAttribute('data-owner-copy-contract'), 'Ðã sao chép Contract ID.');
    const vehicleBtn = e.target.closest('[data-owner-copy-vehicle]');
    if (vehicleBtn) return ownerCopy(vehicleBtn.getAttribute('data-owner-copy-vehicle'), 'Ðã sao chép Vehicle ID.');
  });

  try {
    await load();
  } catch (e) {
    ownerShowError('ownerContractsMessage', e, 'Không th? t?i danh sách h?p d?ng lúc này.');
  }

  $('ownerConfirmHandoverForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.submitter || $('ownerConfirmHandoverForm')?.querySelector('button[type="submit"]');
    try {
      App.setLoading(btn, true);
      const id = App.requireValue($('ownerHandoverContractId')?.value, 'Chua ch?n h?p d?ng');
      const stepUpHeaders = await requireStepUpChallengeHeader();
      await App.requestJson('POST', `${App.getApiBase()}/api/contracts/${id}/owner-confirm-handover`, {
        ghiChu: App.requireValue($('ownerHandoverNote')?.value, 'Thi?u ghi chú giao xe'),
        evidenceUrls: [],
      }, '', stepUpHeaders);
      App.showMessage('ownerContractsMessage', 'Ðã xác nh?n giao xe.', 'success');
      await load();
    } catch (er) {
      ownerShowError('ownerContractsMessage', er, 'Không th? xác nh?n giao xe lúc này.');
    } finally {
      App.setLoading(btn, false);
    }
  });

  $('ownerConfirmReturnForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.submitter || $('ownerConfirmReturnForm')?.querySelector('button[type="submit"]');
    try {
      App.setLoading(btn, true);
      const id = App.requireValue($('ownerReturnContractId')?.value, 'Chua ch?n h?p d?ng');
      const stepUpHeaders = await requireStepUpChallengeHeader();
      await App.requestJson('POST', `${App.getApiBase()}/api/contracts/${id}/owner-confirm-return`, {
        ghiChu: App.requireValue($('ownerReturnNote')?.value, 'Thi?u ghi chú nh?n l?i xe'),
        evidenceUrls: [],
      }, '', stepUpHeaders);
      App.showMessage('ownerContractsMessage', 'Ðã xác nh?n nh?n l?i xe.', 'success');
      await load();
    } catch (er) {
      ownerShowError('ownerContractsMessage', er, 'Không th? xác nh?n nh?n l?i xe lúc này.');
    } finally {
      App.setLoading(btn, false);
    }
  });
}

async function initOwnerDisputesSimple() {
  await App.guardPage({ roles: ['chuxe', 'admin'] });
  const form = $('ownerDamageForm');
  const formPanelId = 'ownerDisputeFormPanel';
  const state = { all: [], filtered: [] };
  const contractMap = new Map();

  const contractLabel = (c) => {
    const code = ownerContractCode(gv(c, 'id'));
    const vehicle = ownerShortId(gv(c, 'xeid'));
    const customer = ownerCustomerCode(gv(c, 'nguoithueid'));
    return `${code} - Xe ${vehicle} - ${customer}`;
  };

  const applyFilter = () => {
    const q = String($('ownerDisputeSearch')?.value || '').trim().toLowerCase();
    const status = String($('ownerDisputeStatusFilter')?.value || '').trim();
    state.filtered = state.all.filter((row) => {
      const label = contractMap.get(gv(row, 'hopdongthueid')) || ownerContractCode(gv(row, 'hopdongthueid'));
      const text = `${ownerShortId(gv(row, 'id'))} ${label} ${gv(row, 'lydo')}`.toLowerCase();
      const matchQ = !q || text.includes(q);
      const matchStatus = !status || String(gv(row, 'trangthai')) === status;
      return matchQ && matchStatus;
    });
  };

  const renderDetail = (row) => {
    ownerTogglePanel('ownerDisputeDetailPanel', true);
    if (!$('ownerDisputeDetail')) return;
    $('ownerDisputeDetail').innerHTML = `
      <div class="detail-grid">
        <div class="kv"><span>Mã tranh ch?p</span><strong>${App.escapeHtml(gv(row, 'id'))}</strong></div>
        <div class="kv"><span>H?p d?ng</span><strong>${App.escapeHtml(contractMap.get(gv(row, 'hopdongthueid')) || gv(row, 'hopdongthueid'))}</strong></div>
        <div class="kv"><span>Lý do</span><strong class="text-break">${App.escapeHtml(gv(row, 'lydo') || 'Chua c?p nh?t')}</strong></div>
        <div class="kv"><span>Chi phí</span><strong>${App.escapeHtml(App.formatMoney(gv(row, 'sotienphaithu') || gv(row, 'estimatedcost') || 0))}</strong></div>
        <div class="kv"><span>Tr?ng thái</span><strong>${App.escapeHtml(String(gv(row, 'trangthai') || ''))}</strong></div>
      </div>
    `;
  };

  const render = () => {
    applyFilter();
    ownerTogglePanel('ownerDisputesEmpty', state.filtered.length === 0);
    App.renderTable('ownerDisputesTable', state.filtered, [
      { key: 'id', label: 'Mã tranh ch?p', render: (r) => `TC-${ownerShortId(gv(r, 'id'))}` },
      { key: 'hopdongthueid', label: 'H?p d?ng', render: (r) => App.escapeHtml(contractMap.get(gv(r, 'hopdongthueid')) || ownerContractCode(gv(r, 'hopdongthueid'))) },
      { key: 'lydo', label: 'Lý do', render: (r) => App.escapeHtml(String(gv(r, 'lydo') || '').slice(0, 90) || 'Chua c?p nh?t') },
      { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
      { key: 'actions', label: 'Thao tác', render: (_r, idx) => `
        <div class="table-actions">
          <button type="button" class="table-action-btn" data-owner-dispute-action="view" data-row="${idx}">Chi ti?t</button>
          <button type="button" class="table-action-btn ok" data-owner-dispute-action="copy" data-row="${idx}">Copy ID</button>
        </div>
      ` },
    ], { onRowClick: renderDetail });
  };

  const load = async () => {
    const [contracts, disputes] = await Promise.all([
      App.requestJson('GET', `${App.getApiBase()}/api/owner/contracts`),
      App.requestJson('GET', `${App.getApiBase()}/api/owner/disputes`),
    ]);
    contractMap.clear();
    arr(contracts.items).forEach((c) => contractMap.set(gv(c, 'id'), contractLabel(c)));
    App.renderSelect('contractId', arr(contracts.items), 'id', contractLabel, 'Ch?n h?p d?ng');
    state.all = arr(disputes.items);
    render();
  };

  $('toggleOwnerDisputeFormBtn')?.addEventListener('click', () => ownerTogglePanel(formPanelId, true));
  $('closeOwnerDisputeFormBtn')?.addEventListener('click', () => ownerTogglePanel(formPanelId, false));
  $('ownerDisputeSearch')?.addEventListener('input', render);
  $('ownerDisputeStatusFilter')?.addEventListener('change', render);
  $('ownerDisputesTable')?.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-owner-dispute-action]');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const row = state.filtered[Number(btn.getAttribute('data-row') || -1)];
    if (!row) return;
    const action = btn.getAttribute('data-owner-dispute-action');
    if (action === 'view') renderDetail(row);
    if (action === 'copy') await ownerCopy(gv(row, 'id'), 'Ðã sao chép mã tranh ch?p.');
  });

  try {
    await load();
  } catch (e) {
    ownerShowError('ownerDisputesMessage', e, 'Không th? t?i danh sách tranh ch?p lúc này.');
  }

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    try {
      App.setLoading(btn, true);
      const contractId = App.requireValue($('contractId')?.value, 'Chua ch?n h?p d?ng');
      const evidenceUrls = ($('evidenceUrls')?.value || '').split('\n').map((x) => x.trim()).filter(Boolean);
      const stepUpHeaders = await requireStepUpChallengeHeader();
      await App.requestJson('POST', `${App.getApiBase()}/api/contracts/${contractId}/damage-claim`, {
        lyDo: App.requireValue($('lyDo')?.value, 'Thi?u lý do'),
        estimatedCost: Number($('estimatedCost')?.value || 0),
        evidenceUrls,
        ghiChu: $('ownerGhiChu')?.value?.trim() || null,
      }, '', stepUpHeaders);
      App.showMessage('ownerDisputesMessage', 'Ðã g?i báo cáo hu h?i.', 'success');
      form.reset();
      ownerTogglePanel(formPanelId, false);
      await load();
    } catch (er) {
      ownerShowError('ownerDisputesMessage', er, 'Không th? g?i báo cáo lúc này, vui lòng th? l?i.');
    } finally {
      App.setLoading(btn, false);
    }
  });
}

async function initRenterVehiclesSimple() {
  await App.guardPage({ roles: ['khach', 'admin'] });
  const form = $('bookingForm');
  const map = new Map();
  const recalc = () => {
    const car = map.get($('xeId')?.value);
    const s = $('ngayBatDau')?.value;
    const e = $('ngayKetThuc')?.value;
    if (!car || !s || !e) return;
    const days = Math.max(1, Math.ceil((new Date(e).getTime() - new Date(s).getTime()) / 86400000));
    if ($('soNgayThue')) $('soNgayThue').value = String(days);
    if ($('tongTienThue')) $('tongTienThue').value = String(days * Number(gv(car, 'giatheongay') || 0));
  };
  const load = async () => {
    const data = await App.requestJson('GET', `${App.getApiBase()}/api/vehicles/public`, null, '');
    map.clear();
    arr(data.items).forEach((x) => map.set(gv(x, 'id'), x));
    const bookableVehicles = arr(data.items).filter((x) => vehicleCanBook(x));
    App.renderSelect('xeId', bookableVehicles, 'id', (v) => `${gv(v, 'bienso')} - ${gv(v, 'hangxe')} ${gv(v, 'dongxe')}`);
    App.renderTable('renterVehiclesTable', arr(data.items), [
      { key: 'bienso', label: 'Bi?n s?' }, { key: 'hangxe', label: 'Hãng xe' }, { key: 'dongxe', label: 'Dòng xe' },
      { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(vehicleDisplayStatus(r)) }, { key: 'giatheongay', label: 'Giá/ngày', render: (r) => App.formatMoney(gv(r, 'giatheongay')) },
    ]);
    if (!bookableVehicles.length) {
      App.showMessage('renterVehiclesMessage', 'Hi?n chua có xe ? tr?ng thái S?n sàng d? d?t.', 'info');
    }
  };
  try {
    await load();
  } catch (e) { App.showMessage('renterVehiclesMessage', e.message, 'error'); }
  ['xeId', 'ngayBatDau', 'ngayKetThuc'].forEach((id) => $(id)?.addEventListener('change', recalc));
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    try {
      App.setLoading(btn, true);
      recalc();
      const xeId = App.requireValue($('xeId')?.value, 'Chua ch?n xe');
      const selectedVehicle = map.get(xeId);
      if (!vehicleCanBook(selectedVehicle)) throw new Error('Xe dang ch? ho?c dang cho thuê, không th? d?t.');
      const res = await App.requestJson('POST', `${App.getApiBase()}/api/bookings`, {
        xeId,
        ngayBatDau: App.requireValue($('ngayBatDau')?.value, 'Thi?u ngày b?t d?u'),
        ngayKetThuc: App.requireValue($('ngayKetThuc')?.value, 'Thi?u ngày k?t thúc'),
        soNgayThue: Number($('soNgayThue')?.value || 1),
        tongTienThue: Number($('tongTienThue')?.value || 0),
        diaDiemNhan: App.requireValue($('diaDiemNhan')?.value, 'Thi?u d?a di?m nh?n'),
        ghiChu: $('bookingGhiChu')?.value?.trim() || null,
      });
      const contractId = res?.hopDongThue?.id || '';
      App.showMessage('renterVehiclesMessage', contractId ? `Ð?t xe thành công, h?p d?ng dã du?c t?o t? d?ng (${contractId}).` : 'Ð?t xe thành công, h?p d?ng dã du?c t?o t? d?ng.', 'success');
      form.reset();
      await load();
    } catch (er) { App.showMessage('renterVehiclesMessage', er.message, 'error'); }
    finally { App.setLoading(btn, false); }
  });
}

async function initOwnerBookingsSimple() {
  await App.guardPage({ roles: ['chuxe', 'admin'] });
  const root = $('ownerBookingsTable');
  const render = (items) => {
    const list = arr(items);
    if (!root) return;
    if (!list.length) {
      root.innerHTML = '<div class="empty-state">Chua có booking nào c?n x? lý.</div>';
      return;
    }
    root.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>Khách</th>
            <th>Ði?m uy tín</th>
            <th>Xe</th>
            <th>Ngày t?o</th>
            <th>H?n duy?t</th>
            <th>Countdown</th>
            <th>Mode auto</th>
            <th>Tr?ng thái</th>
            <th>Thao tác</th>
          </tr>
        </thead>
        <tbody>
          ${list.map((item, index) => `
            <tr data-index="${index}">
              <td>${App.escapeHtml(bookingRenterName(item))}</td>
              <td>${App.escapeHtml(String(gv(item?.renter || {}, 'diemUyTinSnapshot') || gv(item, 'diemuytinlucdat') || 0))}</td>
              <td>${App.escapeHtml(bookingVehicleLabel(item))}</td>
              <td>${App.escapeHtml(App.formatDate(gv(item, 'taoluc')))}</td>
              <td>${App.escapeHtml(App.formatDate(gv(item, 'hanDuyetLuc') || gv(item, 'handuyetluc')))}</td>
              <td>${App.escapeHtml(bookingCountdownLabel(item))}</td>
              <td>${App.escapeHtml(bookingModeLabel(gv(item, 'autoDecisionMode') || gv(item, 'chedotudong')))}</td>
              <td>${App.statusBadge(gv(item, 'decisionOutcomeLabel') || gv(item, 'trangthai'))}</td>
              <td>
                <div class="cta-row">
                  <button type="button" class="approve-booking-btn" data-id="${App.escapeHtml(gv(item, 'id'))}" ${gv(item, 'ownerActionAllowed') ? '' : 'disabled'}>Duy?t</button>
                  <button type="button" class="reject-booking-btn" data-id="${App.escapeHtml(gv(item, 'id'))}" ${gv(item, 'ownerActionAllowed') ? '' : 'disabled'}>T? ch?i</button>
                </div>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
    root.querySelectorAll('.approve-booking-btn').forEach((btn) => btn.addEventListener('click', async () => {
      try {
        App.setLoading(btn, true);
        await App.requestJson('POST', `${App.getApiBase()}/api/bookings/${btn.dataset.id}/approve`, {});
        App.showMessage('ownerBookingsMessage', 'Ðã duy?t booking và t?o h?p d?ng/ti?n c?c.', 'success');
        await load();
      } catch (error) {
        App.showMessage('ownerBookingsMessage', error.message, 'error');
      } finally {
        App.setLoading(btn, false);
      }
    }));
    root.querySelectorAll('.reject-booking-btn').forEach((btn) => btn.addEventListener('click', async () => {
      const lyDo = window.prompt('Nh?p lý do t? ch?i booking:', 'Ch? xe t? ch?i booking');
      if (!lyDo || !lyDo.trim()) return;
      try {
        App.setLoading(btn, true);
        await App.requestJson('POST', `${App.getApiBase()}/api/bookings/${btn.dataset.id}/reject`, { lyDo: lyDo.trim() });
        App.showMessage('ownerBookingsMessage', 'Ðã t? ch?i booking.', 'success');
        await load();
      } catch (error) {
        App.showMessage('ownerBookingsMessage', error.message, 'error');
      } finally {
        App.setLoading(btn, false);
      }
    }));
  };
  const load = async () => {
    const data = await App.requestJson('GET', `${App.getApiBase()}/api/owner/bookings`);
    render(data.items);
  };
  try {
    await load();
  } catch (e) {
    App.showMessage('ownerBookingsMessage', e.message, 'error');
  }
}

async function initRenterBookingsSimple() {
  await App.guardPage({ roles: ['khach', 'admin'] });
  try {
    const data = await App.requestJson('GET', `${App.getApiBase()}/api/renter/bookings`);
    App.renderTable('renterBookingsTable', arr(data.items), [
      { key: 'id', label: 'Booking' },
      { key: 'vehicle', label: 'Xe', render: (r) => App.escapeHtml(bookingVehicleLabel(r)) },
      { key: 'songaythue', label: 'S? ngày' },
      { key: 'autoDecisionMode', label: 'Mode auto', render: (r) => App.escapeHtml(bookingModeLabel(gv(r, 'autoDecisionMode') || gv(r, 'chedotudong'))) },
      { key: 'remainingSeconds', label: 'Th?i gian còn l?i', render: (r) => App.escapeHtml(bookingCountdownLabel(r)) },
      { key: 'decisionOutcomeLabel', label: 'K?t qu?', render: (r) => App.statusBadge(gv(r, 'decisionOutcomeLabel') || gv(r, 'trangthai')) },
    ]);
    App.showMessage('renterBookingsMessage', 'Booking s? ch? ch? xe duy?t. H?p d?ng và ti?n c?c ch? du?c t?o sau khi booking du?c duy?t.', 'info');
  } catch (e) { App.showMessage('renterBookingsMessage', e.message, 'error'); }
}

async function initRenterContractsSimple() {
  await App.guardPage({ roles: ['khach', 'admin'] });
  const map = new Map();
  const load = async () => {
    const data = await App.requestJson('GET', `${App.getApiBase()}/api/renter/contracts`);
    map.clear();
    arr(data.items).forEach((x) => map.set(gv(x, 'id'), x));
    const label = (c) => `${gv(c, 'id')} - ${contractFlowStatus(c)}`;
    App.renderSelect('lockContractId', arr(data.items), 'id', label);
    App.renderSelect('receiveContractId', arr(data.items), 'id', label);
    App.renderSelect('returnContractId', arr(data.items), 'id', label);
    App.renderSelect('settleContractId', arr(data.items), 'id', label);
    App.renderTable('renterContractsTable', arr(data.items), [
      { key: 'id', label: 'H?p d?ng' }, { key: 'xeid', label: 'Xe' }, { key: 'tongtiencoc', label: 'Ti?n c?c', render: (r) => App.formatMoney(gv(r, 'tongtiencoc')) },
      { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(contractFlowStatus(r)) },
    ]);
  };
  const syncSettle = () => {
    const c = map.get($('settleContractId')?.value);
    if (!c) return;
    $('tongTienThanhToan').value = String(Number(gv(c, 'tongtienthanhtoan') || gv(c, 'tongtiencoc') || 0));
    $('tongTienHoanLai').value = String(Number(gv(c, 'tongtienhoanlai') || 0));
  };
  try {
    await load();
    syncSettle();
  } catch (e) { App.showMessage('renterContractsMessage', e.message, 'error'); }
  $('settleContractId')?.addEventListener('change', syncSettle);
  $('lockDepositBtn')?.addEventListener('click', async () => {
    try {
      const stepUpHeaders = await requireStepUpChallengeHeader();
      await App.requestJson('POST', `${App.getApiBase()}/api/contracts/${App.requireValue($('lockContractId')?.value, 'Chua ch?n h?p d?ng')}/lock-deposit`, {}, '', stepUpHeaders);
      App.showMessage('renterContractsMessage', 'Ðã khóa c?c.', 'success');
      await load();
    } catch (er) { App.showMessage('renterContractsMessage', er.message, 'error'); }
  });
  $('confirmReceiveForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const id = App.requireValue($('receiveContractId')?.value, 'Chua ch?n h?p d?ng');
      const evidenceUrls = ($('receiveEvidenceUrls')?.value || '').split('\n').map((x) => x.trim()).filter(Boolean);
      const stepUpHeaders = await requireStepUpChallengeHeader();
      await App.requestJson('POST', `${App.getApiBase()}/api/contracts/${id}/renter-confirm-receive`, { ghiChu: App.requireValue($('receiveNote')?.value, 'Thi?u ghi chú nh?n xe'), evidenceUrls }, '', stepUpHeaders);
      App.showMessage('renterContractsMessage', 'Ðã xác nh?n nh?n xe.', 'success');
      await load();
    } catch (er) { App.showMessage('renterContractsMessage', er.message, 'error'); }
  });
  $('returnVehicleForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const id = App.requireValue($('returnContractId')?.value, 'Chua ch?n h?p d?ng');
      const evidenceUrls = ($('returnEvidenceUrls')?.value || '').split('\n').map((x) => x.trim()).filter(Boolean);
      const stepUpHeaders = await requireStepUpChallengeHeader();
      await App.requestJson('POST', `${App.getApiBase()}/api/contracts/${id}/return-vehicle`, { ghiChu: App.requireValue($('returnNote')?.value, 'Thi?u ghi chú'), evidenceUrls }, '', stepUpHeaders);
      App.showMessage('renterContractsMessage', 'Ðã xác nh?n tr? xe.', 'success');
      await load();
    } catch (er) { App.showMessage('renterContractsMessage', er.message, 'error'); }
  });
  $('settleForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitBtn = e.submitter || $('settleForm')?.querySelector('button[type="submit"]');
    try {
      if (submitBtn) submitBtn.disabled = true;
      const stepUpHeaders = await requireStepUpChallengeHeader();
      await App.requestJson('POST', `${App.getApiBase()}/api/contracts/${App.requireValue($('settleContractId')?.value, 'Chua ch?n h?p d?ng')}/settle`, {
        tongTienThanhToan: Number($('tongTienThanhToan')?.value || 0),
        tongTienHoanLai: Number($('tongTienHoanLai')?.value || 0),
      }, '', stepUpHeaders);
      App.showMessage('renterContractsMessage', 'Ðã t?t toán h?p d?ng.', 'success');
      await load();
    } catch (er) { App.showMessage('renterContractsMessage', er.message, 'error'); }
    finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
}

async function initRenterDepositsSimple() {
  await App.guardPage({ roles: ['khach', 'admin'] });
  try {
    const data = await App.requestJson('GET', `${App.getApiBase()}/api/renter/deposits`);
    App.renderTable('renterDepositsTable', arr(data.items), [
      { key: 'id', label: 'Mã c?c' }, { key: 'hopdongthueid', label: 'H?p d?ng' }, { key: 'tonghoacoc', label: 'T?ng c?c', render: (r) => App.formatMoney(gv(r, 'tonghoacoc')) },
      { key: 'trangthai', label: 'Tr?ng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
    ]);
  } catch (e) { App.showMessage('renterDepositsMessage', e.message, 'error'); }
}

PAGE_INIT.owner_vehicles = initOwnerVehiclesSimple;
PAGE_INIT.owner_availability = initOwnerAvailabilitySimple;
PAGE_INIT.owner_bookings = initOwnerBookingsSimple;
PAGE_INIT.owner_contracts = initOwnerContractsSimple;
PAGE_INIT.owner_disputes = initOwnerDisputesSimple;
PAGE_INIT.renter_vehicles = initRenterVehiclesSimple;
PAGE_INIT.renter_bookings = initRenterBookingsSimple;
PAGE_INIT.renter_contracts = initRenterContractsSimple;
PAGE_INIT.renter_deposits = initRenterDepositsSimple;







