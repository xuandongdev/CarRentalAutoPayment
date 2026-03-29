document.addEventListener('DOMContentLoaded', () => {
  setDefaultApiBase();

  document.getElementById('addVehicle').addEventListener('click', async () => {
    try {
      const body = {
        ownerEmail: requireValue(document.getElementById('ownerEmail').value, 'Can nhap owner email'),
        bienSo: requireValue(document.getElementById('bienSo').value, 'Can nhap bien so'),
        hangXe: requireValue(document.getElementById('hangXe').value, 'Can nhap hang xe'),
        dongXe: requireValue(document.getElementById('dongXe').value, 'Can nhap dong xe'),
        loaiXe: requireValue(document.getElementById('loaiXe').value, 'Can nhap loai xe'),
        giaTheoNgay: parseNonNegativeNumber(document.getElementById('giaTheoNgay').value, 'giaTheoNgay phai >= 0'),
        moTa: document.getElementById('moTa').value.trim(),
      };
      const data = await requestJson('POST', `${getApiBase()}/api/vehicles`, body);
      renderJson('result', data);
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });

  document.getElementById('claimDamage').addEventListener('click', async () => {
    try {
      const contractId = requireValue(document.getElementById('contractId').value, 'Can nhap contractId');
      const body = {
        ownerId: requireValue(document.getElementById('ownerId').value, 'Can nhap ownerId'),
        lyDo: requireValue(document.getElementById('lyDo').value, 'Can nhap ly do'),
        estimatedCost: parseNonNegativeNumber(document.getElementById('estimatedCost').value, 'estimatedCost phai >= 0'),
        evidenceUrls: parseTextareaUrls(document.getElementById('evidenceUrls').value),
        evidenceMeta: {},
        ghiChu: document.getElementById('ghiChu').value.trim(),
      };
      const data = await requestJson('POST', `${getApiBase()}/api/contracts/${contractId}/damage-claim`, body);
      renderJson('result', data);
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });

  document.getElementById('loadOverview').addEventListener('click', async () => {
    try {
      const data = await requestJson('GET', `${getApiBase()}/api/overview`);
      renderJson('result', data);
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });
});
