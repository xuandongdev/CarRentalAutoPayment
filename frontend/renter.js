document.addEventListener('DOMContentLoaded', () => {
  setDefaultApiBase();

  document.getElementById('createBooking').addEventListener('click', async () => {
    try {
      const start = requireValue(document.getElementById('ngayBatDau').value, 'Can nhap ngayBatDau');
      const end = requireValue(document.getElementById('ngayKetThuc').value, 'Can nhap ngayKetThuc');
      const body = {
        renterEmail: requireValue(document.getElementById('renterEmail').value, 'Can nhap renterEmail'),
        bienSo: requireValue(document.getElementById('bookingBienSo').value, 'Can nhap bienSo'),
        soNgayThue: diffDays(start, end),
        diaDiemNhan: requireValue(document.getElementById('diaDiemNhan').value, 'Can nhap dia diem nhan'),
        tongTienThue: parseNonNegativeNumber(document.getElementById('tongTienDuKien').value, 'tongTienDuKien phai >= 0'),
        ghiChu: `Bat dau ${start}, ket thuc ${end}`,
      };
      const data = await requestJson('POST', `${getApiBase()}/api/bookings`, body);
      renderJson('result', data);
      if (data.id) document.getElementById('bookingId').value = data.id;
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });

  document.getElementById('createContract').addEventListener('click', async () => {
    try {
      const body = {
        dangKyId: requireValue(document.getElementById('bookingId').value, 'Can nhap bookingId'),
        tongTienCoc: parseNonNegativeNumber(document.getElementById('tongTienCoc').value, 'tongTienCoc phai >= 0'),
      };
      const data = await requestJson('POST', `${getApiBase()}/api/contracts/create`, body);
      renderJson('result', data);
      const contractId = data?.hopDongThue?.id;
      if (contractId) {
        document.getElementById('lockContractId').value = contractId;
        document.getElementById('returnContractId').value = contractId;
        document.getElementById('settleContractId').value = contractId;
      }
      if (data?.hopDongThue?.nguoithueid) {
        document.getElementById('nguoiTraId').value = data.hopDongThue.nguoithueid;
      }
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });

  document.getElementById('lockDeposit').addEventListener('click', async () => {
    try {
      const contractId = requireValue(document.getElementById('lockContractId').value, 'Can nhap contractId');
      const data = await requestJson('POST', `${getApiBase()}/api/contracts/${contractId}/lock-deposit`);
      renderJson('result', data);
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });

  document.getElementById('returnVehicle').addEventListener('click', async () => {
    try {
      const contractId = requireValue(document.getElementById('returnContractId').value, 'Can nhap contractId');
      const body = {
        nguoiTraId: requireValue(document.getElementById('nguoiTraId').value, 'Can nhap nguoiTraId'),
        ghiChu: requireValue(document.getElementById('returnNote').value, 'Can nhap ghiChu'),
        evidenceUrls: parseTextareaUrls(document.getElementById('returnEvidenceUrls').value),
        evidenceMeta: {},
      };
      const data = await requestJson('POST', `${getApiBase()}/api/contracts/${contractId}/return-vehicle`, body);
      renderJson('result', data);
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });

  document.getElementById('settleContract').addEventListener('click', async () => {
    try {
      const contractId = requireValue(document.getElementById('settleContractId').value, 'Can nhap contractId');
      const body = {
        tongTienThanhToan: parseNonNegativeNumber(document.getElementById('tongTienThanhToan').value, 'tongTienThanhToan phai >= 0'),
        tongTienHoanLai: parseNonNegativeNumber(document.getElementById('tongTienHoanLai').value, 'tongTienHoanLai phai >= 0'),
      };
      const data = await requestJson('POST', `${getApiBase()}/api/contracts/${contractId}/settle`, body);
      renderJson('result', data);
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });
});
