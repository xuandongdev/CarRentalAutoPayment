document.addEventListener('DOMContentLoaded', () => {
  setDefaultApiBase();
  bindUtilityButtons('result');
  loadReferenceData('referenceData').catch((error) => {
    renderJson('referenceData', { error: error.message });
    notifyError('load_reference_data', error);
  });

  const refreshReference = async () => loadReferenceData('referenceData');

  const bindMirrorButton = (buttonId, action) => {
    const button = document.getElementById(buttonId);
    if (!button) return;
    button.addEventListener('click', action);
  };

  bindMirrorButton('loadOverviewBtn2', async () => {
    try {
      const data = await requestJson('GET', `${getApiBase()}/api/overview`);
      renderJson('result', data);
      renderReferenceData('referenceData', data);
      notifySuccess('admin_refresh_overview', `syncStatus=${data.syncStatus}`);
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('admin_refresh_overview', error);
    }
  });

  bindMirrorButton('loadChainBtn2', async () => {
    try {
      const data = await requestJson('GET', `${getApiBase()}/api/node/chain`);
      renderJson('result', data);
      notifySuccess('admin_refresh_chain', `latestBlockHeight=${data?.meta?.latestBlockHeight ?? 'n/a'}`);
    } catch (error) {
      renderJson('result', { error: error.message });
      notifyError('admin_refresh_chain', error);
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
});
