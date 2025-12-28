(() => {
  const API_BASE = window.location.origin + '/api/v1';
  const TOKEN_KEY = 'soulpull_token';

  const statusEl = document.getElementById('status');
  const addrEl = document.getElementById('wallet-address');

  function setStatus(text) {
    statusEl.textContent = text;
  }

  function setAddress(text) {
    addrEl.textContent = text || '';
  }

  async function registerWallet(address) {
    const res = await fetch(API_BASE + '/register-wallet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ wallet_address: address }),
    });

    let data = null;
    try {
      data = await res.json();
    } catch (_) {
      // ignore
    }

    if (!res.ok) {
      const msg = data?.error || `register-wallet failed: ${res.status}`;
      throw new Error(msg);
    }

    return data;
  }

  async function fetchTonproofPayload() {
    const res = await fetch(API_BASE + '/tonproof/payload', { method: 'GET' });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.error || `tonproof/payload failed: ${res.status}`);
    return data.payload;
  }

  async function verifyTonproof({ walletAddress, publicKey, proof }) {
    const res = await fetch(API_BASE + '/tonproof/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        wallet_address: walletAddress,
        public_key: publicKey,
        proof,
      }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.error || `tonproof/verify failed: ${res.status}`);
    if (!data?.token) throw new Error('tonproof/verify: missing token');
    return data.token;
  }

  async function me(token) {
    const res = await fetch(API_BASE + '/me', {
      method: 'GET',
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.error || `me failed: ${res.status}`);
    return data;
  }

  function getTonConnectCtor() {
    const ns = window.TON_CONNECT_UI;
    return ns?.TonConnectUI || ns?.TONConnectUI;
  }

  function init() {
    const TonConnectUI = getTonConnectCtor();
    if (!TonConnectUI) {
      setStatus('Ошибка: TonConnect UI не загрузился');
      return;
    }

    setStatus('init');
    setAddress('');

    const tonConnectUI = new TonConnectUI({
      manifestUrl: window.location.origin + '/tonconnect-manifest.json',
      buttonRootId: 'tonconnect',
    });

    // If we have token (after previous login) — validate it and show "logged in".
    const savedToken = localStorage.getItem(TOKEN_KEY);
    if (savedToken) {
      me(savedToken)
        .then((u) => {
          setAddress(u?.wallet_address || '');
          setStatus('logged in');
        })
        .catch(() => {
          localStorage.removeItem(TOKEN_KEY);
        });
    }

    // Prepare TON Proof request parameters for TonConnect UI
    setStatus('loading tonproof payload');
    tonConnectUI.setConnectRequestParameters({ state: 'loading' });
    fetchTonproofPayload()
      .then((payload) => {
        tonConnectUI.setConnectRequestParameters({
          state: 'ready',
          value: { tonProof: payload },
        });
        setStatus('ready');
      })
      .catch((e) => {
        tonConnectUI.setConnectRequestParameters(null);
        setStatus(`Ошибка: ${e instanceof Error ? e.message : 'tonproof payload error'}`);
      });

    tonConnectUI.onStatusChange(async (wallet) => {
      try {
        const address = wallet?.account?.address;
        if (!address) {
          setAddress('');
          setStatus('wallet disconnected');
          return;
        }

        setAddress(address);
        setStatus('wallet connected');

        // Register wallet (legacy behavior, still required)
        try {
          await registerWallet(address);
        } catch (_) {
          // ignore registration errors for login flow; will be visible in logs if needed
        }

        const publicKey = wallet?.account?.publicKey;
        const proof = wallet?.connectItems?.tonProof?.proof;
        if (!publicKey || !proof) {
          setStatus('Ошибка: tonProof отсутствует. Переподключите кошелёк.');
          return;
        }

        setStatus('verifying tonProof');
        const token = await verifyTonproof({
          walletAddress: address,
          publicKey,
          proof,
        });
        localStorage.setItem(TOKEN_KEY, token);

        const u = await me(token);
        setAddress(u?.wallet_address || address);
        setStatus('logged in');
      } catch (e) {
        setStatus(`Ошибка: ${e instanceof Error ? e.message : 'unknown error'}`);
      }
    });
  }

  window.addEventListener('DOMContentLoaded', init);
})();


