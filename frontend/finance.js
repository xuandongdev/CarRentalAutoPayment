document.addEventListener('DOMContentLoaded', () => {
  setDefaultApiBase();
  bindUtilityButtons('result');
  loadReferenceData('referenceData').catch((error) => {
    renderJson('referenceData', { error: error.message });
    notifyError('load_reference_data', error);
  });

  document.getElementById('loadWalletsOverviewBtn').addEventListener('click', async () => {
    try {
      const data = await requestJson('GET', `${getApiBase()}/api/wallets/overview`);
      renderJson('result', data);
      notifySuccess('wallets_overview', `count=${data?.wallets?.length || 0}`);
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('wallets_overview', error);
    }
  });

  document.getElementById('loadFinanceSummaryBtn').addEventListener('click', async () => {
    try {
      const data = await requestJson('GET', `${getApiBase()}/api/finance/summary`);
      renderJson('result', data);
      notifySuccess('finance_summary', `fees=${data?.totalPlatformFeesCollected || 0}`);
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('finance_summary', error);
    }
  });

  document.getElementById('loadFinanceTransactionsBtn').addEventListener('click', async () => {
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

  document.getElementById('loadMoneyFlowBtn').addEventListener('click', async () => {
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
});
