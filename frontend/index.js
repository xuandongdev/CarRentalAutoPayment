document.addEventListener('DOMContentLoaded', () => {
  setDefaultApiBase();

  document.getElementById('loadOverview').addEventListener('click', async () => {
    try {
      const data = await requestJson('GET', `${getApiBase()}/api/overview`);
      renderJson('result', data);
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });

  document.getElementById('loadChain').addEventListener('click', async () => {
    try {
      const data = await requestJson('GET', `${getApiBase()}/api/node/chain`);
      renderJson('result', data);
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });

  document.getElementById('runReconcile').addEventListener('click', async () => {
    try {
      const data = await requestJson('POST', `${getApiBase()}/api/node/reconcile`);
      renderJson('result', data);
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });

  document.getElementById('submitNoDamage').addEventListener('click', async () => {
    try {
      const disputeId = requireValue(document.getElementById('noDamageDisputeId').value, 'Can nhap disputeId');
      const body = {
        adminId: requireValue(document.getElementById('noDamageAdminId').value, 'Can nhap adminId'),
        decisionNote: requireValue(document.getElementById('noDamageDecisionNote').value, 'Can nhap decisionNote'),
        evidenceMeta: {},
      };
      const data = await requestJson('POST', `${getApiBase()}/api/disputes/${disputeId}/admin-confirm-no-damage`, body);
      renderJson('result', data);
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });

  document.getElementById('submitDamage').addEventListener('click', async () => {
    try {
      const disputeId = requireValue(document.getElementById('damageDisputeId').value, 'Can nhap disputeId');
      const body = {
        adminId: requireValue(document.getElementById('damageAdminId').value, 'Can nhap adminId'),
        approvedCost: parseNonNegativeNumber(document.getElementById('approvedCost').value, 'approvedCost phai >= 0'),
        decisionNote: requireValue(document.getElementById('damageDecisionNote').value, 'Can nhap decisionNote'),
        evidenceMeta: {},
      };
      const data = await requestJson('POST', `${getApiBase()}/api/disputes/${disputeId}/admin-confirm-damage`, body);
      renderJson('result', data);
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });
});
