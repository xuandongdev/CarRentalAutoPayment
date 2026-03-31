const $ = (id) => document.getElementById(id);
const arr = (v) => (Array.isArray(v) ? v : []);
const gv = (r, ...k) => { for (const x of k) { if (r && r[x] !== undefined && r[x] !== null) return r[x]; } return ''; };
const j = (v) => { try { return JSON.stringify(v ?? {}, null, 2); } catch { return String(v ?? ''); } };

const vehicleDisplayStatus = (row) => gv(row, 'displaytrangthailabel', 'displayTrangThaiLabel', 'trangthai');
const vehicleCanBook = (row) => {
  const value = gv(row, 'canbook', 'canBook', null);
  return value === true || value === 'true';
};

function disputePriority(row) {
  const status = String(gv(row, 'trangthai') || '');
  const amount = Number(gv(row, 'sotienphaithu') || 0);
  if (status === 'dangMo' || status === 'dangXuLy') return { label: 'Cao', cls: 'danger' };
  if (amount > 0) return { label: 'Trung bình', cls: 'pending' };
  return { label: 'Thấp', cls: 'ok' };
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

function confirmModal({ title, message, confirmText = 'Xác nhận', danger = false }) {
  return new Promise((resolve) => {
    const root = ensureModalRoot();
    root.innerHTML = `
      <div class="modal-overlay">
        <div class="modal-card">
          <h3>${App.escapeHtml(title || 'Xác nhận thao tác')}</h3>
          <p>${App.escapeHtml(message || '')}</p>
          <div class="modal-actions">
            <button type="button" id="modalCancelBtn" class="btn-link secondary">Hủy</button>
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
          <h3>${isDamage ? 'Xác nhận có hư hại' : 'Xác nhận không hư hại'}</h3>
          <p>Tranh chấp: <strong>${App.escapeHtml(gv(row, 'id'))}</strong></p>
          ${isDamage ? `
            <label>Chi phí duyệt
              <input id="modalApprovedCost" type="number" min="0" step="0.01" data-required="true">
            </label>
          ` : ''}
          <label>Kết luận
            <textarea id="modalDecisionNote" data-required="true" placeholder="Nhập kết luận xử lý"></textarea>
          </label>
          <div class="modal-actions">
            <button type="button" id="modalCancelBtn" class="btn-link secondary">Hủy</button>
            <button type="button" id="modalConfirmBtn" class="btn-link ${isDamage ? 'danger' : ''}">Xác nhận</button>
          </div>
        </div>
      </div>
    `;
    App.setRequiredMarkers();
    const done = (val) => { closeModal(); resolve(val); };
    document.getElementById('modalCancelBtn')?.addEventListener('click', () => done(null));
    document.getElementById('modalConfirmBtn')?.addEventListener('click', () => {
      try {
        const decisionNote = App.requireValue(document.getElementById('modalDecisionNote')?.value, 'Thiếu kết luận');
        if (!isDamage) return done({ decisionNote });
        const approvedCost = Number(App.requireValue(document.getElementById('modalApprovedCost')?.value, 'Thiếu chi phí duyệt'));
        done({ decisionNote, approvedCost });
      } catch (e) {
        alert(e.message);
      }
    });
  });
}
function setInspector(title, data, events = [], tx = []) {
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
  if (!row) return ($(id).innerHTML = '<div class="empty-state">Chọn bản ghi để xem chi tiết.</div>');
  const html = Object.entries(row).slice(0, 18).map(([k, v]) => `<div class="kv"><span>${App.escapeHtml(k)}</span><strong>${App.escapeHtml(typeof v === 'object' ? JSON.stringify(v) : String(v))}</strong></div>`).join('');
  $(id).innerHTML = `<div class="detail-grid">${html}</div>`;
}

async function initLanding() {
  await App.guardPage();
  try {
    const data = await App.requestJson('GET', `${App.getApiBase()}/api/vehicles/public`, null, '');
    App.renderTable('featuredVehicles', arr(data.items), [
      { key: 'bienso', label: 'Biển số' },
      { key: 'hangxe', label: 'Hãng xe' },
      { key: 'dongxe', label: 'Dòng xe' },
      { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(vehicleDisplayStatus(r)) },
      { key: 'giatheongay', label: 'Giá/ngày', render: (r) => App.formatMoney(gv(r, 'giatheongay')) },
    ]);
  } catch (e) { App.showMessage('landingMessage', e.message, 'error'); }
}

async function initLogin() {
  await App.guardPage({ guestOnly: true });
  const form = $('loginForm');
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    try {
      App.setLoading(btn, true);
      const data = await App.requestJson('POST', `${App.getApiBase()}/auth/login`, {
        identifier: App.requireValue($('identifier')?.value, 'Thiếu identifier'),
        password: App.requireValue($('password')?.value, 'Thiếu password'),
      }, '');
      App.setToken(data.accessToken);
      App.redirectByRole(data?.user?.vaiTro);
    } catch (e2) { App.showMessage('loginMessage', e2.message, 'error'); } finally { App.setLoading(btn, false); }
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
      const password = App.requireValue($('password')?.value, 'Thiếu mật khẩu');
      if (password !== App.requireValue($('confirmPassword')?.value, 'Thiếu xác nhận mật khẩu')) throw new Error('Mật khẩu không khớp');
      await App.requestJson('POST', `${App.getApiBase()}/auth/register`, {
        hoTen: App.requireValue($('hoTen')?.value, 'Thiếu họ tên'), email: $('email')?.value?.trim() || '', soDienThoai: $('soDienThoai')?.value?.trim() || '', password,
      }, '');
      App.showMessage('registerMessage', 'Đăng ký thành công, vui lòng đăng nhập.', 'success');
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
      ...arr(overview.vehicles).filter((v) => gv(v, 'trangthai') === 'choDuyet').map((x) => ({ type: 'vehicle', id: x.id, label: `Duyệt xe ${gv(x, 'bienso')}`, row: x })),
      ...arr(overview.disputes).filter((v) => ['dangMo', 'dangXuLy'].includes(gv(v, 'trangthai'))).map((x) => ({ type: 'dispute', id: x.id, label: `Xử lý tranh chấp ${x.id}`, row: x })),
    ];
    App.renderTable('adminWorkbenchTable', work, [
      { key: 'type', label: 'Loại' }, { key: 'label', label: 'Công việc' }, { key: 'id', label: 'ID' },
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

async function initAdminUsers() { return initAdminList('Người dùng', '/api/admin/users', [
  { key: 'hoten', label: 'Họ tên' }, { key: 'email', label: 'Email' }, { key: 'sodienthoai', label: 'Điện thoại' },
  { key: 'vaitro', label: 'Vai trò', render: (r) => App.statusBadge(gv(r, 'vaitro')) }, { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
]); }

async function initAdminVehicles() {
  await App.guardPage({ roles: ['admin'] });
  const updateStatus = async (row, trangThai) => {
    const ok = await confirmModal({
      title: 'Xác nhận cập nhật trạng thái xe',
      message: `Xe ${gv(row, 'bienso')} sẽ chuyển sang trạng thái ${trangThai}.`,
      confirmText: 'Cập nhật',
    });
    if (!ok) return;
    await App.requestJson('PATCH', `${App.getApiBase()}/api/admin/vehicles/${gv(row, 'id')}/status`, { trangThai });
    App.showMessage('adminListMessage', `Đã cập nhật xe ${gv(row, 'bienso')} -> ${trangThai}.`, 'success');
    await initAdminVehicles();
  };

  try {
    const res = await App.requestJson('GET', `${App.getApiBase()}/api/admin/vehicles`);
    const rows = arr(res.items);
    $('adminListCounter').textContent = rows.length;
    App.renderTable('adminListTable', rows, [
      { key: 'bienso', label: 'Biển số' },
      { key: 'hangxe', label: 'Hãng xe' },
      { key: 'dongxe', label: 'Dòng xe' },
      { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
      { key: 'giatheongay', label: 'Giá/ngày', render: (r) => App.formatMoney(gv(r, 'giatheongay')) },
      {
        key: 'actions',
        label: 'Thao tác nhanh',
        render: (_r, idx) => `
          <div class="table-actions">
            <button type="button" class="table-action-btn ok" data-admin-action="vehicle-approve" data-row="${idx}">Duyệt</button>
            <button type="button" class="table-action-btn pending" data-admin-action="vehicle-maintain" data-row="${idx}">Bảo trì</button>
            <button type="button" class="table-action-btn danger" data-admin-action="vehicle-stop" data-row="${idx}">Ngừng</button>
          </div>
        `,
      },
    ], {
      onRowClick: async (row) => {
        setDetail('adminEntityDetail', row);
        setInspector(`Xe ${gv(row, 'bienso')}`, row);
        if ($('adminModuleActions')) {
          $('adminModuleActions').innerHTML = `
            <label>Trạng thái mới
              <select id="adminVehicleStatusSelect">
                <option value="choDuyet">choDuyet</option>
                <option value="sanSang">sanSang</option>
                <option value="dangThue">dangThue</option>
                <option value="baoTri">baoTri</option>
                <option value="ngungHoatDong">ngungHoatDong</option>
              </select>
            </label>
            <button id="adminApproveVehicleBtn" type="button">Cập nhật trạng thái xe đang chọn</button>
          `;
          $('adminVehicleStatusSelect').value = gv(row, 'trangthai') || 'choDuyet';
          $('adminApproveVehicleBtn').onclick = async () => {
            try {
              const btn = $('adminApproveVehicleBtn');
              App.setLoading(btn, true);
              await updateStatus(row, App.requireValue($('adminVehicleStatusSelect')?.value, 'Thiếu trạng thái'));
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
  { key: 'songaythue', label: 'Số ngày' }, { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
], (r) => gv(r, 'hopdongthueid')); }

async function initAdminContracts() { return initAdminList('Hợp đồng', '/api/admin/contracts', [
  { key: 'id', label: 'Mã hợp đồng' }, { key: 'xeid', label: 'Xe' }, { key: 'nguoithueid', label: 'Khách thuê' },
  { key: 'chuxeid', label: 'Chủ xe' }, { key: 'tongtiencoc', label: 'Tiền cọc', render: (r) => App.formatMoney(gv(r, 'tongtiencoc')) },
  { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
], (r) => gv(r, 'id')); }

async function initAdminDisputes() {
  await App.guardPage({ roles: ['admin'] });
  const applyNoDamage = async (row) => {
    const data = await disputeDecisionModal({ row, mode: 'no-damage' });
    if (!data) return;
    await App.requestJson('POST', `${App.getApiBase()}/api/disputes/${gv(row, 'id')}/admin-confirm-no-damage`, {
      decisionNote: data.decisionNote,
    });
    App.showMessage('adminListMessage', `Đã xử lý tranh chấp ${gv(row, 'id')} (không hư hại).`, 'success');
    await initAdminDisputes();
  };
  const applyDamage = async (row) => {
    const data = await disputeDecisionModal({ row, mode: 'damage' });
    if (!data) return;
    await App.requestJson('POST', `${App.getApiBase()}/api/disputes/${gv(row, 'id')}/admin-confirm-damage`, {
      approvedCost: data.approvedCost,
      decisionNote: data.decisionNote,
    });
    App.showMessage('adminListMessage', `Đã xử lý tranh chấp ${gv(row, 'id')} (có hư hại).`, 'success');
    await initAdminDisputes();
  };
  try {
    const res = await App.requestJson('GET', `${App.getApiBase()}/api/admin/disputes`);
    const rows = arr(res.items);
    $('adminListCounter').textContent = rows.length;
    App.renderTable('adminListTable', rows, [
      { key: 'id', label: 'Mã tranh chấp' },
      { key: 'hopdongthueid', label: 'Hợp đồng' },
      { key: 'lydo', label: 'Lý do' },
      {
        key: 'priority',
        label: 'Ưu tiên',
        render: (r) => {
          const p = disputePriority(r);
          return `<span class="badge ${p.cls}">${p.label}</span>`;
        },
      },
      { key: 'sotienphaithu', label: 'Số tiền', render: (r) => App.formatMoney(gv(r, 'sotienphaithu')) },
      { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
      {
        key: 'actions',
        label: 'Thao tác nhanh',
        render: (_r, idx) => `
          <div class="table-actions">
            <button type="button" class="table-action-btn ok" data-admin-action="dispute-no-damage" data-row="${idx}">Không hư hại</button>
            <button type="button" class="table-action-btn danger" data-admin-action="dispute-damage" data-row="${idx}">Có hư hại</button>
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
        setInspector(`Tranh chấp ${gv(row, 'id')}`, row, arr(flow.events), arr(flow.transactions));
        if ($('adminModuleActions')) {
          $('adminModuleActions').innerHTML = `
            <div class="table-actions">
              <button id="adminNoDamageBtn" type="button" class="table-action-btn ok">Xác nhận không hư hại</button>
              <button id="adminDamageBtn" type="button" class="table-action-btn danger">Xác nhận có hư hại</button>
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

async function initOwnerDashboard() {
  const session = await App.guardPage({ roles: ['chuxe', 'admin'] });
  if (session && $('welcomeUser')) $('welcomeUser').textContent = `Xin chào, ${session?.user?.hoTen || 'chủ xe'}`;
  try {
    const [dash, vehicles, disputes] = await Promise.all([
      App.requestJson('GET', `${App.getApiBase()}/api/dashboard`),
      App.requestJson('GET', `${App.getApiBase()}/api/owner/vehicles`),
      App.requestJson('GET', `${App.getApiBase()}/api/owner/disputes`),
    ]);
    const rows = arr(vehicles.items);
    $('kpiVehicles').textContent = rows.length;
    $('kpiPending').textContent = rows.filter((r) => gv(r, 'trangthai') === 'choDuyet').length;
    $('kpiActiveRent').textContent = rows.filter((r) => gv(r, 'trangthai') === 'dangThue').length;
    $('kpiContracts').textContent = dash?.stats?.contracts || 0;
    $('kpiDisputes').textContent = arr(disputes.items).length;
    App.renderTable('ownerRecentVehicles', rows.slice(0, 6), [
      { key: 'bienso', label: 'Biển số' }, { key: 'hangxe', label: 'Hãng xe' }, { key: 'dongxe', label: 'Dòng xe' }, { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(vehicleDisplayStatus(r)) },
    ]);
  } catch (e) { App.showMessage('ownerDashboardMessage', e.message, 'error'); }
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
    $('kpiActive').textContent = arr(contracts.items).filter((c) => gv(c, 'trangthai') === 'dangThue').length;
    App.renderTable('renterRecentBookings', arr(bookings.items).slice(0, 6), [
      { key: 'id', label: 'Booking' }, { key: 'xeid', label: 'Xe' }, { key: 'songaythue', label: 'Số ngày' },
      { key: 'tongtienthue', label: 'Tổng tiền', render: (r) => App.formatMoney(gv(r, 'tongtienthue')) }, { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
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
    $('chainSyncStatus').textContent = summary?.latestBlock?.hash ? `Đồng bộ đến block #${summary.latestBlock.blockheight}` : 'Chưa có dữ liệu block';

    App.renderTable('financeTransactionsTable', arr(data.transactions), [
      { key: 'txHash', label: 'Tx hash' }, { key: 'txType', label: 'Loại giao dịch' }, { key: 'amount', label: 'Số tiền', render: (r) => App.formatMoney(gv(r, 'amount')) },
      { key: 'fromAddress', label: 'Từ' }, { key: 'toAddress', label: 'Đến' },
      { key: 'status', label: 'Trạng thái', render: (r) => App.statusBadge(gv(r, 'status') || 'pending') },
      { key: 'timestamp', label: 'Thời gian', render: (r) => App.formatDate(gv(r, 'timestamp')) },
    ], { onRowClick: async (row) => {
      setDetail('financeTxDetail', row);
      let flow = { events: [], transactions: [] };
      if (gv(row, 'contractId')) { try { flow = await App.requestJson('GET', `${App.getApiBase()}/api/contracts/${gv(row, 'contractId')}/money-flow`); } catch {} }
      setInspector(`Giao dịch ${gv(row, 'txHash')}`, row, arr(flow.events), arr(flow.transactions));
    }});
  };

  $('financeFiltersForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const q = new URLSearchParams();
      ['walletAddress', 'txType', 'contractId', 'disputeId'].forEach((id) => { const v = $(id)?.value?.trim(); if (v) q.set(id, v); });
      const data = await App.requestJson('GET', `${App.getApiBase()}/api/finance/transactions${q.toString() ? '?' + q.toString() : ''}`);
      App.renderTable('financeTransactionsTable', arr(data.transactions), [
        { key: 'txHash', label: 'Tx hash' }, { key: 'txType', label: 'Loại giao dịch' }, { key: 'amount', label: 'Số tiền', render: (r) => App.formatMoney(gv(r, 'amount')) },
        { key: 'fromAddress', label: 'Từ' }, { key: 'toAddress', label: 'Đến' }, { key: 'status', label: 'Trạng thái', render: (r) => App.statusBadge(gv(r, 'status') || 'pending') },
      ], { onRowClick: (row) => { setDetail('financeTxDetail', row); setInspector(`Giao dịch ${gv(row, 'txHash')}`, row); } });
    } catch (er) { App.showMessage('financeMessage', er.message, 'error'); }
  });

  try { await load(); } catch (e) { App.showMessage('financeMessage', e.message, 'error'); }
}

async function initChain() {
  await App.guardPage({ roles: ['admin'] });
  try {
    const chain = await App.requestJson('GET', `${App.getApiBase()}/api/node/chain`);
    if ($('chainJson')) $('chainJson').textContent = j(chain);
    setInspector('Dữ liệu chuỗi', chain);
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
  const fn = PAGE_INIT[document.body?.dataset?.page];
  if (!fn) return;
  try { await fn(); } catch (e) { if ($('pageMessage')) { $('pageMessage').textContent = e.message; $('pageMessage').className = 'message error'; } }
});

async function initOwnerVehiclesSimple() {
  await App.guardPage({ roles: ['chuxe', 'admin'] });
  const form = $('vehicleForm');
  const load = async () => {
    const data = await App.requestJson('GET', `${App.getApiBase()}/api/owner/vehicles`);
    App.renderTable('ownerVehiclesTable', arr(data.items), [
      { key: 'bienso', label: 'Biển số' }, { key: 'hangxe', label: 'Hãng xe' }, { key: 'dongxe', label: 'Dòng xe' },
      { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(vehicleDisplayStatus(r)) }, { key: 'giatheongay', label: 'Giá/ngày', render: (r) => App.formatMoney(gv(r, 'giatheongay')) },
    ]);
  };
  try {
    await load();
  } catch (e) { App.showMessage('ownerVehicleMessage', e.message, 'error'); }
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await App.requestJson('POST', `${App.getApiBase()}/api/vehicles`, {
        bienSo: App.requireValue($('bienSo')?.value, 'Thiếu biển số'),
        hangXe: App.requireValue($('hangXe')?.value, 'Thiếu hãng xe'),
        dongXe: App.requireValue($('dongXe')?.value, 'Thiếu dòng xe'),
        loaiXe: App.requireValue($('loaiXe')?.value, 'Thiếu loại xe'),
        namSanXuat: $('namSanXuat')?.value ? Number($('namSanXuat')?.value) : null,
        moTa: $('moTa')?.value?.trim() || null,
        giaTheoNgay: Number($('giaTheoNgay')?.value || 0),
        giaTheoGio: Number($('giaTheoGio')?.value || 0),
        baoHiem: $('baoHiem')?.value?.trim() || null,
        dangKiem: $('dangKiem')?.value?.trim() || null,
        dangKyXe: $('dangKyXe')?.value?.trim() || null,
        ngayHetHanDangKiem: $('ngayHetHanDangKiem')?.value || null,
      });
      App.showMessage('ownerVehicleMessage', 'Đã lưu xe thành công.', 'success');
      form.reset();
      await load();
    } catch (er) { App.showMessage('ownerVehicleMessage', er.message, 'error'); }
  });
}

async function initOwnerAvailabilitySimple() {
  await App.guardPage({ roles: ['chuxe', 'admin'] });
  const form = $('availabilityForm');
  const load = async () => {
    const [vehicles, slots] = await Promise.all([
      App.requestJson('GET', `${App.getApiBase()}/api/owner/vehicles`),
      App.requestJson('GET', `${App.getApiBase()}/api/owner/availability`),
    ]);
    App.renderSelect('xeId', arr(vehicles.items), 'id', (v) => `${gv(v, 'bienso')} - ${gv(v, 'hangxe')}`);
    App.renderTable('ownerAvailabilityTable', arr(slots.items), [
      { key: 'xeid', label: 'Xe' }, { key: 'ngaybatdau', label: 'Bắt đầu', render: (r) => App.formatDate(gv(r, 'ngaybatdau')) },
      { key: 'ngayketthuc', label: 'Kết thúc', render: (r) => App.formatDate(gv(r, 'ngayketthuc')) }, { key: 'controng', label: 'Còn trống', render: (r) => App.statusBadge(gv(r, 'controng') ? 'Có' : 'Không') },
    ]);
  };
  try {
    await load();
  } catch (e) { App.showMessage('ownerAvailabilityMessage', e.message, 'error'); }
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await App.requestJson('POST', `${App.getApiBase()}/api/owner/availability`, {
        xeId: App.requireValue($('xeId')?.value, 'Chưa chọn xe'),
        ngayBatDau: App.requireValue($('ngayBatDau')?.value, 'Thiếu ngày bắt đầu'),
        ngayKetThuc: App.requireValue($('ngayKetThuc')?.value, 'Thiếu ngày kết thúc'),
        conTrong: $('conTrong')?.value !== 'false',
        ghiChu: $('ghiChu')?.value?.trim() || null,
      });
      App.showMessage('ownerAvailabilityMessage', 'Đã lưu lịch trống.', 'success');
      form.reset();
      await load();
    } catch (er) { App.showMessage('ownerAvailabilityMessage', er.message, 'error'); }
  });
}

async function initOwnerContractsSimple() {
  await App.guardPage({ roles: ['chuxe', 'admin'] });
  try {
    const data = await App.requestJson('GET', `${App.getApiBase()}/api/owner/contracts`);
    App.renderTable('ownerContractsTable', arr(data.items), [
      { key: 'id', label: 'Hợp đồng' }, { key: 'xeid', label: 'Xe' }, { key: 'nguoithueid', label: 'Khách thuê' },
      { key: 'tongtiencoc', label: 'Tiền cọc', render: (r) => App.formatMoney(gv(r, 'tongtiencoc')) }, { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
    ]);
  } catch (e) { App.showMessage('ownerContractsMessage', e.message, 'error'); }
}

async function initOwnerDisputesSimple() {
  await App.guardPage({ roles: ['chuxe', 'admin'] });
  const form = $('ownerDamageForm');
  const load = async () => {
    const [contracts, disputes] = await Promise.all([
      App.requestJson('GET', `${App.getApiBase()}/api/owner/contracts`),
      App.requestJson('GET', `${App.getApiBase()}/api/owner/disputes`),
    ]);
    App.renderSelect('contractId', arr(contracts.items), 'id', (c) => `${gv(c, 'id')} (${gv(c, 'trangthai')})`);
    App.renderTable('ownerDisputesTable', arr(disputes.items), [
      { key: 'id', label: 'Mã tranh chấp' }, { key: 'hopdongthueid', label: 'Hợp đồng' }, { key: 'lydo', label: 'Lý do' },
      { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
    ]);
  };
  try {
    await load();
  } catch (e) { App.showMessage('ownerDisputesMessage', e.message, 'error'); }
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const contractId = App.requireValue($('contractId')?.value, 'Chưa chọn hợp đồng');
      const evidenceUrls = ($('evidenceUrls')?.value || '').split('\n').map((x) => x.trim()).filter(Boolean);
      await App.requestJson('POST', `${App.getApiBase()}/api/contracts/${contractId}/damage-claim`, {
        lyDo: App.requireValue($('lyDo')?.value, 'Thiếu lý do'),
        estimatedCost: Number($('estimatedCost')?.value || 0),
        evidenceUrls,
        ghiChu: $('ownerGhiChu')?.value?.trim() || null,
      });
      App.showMessage('ownerDisputesMessage', 'Đã gửi báo cáo hư hại.', 'success');
      form.reset();
      await load();
    } catch (er) { App.showMessage('ownerDisputesMessage', er.message, 'error'); }
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
      { key: 'bienso', label: 'Biển số' }, { key: 'hangxe', label: 'Hãng xe' }, { key: 'dongxe', label: 'Dòng xe' },
      { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(vehicleDisplayStatus(r)) }, { key: 'giatheongay', label: 'Giá/ngày', render: (r) => App.formatMoney(gv(r, 'giatheongay')) },
    ]);
    if (!bookableVehicles.length) {
      App.showMessage('renterVehiclesMessage', 'Hiện chưa có xe ở trạng thái Sẵn sàng để đặt.', 'info');
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
      const xeId = App.requireValue($('xeId')?.value, 'Chưa chọn xe');
      const selectedVehicle = map.get(xeId);
      if (!vehicleCanBook(selectedVehicle)) throw new Error('Xe đang chờ hoặc đang cho thuê, không thể đặt.');
      const res = await App.requestJson('POST', `${App.getApiBase()}/api/bookings`, {
        xeId,
        ngayBatDau: App.requireValue($('ngayBatDau')?.value, 'Thiếu ngày bắt đầu'),
        ngayKetThuc: App.requireValue($('ngayKetThuc')?.value, 'Thiếu ngày kết thúc'),
        soNgayThue: Number($('soNgayThue')?.value || 1),
        tongTienThue: Number($('tongTienThue')?.value || 0),
        diaDiemNhan: App.requireValue($('diaDiemNhan')?.value, 'Thiếu địa điểm nhận'),
        ghiChu: $('bookingGhiChu')?.value?.trim() || null,
      });
      const contractId = res?.hopDongThue?.id || '';
      App.showMessage('renterVehiclesMessage', contractId ? `Đặt xe thành công, hợp đồng đã được tạo tự động (${contractId}).` : 'Đặt xe thành công, hợp đồng đã được tạo tự động.', 'success');
      form.reset();
      await load();
    } catch (er) { App.showMessage('renterVehiclesMessage', er.message, 'error'); }
    finally { App.setLoading(btn, false); }
  });
}

async function initRenterBookingsSimple() {
  await App.guardPage({ roles: ['khach', 'admin'] });
  try {
    const data = await App.requestJson('GET', `${App.getApiBase()}/api/renter/bookings`);
    App.renderTable('renterBookingsTable', arr(data.items), [
      { key: 'id', label: 'Booking' }, { key: 'xeid', label: 'Xe' }, { key: 'songaythue', label: 'Số ngày' },
      { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
    ]);
    App.showMessage('renterBookingsMessage', 'Hợp đồng được tạo tự động ngay khi đặt xe thành công.', 'info');
  } catch (e) { App.showMessage('renterBookingsMessage', e.message, 'error'); }
}

async function initRenterContractsSimple() {
  await App.guardPage({ roles: ['khach', 'admin'] });
  const map = new Map();
  const load = async () => {
    const data = await App.requestJson('GET', `${App.getApiBase()}/api/renter/contracts`);
    map.clear();
    arr(data.items).forEach((x) => map.set(gv(x, 'id'), x));
    const label = (c) => `${gv(c, 'id')} - ${gv(c, 'trangthai')}`;
    App.renderSelect('lockContractId', arr(data.items), 'id', label);
    App.renderSelect('returnContractId', arr(data.items), 'id', label);
    App.renderSelect('settleContractId', arr(data.items), 'id', label);
    App.renderTable('renterContractsTable', arr(data.items), [
      { key: 'id', label: 'Hợp đồng' }, { key: 'xeid', label: 'Xe' }, { key: 'tongtiencoc', label: 'Tiền cọc', render: (r) => App.formatMoney(gv(r, 'tongtiencoc')) },
      { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
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
      await App.requestJson('POST', `${App.getApiBase()}/api/contracts/${App.requireValue($('lockContractId')?.value, 'Chưa chọn hợp đồng')}/lock-deposit`, {});
      App.showMessage('renterContractsMessage', 'Đã khóa cọc.', 'success');
      await load();
    } catch (er) { App.showMessage('renterContractsMessage', er.message, 'error'); }
  });
  $('returnVehicleForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const id = App.requireValue($('returnContractId')?.value, 'Chưa chọn hợp đồng');
      const evidenceUrls = ($('returnEvidenceUrls')?.value || '').split('\n').map((x) => x.trim()).filter(Boolean);
      await App.requestJson('POST', `${App.getApiBase()}/api/contracts/${id}/return-vehicle`, { ghiChu: App.requireValue($('returnNote')?.value, 'Thiếu ghi chú'), evidenceUrls });
      App.showMessage('renterContractsMessage', 'Đã xác nhận trả xe.', 'success');
      await load();
    } catch (er) { App.showMessage('renterContractsMessage', er.message, 'error'); }
  });
  $('settleForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitBtn = e.submitter || $('settleForm')?.querySelector('button[type="submit"]');
    try {
      if (submitBtn) submitBtn.disabled = true;
      await App.requestJson('POST', `${App.getApiBase()}/api/contracts/${App.requireValue($('settleContractId')?.value, 'Chưa chọn hợp đồng')}/settle`, {
        tongTienThanhToan: Number($('tongTienThanhToan')?.value || 0),
        tongTienHoanLai: Number($('tongTienHoanLai')?.value || 0),
      });
      App.showMessage('renterContractsMessage', 'Đã tất toán hợp đồng.', 'success');
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
      { key: 'id', label: 'Mã cọc' }, { key: 'hopdongthueid', label: 'Hợp đồng' }, { key: 'tonghoacoc', label: 'Tổng cọc', render: (r) => App.formatMoney(gv(r, 'tonghoacoc')) },
      { key: 'trangthai', label: 'Trạng thái', render: (r) => App.statusBadge(gv(r, 'trangthai')) },
    ]);
  } catch (e) { App.showMessage('renterDepositsMessage', e.message, 'error'); }
}

PAGE_INIT.owner_vehicles = initOwnerVehiclesSimple;
PAGE_INIT.owner_availability = initOwnerAvailabilitySimple;
PAGE_INIT.owner_contracts = initOwnerContractsSimple;
PAGE_INIT.owner_disputes = initOwnerDisputesSimple;
PAGE_INIT.renter_vehicles = initRenterVehiclesSimple;
PAGE_INIT.renter_bookings = initRenterBookingsSimple;
PAGE_INIT.renter_contracts = initRenterContractsSimple;
PAGE_INIT.renter_deposits = initRenterDepositsSimple;


