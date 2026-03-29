document.addEventListener('DOMContentLoaded', () => {
  setDefaultApiBase();
  bindUtilityButtons('result');
  loadReferenceData('referenceData').catch((error) => renderJson('referenceData', { error: error.message }));

  const refreshReference = async () => {
    await loadReferenceData('referenceData');
  };

  document.getElementById('registerBtn').addEventListener('click', async () => {
    try {
      const body = {
        hoTen: requireValue(document.getElementById('registerHoTen').value, 'Can nhap hoTen'),
        email: document.getElementById('registerEmail').value.trim(),
        soDienThoai: document.getElementById('registerSoDienThoai').value.trim(),
        password: requireValue(document.getElementById('registerPassword').value, 'Can nhap password'),
      };
      const data = await requestJson('POST', `${getApiBase()}/auth/register`, body, '');
      renderJson('result', data);
      await refreshReference();
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });

  document.getElementById('loginBtn').addEventListener('click', async () => {
    try {
      const body = {
        identifier: requireValue(document.getElementById('identifier').value, 'Can nhap email hoac so dien thoai'),
        password: requireValue(document.getElementById('password').value, 'Can nhap password'),
      };
      const data = await requestJson('POST', `${getApiBase()}/auth/login`, body, '');
      setToken(data.accessToken);
      renderJson('result', data);
      await refreshReference();
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });

  document.getElementById('meBtn').addEventListener('click', async () => {
    try {
      const data = await requestJson('GET', `${getApiBase()}/auth/me`);
      renderJson('result', data);
      await refreshReference();
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });

  document.getElementById('logoutBtn').addEventListener('click', async () => {
    try {
      const data = await requestJson('POST', `${getApiBase()}/auth/logout`, {});
      clearToken();
      renderJson('result', data);
    } catch (error) {
      renderJson('result', { error: error.message });
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
      const nonceData = await requestJson('POST', `${getApiBase()}/auth/wallet/nonce`, {
        walletAddress,
        chainId,
        purpose: 'link_wallet',
      });
      const signature = await window.ethereum.request({
        method: 'personal_sign',
        params: [nonceData.message, walletAddress],
      });
      const verifyData = await requestJson('POST', `${getApiBase()}/auth/wallet/verify`, {
        walletAddress,
        message: nonceData.message,
        signature,
        purpose: 'link_wallet',
      });
      renderJson('result', { nonce: nonceData, verify: verifyData });
      await refreshReference();
    } catch (error) {
      renderJson('result', { error: error.message });
    }
  });
});
