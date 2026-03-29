document.addEventListener('DOMContentLoaded', () => {
  setDefaultApiBase();
  bindUtilityButtons('result');
  loadReferenceData('referenceData').catch((error) => {
    renderJson('referenceData', { error: error.message });
    notifyError('load_reference_data', error);
  });

  const refreshReference = async () => loadReferenceData('referenceData');

  document.getElementById('createBooking').addEventListener('click', async () => {
    try {
      const start = requireValue(document.getElementById('ngayBatDau').value, 'Can nhap ngayBatDau');
      const end = requireValue(document.getElementById('ngayKetThuc').value, 'Can nhap ngayKetThuc');
      const data = await requestJson('POST', `${getApiBase()}/api/bookings`, {
        renterEmail: requireValue(document.getElementById('renterEmail').value, 'Can nhap renterEmail'),
        bienSo: requireValue(document.getElementById('bookingBienSo').value, 'Can nhap bienSo'),
        soNgayThue: diffDays(start, end),
        diaDiemNhan: requireValue(document.getElementById('diaDiemNhan').value, 'Can nhap dia diem nhan'),
        tongTienThue: parseNonNegativeNumber(document.getElementById('tongTienDuKien').value, 'tongTienDuKien phai >= 0'),
        ghiChu: `Bat dau ${start}, ket thuc ${end}`,
      });
      renderJson('result', data);
      if (data.id) document.getElementById('bookingId').value = data.id;
      await refreshReference();
      notifySuccess('create_booking', data?.id || 'ok');
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('create_booking', error);
    }
  });

  document.getElementById('createContract').addEventListener('click', async () => {
    try {
      const data = await requestJson('POST', `${getApiBase()}/api/contracts/create`, {
        dangKyId: requireValue(document.getElementById('bookingId').value, 'Can nhap bookingId'),
        tongTienCoc: parseNonNegativeNumber(document.getElementById('tongTienCoc').value, 'tongTienCoc phai >= 0'),
      });
      renderJson('result', data);
      const contractId = data?.hopDongThue?.id;
      if (contractId) {
        document.getElementById('lockContractId').value = contractId;
        document.getElementById('returnContractId').value = contractId;
        document.getElementById('settleContractId').value = contractId;
      }
      if (data?.hopDongThue?.nguoithueid) document.getElementById('nguoiTraId').value = data.hopDongThue.nguoithueid;
      await refreshReference();
      notifySuccess('create_contract', contractId || 'ok');
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('create_contract', error);
    }
  });

  document.getElementById('lockDeposit').addEventListener('click', async () => {
    try {
      const contractId = requireValue(document.getElementById('lockContractId').value, 'Can nhap contractId');
      const data = await requestJson('POST', `${getApiBase()}/api/contracts/${contractId}/lock-deposit`);
      renderJson('result', data);
      await refreshReference();
      notifySuccess('lock_deposit', data?.transaction?.txHash || contractId);
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('lock_deposit', error);
    }
  });

  document.getElementById('returnVehicle').addEventListener('click', async () => {
    try {
      const contractId = requireValue(document.getElementById('returnContractId').value, 'Can nhap contractId');
      const data = await requestJson('POST', `${getApiBase()}/api/contracts/${contractId}/return-vehicle`, {
        nguoiTraId: requireValue(document.getElementById('nguoiTraId').value, 'Can nhap nguoiTraId'),
        ghiChu: requireValue(document.getElementById('returnNote').value, 'Can nhap ghiChu'),
        evidenceUrls: parseTextareaUrls(document.getElementById('returnEvidenceUrls').value),
        evidenceMeta: {},
      });
      renderJson('result', data);
      await refreshReference();
      notifySuccess('return_vehicle', data?.transaction?.txHash || contractId);
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('return_vehicle', error);
    }
  });

  document.getElementById('settleContract').addEventListener('click', async () => {
    try {
      const contractId = requireValue(document.getElementById('settleContractId').value, 'Can nhap contractId');
      const data = await requestJson('POST', `${getApiBase()}/api/contracts/${contractId}/settle`, {
        tongTienThanhToan: parseNonNegativeNumber(document.getElementById('tongTienThanhToan').value, 'tongTienThanhToan phai >= 0'),
        tongTienHoanLai: parseNonNegativeNumber(document.getElementById('tongTienHoanLai').value, 'tongTienHoanLai phai >= 0'),
      });
      renderJson('result', data);
      await refreshReference();
      notifySuccess('settle_contract', data?.transactions?.[0]?.txHash || contractId);
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('settle_contract', error);
    }
  });
});
