HTML_PAGE = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Car Rental Demo</title>
  <style>
    body { font-family: Arial, sans-serif; background:#f5f6f8; margin:0; padding:24px; }
    .wrap { max-width: 1400px; margin: 0 auto; }
    h1 { margin-top:0; }
    .grid { display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:16px; }
    .card { background:white; border-radius:14px; padding:16px; box-shadow:0 1px 3px rgba(0,0,0,.08); }
    label { display:block; font-size:14px; margin-top:8px; color:#333; }
    input, button, textarea { width:100%; box-sizing:border-box; padding:10px 12px; margin-top:6px; border:1px solid #d0d5dd; border-radius:10px; }
    textarea { min-height: 90px; resize: vertical; }
    button { cursor:pointer; background:#111827; color:white; border:none; font-weight:600; }
    button.secondary { background:#2563eb; }
    pre { background:#0f172a; color:#e2e8f0; padding:12px; border-radius:10px; overflow:auto; max-height:360px; }
    .section { margin-top:16px; }
    @media (max-width: 900px) { .grid { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="grid">
      <div class="card">
        <h3>1. Them xe</h3>
        <label>Email chu xe <input id="ownerEmail" value="chuxe1@example.com"></label>
        <label>Bien so <input id="bienSo" value="51A-99999"></label>
        <label>Hang xe <input id="hangXe" value="Toyota"></label>
        <label>Dong xe <input id="dongXe" value="Vios"></label>
        <label>Loai xe <input id="loaiXe" value="Sedan"></label>
        <label>Gia theo ngay <input id="giaTheoNgay" value="800000"></label>
        <label>Gia theo gio <input id="giaTheoGio" value="120000"></label>
        <button onclick="addVehicle()">Them xe</button>
      </div>
      <div class="card">
        <h3>2. Tao dang ky thue xe</h3>
        <label>Email nguoi thue <input id="renterEmail" value="khach1@example.com"></label>
        <label>Bien so xe <input id="bookingBienSo" value="51A-99999"></label>
        <label>So ngay thue <input id="soNgayThue" value="2"></label>
        <label>Dia diem nhan <input id="diaDiemNhan" value="Regent Phu Quoc"></label>
        <label>Tong tien thue <input id="tongTienThue" value="1600000"></label>
        <button onclick="createBooking()">Tao dang ky</button>
      </div>
      <div class="card">
        <h3>3. Tao hop dong tu dang ky</h3>
        <label>Dang ky ID <input id="dangKyId" placeholder="copy tu ket qua"></label>
        <label>Tong tien coc <input id="tongTienCoc" value="2000000"></label>
        <button class="secondary" onclick="createContract()">Tao hop dong</button>
      </div>
      <div class="card">
        <h3>4. Khoa coc</h3>
        <label>Hop dong ID <input id="hopDongIdLock" placeholder="copy contract id"></label>
        <button onclick="lockDeposit()">Khoa coc va mine block</button>
      </div>
      <div class="card">
        <h3>5. Khach tra xe</h3>
        <label>Hop dong ID <input id="hopDongIdReturn" placeholder="copy contract id"></label>
        <label>Nguoi tra ID <input id="nguoiTraId" placeholder="nguoi thue id"></label>
        <label>Ghi chu <input id="returnGhiChu" value="Khach da tra xe"></label>
        <label>Evidence URLs JSON <textarea id="returnEvidenceUrls">["https://example.com/return-1.jpg"]</textarea></label>
        <label>Evidence Meta JSON <textarea id="returnEvidenceMeta">{"camera":"gate-1"}</textarea></label>
        <button onclick="returnVehicle()">Return vehicle</button>
      </div>
      <div class="card">
        <h3>6. Owner khieu nai hu hai</h3>
        <label>Hop dong ID <input id="hopDongIdDamageClaim" placeholder="copy contract id"></label>
        <label>Owner ID <input id="damageOwnerId" placeholder="chu xe id"></label>
        <label>Ly do <input id="damageLyDo" value="Xe bi tray xuoc can sau"></label>
        <label>Estimated cost <input id="damageEstimatedCost" value="1200000"></label>
        <label>Ghi chu <input id="damageGhiChu" value="Phat hien sau khi nhan lai xe"></label>
        <label>Evidence URLs JSON <textarea id="damageEvidenceUrls">["https://example.com/damage-1.jpg"]</textarea></label>
        <label>Evidence Meta JSON <textarea id="damageEvidenceMeta">{"angle":"rear-bumper"}</textarea></label>
        <button onclick="createDamageClaim()">Damage claim</button>
      </div>
      <div class="card">
        <h3>7. Admin xac nhan khong hu hai</h3>
        <label>Dispute ID <input id="disputeIdNoDamage" placeholder="copy dispute id"></label>
        <label>Admin ID <input id="adminIdNoDamage" placeholder="admin id"></label>
        <label>Decision note <textarea id="decisionNoteNoDamage">Da doi chieu anh giao xe va anh tra xe, khong co hu hai moi</textarea></label>
        <label>Evidence Meta JSON <textarea id="decisionMetaNoDamage">{"review":"matched-images"}</textarea></label>
        <button class="secondary" onclick="adminConfirmNoDamage()">Admin confirm no damage</button>
      </div>
      <div class="card">
        <h3>8. Admin xac nhan co hu hai</h3>
        <label>Dispute ID <input id="disputeIdDamage" placeholder="copy dispute id"></label>
        <label>Admin ID <input id="adminIdDamage" placeholder="admin id"></label>
        <label>Approved cost <input id="approvedCost" value="1000000"></label>
        <label>Decision note <textarea id="decisionNoteDamage">Xac nhan hu hai thuc te</textarea></label>
        <label>Evidence Meta JSON <textarea id="decisionMetaDamage">{"review":"damage-confirmed"}</textarea></label>
        <button class="secondary" onclick="adminConfirmDamage()">Admin confirm damage</button>
      </div>
      <div class="card">
        <h3>9. Tat toan hop dong cu</h3>
        <label>Hop dong ID <input id="hopDongIdSettle" placeholder="copy contract id"></label>
        <label>Tong tien thanh toan <input id="tongTienThanhToan" value="1500000"></label>
        <label>Tong tien hoan lai <input id="tongTienHoanLai" value="500000"></label>
        <button onclick="settleContract()">Tat toan va mine block</button>
      </div>
      <div class="card">
        <h3>10. Tai lai du lieu</h3>
        <button class="secondary" onclick="refreshData()">Refresh overview</button>
      </div>
    </div>
    <div class="section card">
      <h3>Ket qua</h3>
      <pre id="result">Chua co du lieu</pre>
    </div>
    <div class="section card">
      <h3>Overview</h3>
      <pre id="overview">Dang tai...</pre>
    </div>
  </div>
<script>
async function api(url, method='GET', body=null) {
  const res = await fetch(url, { method, headers: {'Content-Type':'application/json'}, body: body ? JSON.stringify(body) : null });
  const data = await res.json();
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data, null, 2);
    throw new Error(detail);
  }
  return data;
}
function showResult(data) {
  document.getElementById('result').textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
}
function parseJsonField(id, fallback) {
  const raw = document.getElementById(id).value.trim();
  if (!raw) return fallback;
  return JSON.parse(raw);
}
function syncContractId(id) {
  if (!id) return;
  document.getElementById('hopDongIdLock').value = id;
  document.getElementById('hopDongIdReturn').value = id;
  document.getElementById('hopDongIdDamageClaim').value = id;
  document.getElementById('hopDongIdSettle').value = id;
}
async function refreshData() {
  try {
    const data = await api('/api/overview');
    document.getElementById('overview').textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    document.getElementById('overview').textContent = e.message;
  }
}
async function addVehicle() {
  try {
    const data = await api('/api/vehicles', 'POST', { ownerEmail: ownerEmail.value, bienSo: bienSo.value, hangXe: hangXe.value, dongXe: dongXe.value, loaiXe: loaiXe.value, giaTheoNgay: Number(giaTheoNgay.value), giaTheoGio: Number(giaTheoGio.value) });
    showResult(data); await refreshData();
  } catch (e) { showResult({error:e.message}); }
}
async function createBooking() {
  try {
    const data = await api('/api/bookings', 'POST', { renterEmail: renterEmail.value, bienSo: bookingBienSo.value, soNgayThue: Number(soNgayThue.value), diaDiemNhan: diaDiemNhan.value, tongTienThue: Number(tongTienThue.value) });
    showResult(data); if (data.id) dangKyId.value = data.id; await refreshData();
  } catch (e) { showResult({error:e.message}); }
}
async function createContract() {
  try {
    const data = await api('/api/contracts/from-booking', 'POST', { dangKyId: dangKyId.value, tongTienCoc: Number(tongTienCoc.value) });
    showResult(data);
    if (data.hopDongThue && data.hopDongThue.id) {
      syncContractId(data.hopDongThue.id);
      nguoiTraId.value = data.hopDongThue.nguoithueid || '';
      damageOwnerId.value = data.hopDongThue.chuxeid || '';
    }
    await refreshData();
  } catch (e) { showResult({error:e.message}); }
}
async function lockDeposit() {
  try { const data = await api(`/api/contracts/${hopDongIdLock.value}/lock-deposit`, 'POST'); showResult(data); await refreshData(); }
  catch (e) { showResult({error:e.message}); }
}
async function returnVehicle() {
  try {
    const data = await api(`/api/contracts/${hopDongIdReturn.value}/return-vehicle`, 'POST', { nguoiTraId: nguoiTraId.value, ghiChu: returnGhiChu.value, evidenceUrls: parseJsonField('returnEvidenceUrls', []), evidenceMeta: parseJsonField('returnEvidenceMeta', {}) });
    showResult(data); await refreshData();
  } catch (e) { showResult({error:e.message}); }
}
async function createDamageClaim() {
  try {
    const data = await api(`/api/contracts/${hopDongIdDamageClaim.value}/damage-claim`, 'POST', { ownerId: damageOwnerId.value, lyDo: damageLyDo.value, estimatedCost: Number(damageEstimatedCost.value), ghiChu: damageGhiChu.value, evidenceUrls: parseJsonField('damageEvidenceUrls', []), evidenceMeta: parseJsonField('damageEvidenceMeta', {}) });
    showResult(data); if (data.dispute && data.dispute.id) { disputeIdNoDamage.value = data.dispute.id; disputeIdDamage.value = data.dispute.id; } await refreshData();
  } catch (e) { showResult({error:e.message}); }
}
async function adminConfirmNoDamage() {
  try {
    const data = await api(`/api/disputes/${disputeIdNoDamage.value}/admin-confirm-no-damage`, 'POST', { adminId: adminIdNoDamage.value, decisionNote: decisionNoteNoDamage.value, evidenceMeta: parseJsonField('decisionMetaNoDamage', {}) });
    showResult(data); await refreshData();
  } catch (e) { showResult({error:e.message}); }
}
async function adminConfirmDamage() {
  try {
    const data = await api(`/api/disputes/${disputeIdDamage.value}/admin-confirm-damage`, 'POST', { adminId: adminIdDamage.value, approvedCost: Number(approvedCost.value), decisionNote: decisionNoteDamage.value, evidenceMeta: parseJsonField('decisionMetaDamage', {}) });
    showResult(data); await refreshData();
  } catch (e) { showResult({error:e.message}); }
}
async function settleContract() {
  try {
    const data = await api(`/api/contracts/${hopDongIdSettle.value}/settle`, 'POST', { tongTienThanhToan: Number(tongTienThanhToan.value), tongTienHoanLai: Number(tongTienHoanLai.value) });
    showResult(data); await refreshData();
  } catch (e) { showResult({error:e.message}); }
}
refreshData();
</script>
</body>
</html>
"""

