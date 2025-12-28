(function () {
  const statusEl = document.getElementById('status');
  const walletEl = document.getElementById('wallet');
  const pubkeyEl = document.getElementById('pubkey');
  const hintEl = document.getElementById('hint');
  const errorEl = document.getElementById('error');

  function setStatus(text) {
    statusEl.textContent = text;
  }

  function showError(text) {
    errorEl.style.display = 'block';
    errorEl.textContent = text;
  }

  function clearError() {
    errorEl.style.display = 'none';
    errorEl.textContent = '';
  }

  async function fetchTonProofPayload() {
    const res = await fetch('/api/v1/ton-proof/payload', {
      method: 'GET',
      credentials: 'include',
    });
    if (!res.ok) {
      throw new Error(`payload request failed: ${res.status}`);
    }
    const data = await res.json();
    return data.payload;
  }

  async function verifyTonProof(wallet) {
    const proofItem = wallet?.connectItems?.tonProof;
    if (!proofItem || !('proof' in proofItem)) {
      throw new Error('ton_proof отсутствует (кошелёк не прислал proof)');
    }

    const req = {
      address: wallet.account.address,
      publicKey: wallet.account.publicKey,
      walletStateInit: wallet.account.walletStateInit,
      proof: proofItem.proof,
    };

    const res = await fetch('/api/v1/ton-proof/verify', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      throw new Error(data?.error || `verify failed: ${res.status}`);
    }
    return data;
  }

  async function main() {
    clearError();
    setStatus('init');

    if (!window.TON_CONNECT_UI || !window.TON_CONNECT_UI.TonConnectUI) {
      showError('TonConnect UI не загрузился. Проверь доступ к CDN.');
      return;
    }

    const tc = new window.TON_CONNECT_UI.TonConnectUI({
      manifestUrl: '/tonconnect-manifest.json',
      widgetRootId: 'tc-widget-root',
    });

    setStatus('loading payload');
    tc.setConnectRequestParameters({ state: 'loading' });

    try {
      const payload = await fetchTonProofPayload();
      tc.setConnectRequestParameters({
        state: 'ready',
        value: { tonProof: payload },
      });
      setStatus('ready');
    } catch (e) {
      tc.setConnectRequestParameters(null);
      setStatus('error');
      showError(e instanceof Error ? e.message : 'payload error');
    }

    tc.onStatusChange(async (wallet) => {
      clearError();

      if (!wallet) {
        setStatus('disconnected');
        walletEl.textContent = '—';
        pubkeyEl.textContent = '—';
        return;
      }

      walletEl.textContent = wallet?.account?.address || '—';
      pubkeyEl.textContent = wallet?.account?.publicKey || '—';

      try {
        setStatus('verifying');
        hintEl.innerHTML = 'Проверяем <code>ton_proof</code> на бэкенде…';
        await verifyTonProof(wallet);
        setStatus('ok');
        hintEl.textContent = 'OK: ton_proof валиден, сессия создана на сервере.';
      } catch (e) {
        setStatus('error');
        showError(e instanceof Error ? e.message : 'verify error');
      }
    });
  }

  window.addEventListener('load', () => {
    main().catch((e) => {
      setStatus('error');
      showError(e instanceof Error ? e.message : 'init error');
    });
  });
})();


