document.addEventListener('DOMContentLoaded', () => {
  setDefaultApiBase();
  bindUtilityButtons('result');
  loadReferenceData('referenceData').catch((error) => {
    renderJson('referenceData', { error: error.message });
    notifyError('load_reference_data', error);
  });

  const refreshReference = async () => loadReferenceData('referenceData');

  const syncContractIds = (contractId) => {
    if (!contractId) return;
    ['lockContractId', 'returnContractId', 'damageContractId', 'settleContractId'].forEach((id) => {
      const input = document.getElementById(id);
      if (input) input.value = contractId;
    });
  };

  document.getElementById('registerBtn').addEventListener('click', async () => {
    try {
      const data = await requestJson('POST', `${getApiBase()}/auth/register`, {
        hoTen: requireValue(document.getElementById('registerHoTen').value, 'Can nhap hoTen'),
        email: document.getElementById('registerEmail').value.trim(),
        soDienThoai: document.getElementById('registerSoDienThoai').value.trim(),
        password: requireValue(document.getElementById('registerPassword').value, 'Can nhap password'),
      }, '');
      renderJson('result', data);
      await refreshReference();
      notifySuccess('register', data?.user?.id || 'ok');
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('register', error);
    }
  });

  document.getElementById('loginBtn').addEventListener('click', async () => {
    try {
      const data = await requestJson('POST', `${getApiBase()}/auth/login`, {
        identifier: requireValue(document.getElementById('identifier').value, 'Can nhap identifier'),
        password: requireValue(document.getElementById('password').value, 'Can nhap password'),
      }, '');
      setToken(data.accessToken);
      renderJson('result', data);
      await refreshReference();
      notifySuccess('login', data?.user?.id || 'ok');
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('login', error);
    }
  });

  document.getElementById('meBtn').addEventListener('click', async () => {
    try {
      const data = await requestJson('GET', `${getApiBase()}/auth/me`);
      renderJson('result', data);
      await refreshReference();
      notifySuccess('get_me', data?.user?.id || 'ok');
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('get_me', error);
    }
  });

  document.getElementById('logoutBtn').addEventListener('click', async () => {
    try {
      const data = await requestJson('POST', `${getApiBase()}/auth/logout`, {});
      clearToken();
      renderJson('result', data);
      notifySuccess('logout', 'session_revoked');
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('logout', error);
    }
  });

  document.getElementById('linkWalletBtn').addEventListener('click', async () => {
    try {
      if (!window.ethereum) throw new Error('MetaMask chua san sang trong trinh duyet nay');
      const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
      const walletAddress = accounts?.[0];
      if (!walletAddress) throw new Error('Khong lay duoc wallet address');
      const chainHex = await window.ethereum.request({ method: 'eth_chainId' });
      const chainId = parseInt(chainHex, 16);
      const nonceData = await requestJson('POST', `${getApiBase()}/auth/wallet/nonce`, { walletAddress, chainId, purpose: 'link_wallet' });
      const signature = await window.ethereum.request({ method: 'personal_sign', params: [nonceData.message, walletAddress] });
      const verifyData = await requestJson('POST', `${getApiBase()}/auth/wallet/verify`, { walletAddress, message: nonceData.message, signature, purpose: 'link_wallet' });
      renderJson('result', { nonce: nonceData, verify: verifyData });
      await refreshReference();
      notifySuccess('link_wallet', verifyData?.wallet?.address || walletAddress);
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('link_wallet', error);
    }
  });

  document.getElementById('addVehicle').addEventListener('click', async () => {
    try {
      const data = await requestJson('POST', `${getApiBase()}/api/vehicles`, {
        ownerEmail: requireValue(document.getElementById('ownerEmail').value, 'Can nhap ownerEmail'),
        bienSo: requireValue(document.getElementById('bienSo').value, 'Can nhap bienSo'),
        hangXe: requireValue(document.getElementById('hangXe').value, 'Can nhap hangXe'),
        dongXe: requireValue(document.getElementById('dongXe').value, 'Can nhap dongXe'),
        loaiXe: requireValue(document.getElementById('loaiXe').value, 'Can nhap loaiXe'),
        giaTheoNgay: parseNonNegativeNumber(document.getElementById('giaTheoNgay').value, 'giaTheoNgay phai >= 0'),
        giaTheoGio: parseNonNegativeNumber(document.getElementById('giaTheoGio').value, 'giaTheoGio phai >= 0'),
        moTa: document.getElementById('moTa').value.trim(),
      });
      renderJson('result', data);
      await refreshReference();
      notifySuccess('add_vehicle', data?.id || data?.bienso || 'ok');
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('add_vehicle', error);
    }
  });

  document.getElementById('createBooking').addEventListener('click', async () => {
    try {
      const start = requireValue(document.getElementById('ngayBatDau').value, 'Can nhap ngayBatDau');
      const end = requireValue(document.getElementById('ngayKetThuc').value, 'Can nhap ngayKetThuc');
      const data = await requestJson('POST', `${getApiBase()}/api/bookings`, {
        renterEmail: requireValue(document.getElementById('renterEmail').value, 'Can nhap renterEmail'),
        bienSo: requireValue(document.getElementById('bookingBienSo').value, 'Can nhap bienSo'),
        soNgayThue: diffDays(start, end),
        diaDiemNhan: requireValue(document.getElementById('diaDiemNhan').value, 'Can nhap diaDiemNhan'),
        tongTienThue: parseNonNegativeNumber(document.getElementById('tongTienThue').value, 'tongTienThue phai >= 0'),
        ghiChu: `Bat dau ${start}, ket thuc ${end}`,
      });
      if (data.id) document.getElementById('bookingId').value = data.id;
      renderJson('result', data);
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
      const contract = data?.hopDongThue;
      syncContractIds(contract?.id);
      if (contract?.nguoithueid) document.getElementById('nguoiTraId').value = contract.nguoithueid;
      if (contract?.chuxeid) document.getElementById('ownerId').value = contract.chuxeid;
      renderJson('result', data);
      await refreshReference();
      notifySuccess('create_contract', contract?.id || 'ok');
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

  document.getElementById('claimDamage').addEventListener('click', async () => {
    try {
      const contractId = requireValue(document.getElementById('damageContractId').value, 'Can nhap contractId');
      const data = await requestJson('POST', `${getApiBase()}/api/contracts/${contractId}/damage-claim`, {
        ownerId: requireValue(document.getElementById('ownerId').value, 'Can nhap ownerId'),
        lyDo: requireValue(document.getElementById('lyDo').value, 'Can nhap lyDo'),
        estimatedCost: parseNonNegativeNumber(document.getElementById('estimatedCost').value, 'estimatedCost phai >= 0'),
        evidenceUrls: parseTextareaUrls(document.getElementById('damageEvidenceUrls').value),
        evidenceMeta: {},
        ghiChu: document.getElementById('ghiChu').value.trim(),
      });
      if (data?.dispute?.id) {
        document.getElementById('noDamageDisputeId').value = data.dispute.id;
        document.getElementById('damageDisputeId').value = data.dispute.id;
      }
      renderJson('result', data);
      await refreshReference();
      notifySuccess('damage_claim', data?.dispute?.id || 'ok');
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('damage_claim', error);
    }
  });

  document.getElementById('submitNoDamage').addEventListener('click', async () => {
    try {
      const disputeId = requireValue(document.getElementById('noDamageDisputeId').value, 'Can nhap disputeId');
      const data = await requestJson('POST', `${getApiBase()}/api/disputes/${disputeId}/admin-confirm-no-damage`, {
        adminId: requireValue(document.getElementById('noDamageAdminId').value, 'Can nhap adminId'),
        decisionNote: requireValue(document.getElementById('noDamageDecisionNote').value, 'Can nhap decisionNote'),
        evidenceMeta: {},
      });
      renderJson('result', data);
      await refreshReference();
      notifySuccess('admin_confirm_no_damage', disputeId);
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('admin_confirm_no_damage', error);
    }
  });

  document.getElementById('submitDamage').addEventListener('click', async () => {
    try {
      const disputeId = requireValue(document.getElementById('damageDisputeId').value, 'Can nhap disputeId');
      const data = await requestJson('POST', `${getApiBase()}/api/disputes/${disputeId}/admin-confirm-damage`, {
        adminId: requireValue(document.getElementById('damageAdminId').value, 'Can nhap adminId'),
        approvedCost: parseNonNegativeNumber(document.getElementById('approvedCost').value, 'approvedCost phai >= 0'),
        decisionNote: requireValue(document.getElementById('damageDecisionNote').value, 'Can nhap decisionNote'),
        evidenceMeta: {},
      });
      renderJson('result', data);
      await refreshReference();
      notifySuccess('admin_confirm_damage', disputeId);
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('admin_confirm_damage', error);
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

  const walletsBtn = document.getElementById('loadWalletsOverviewBtn');
  if (walletsBtn) {
    walletsBtn.addEventListener('click', async () => {
      try {
        const data = await requestJson('GET', `${getApiBase()}/api/wallets/overview`);
        renderJson('result', data);
        notifySuccess('wallets_overview', `count=${data?.wallets?.length || 0}`);
      } catch (error) {
        renderJson('result', { error: error.message });
        notifyError('wallets_overview', error);
      }
    });
  }

  const financeSummaryBtn = document.getElementById('loadFinanceSummaryBtn');
  if (financeSummaryBtn) {
    financeSummaryBtn.addEventListener('click', async () => {
      try {
        const data = await requestJson('GET', `${getApiBase()}/api/finance/summary`);
        renderJson('result', data);
        notifySuccess('finance_summary', `fees=${data?.totalPlatformFeesCollected || 0}`);
      } catch (error) {
        renderJson('result', { error: error.message });
        notifyError('finance_summary', error);
      }
    });
  }

  const financeTransactionsBtn = document.getElementById('loadFinanceTransactionsBtn');
  if (financeTransactionsBtn) {
    financeTransactionsBtn.addEventListener('click', async () => {
      try {
        const params = new URLSearchParams();
        const walletAddress = document.getElementById('financeWalletAddress').value.trim();
        const txType = document.getElementById('financeTxType').value.trim();
        const contractId = document.getElementById('financeContractId').value.trim();
        const disputeId = document.getElementById('financeDisputeId').value.trim();
        if (walletAddress) params.set('walletAddress', walletAddress);
        if (txType) params.set('txType', txType);
        if (contractId) params.set('contractId', contractId);
        if (disputeId) params.set('disputeId', disputeId);
        const query = params.toString() ? `?${params.toString()}` : '';
        const data = await requestJson('GET', `${getApiBase()}/api/finance/transactions${query}`);
        renderJson('result', data);
        notifySuccess('finance_transactions', `count=${data?.count || 0}`);
      } catch (error) {
        renderJson('result', { error: error.message });
        notifyError('finance_transactions', error);
      }
    });
  }

  const moneyFlowBtn = document.getElementById('loadMoneyFlowBtn');
  if (moneyFlowBtn) {
    moneyFlowBtn.addEventListener('click', async () => {
      try {
        const contractId = requireValue(document.getElementById('moneyFlowContractId').value, 'Can nhap contractId');
        const data = await requestJson('GET', `${getApiBase()}/api/contracts/${contractId}/money-flow`);
        renderJson('result', data);
        notifySuccess('contract_money_flow', contractId);
      } catch (error) {
        renderJson('result', { error: error.message });
        notifyError('contract_money_flow', error);
      }
    });
  }
});
