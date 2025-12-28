(() => {
  const API_BASE = window.location.origin + '/api/v1';

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

    setStatus('Готово. Подключите кошелёк.');
    setAddress('');

    const tonConnectUI = new TonConnectUI({
      manifestUrl: window.location.origin + '/tonconnect-manifest.json',
      buttonRootId: 'tonconnect',
    });

    tonConnectUI.onStatusChange(async (wallet) => {
      try {
        const address = wallet?.account?.address;
        if (!address) {
          setAddress('');
          setStatus('Кошелёк отключен');
          return;
        }

        setAddress(address);
        setStatus('Подключен. Регистрируем…');

        const result = await registerWallet(address);
        setStatus(result?.created ? 'Зарегистрирован' : 'Уже зарегистрирован');
      } catch (e) {
        setStatus(`Ошибка: ${e instanceof Error ? e.message : 'unknown error'}`);
      }
    });
  }

  window.addEventListener('DOMContentLoaded', init);
})();

(() => {
  const API_BASE = window.location.origin + '/api/v1';

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

  function getTonConnectCtor() {
    // UMD bundle exposes global "TON_CONNECT_UI".
    // Depending on version, constructor can be TonConnectUI or TONConnectUI.
    const ns = window.TON_CONNECT_UI;
    return ns?.TonConnectUI || ns?.TONConnectUI || ns?.TONConnectUI;
  }

  function init() {
    const TonConnectUI = getTonConnectCtor();
    if (!TonConnectUI) {
      setStatus('Ошибка: TonConnect UI не загрузился');
      return;
    }

    setStatus('Готово. Подключите кошелёк.');
    setAddress('');

    const tonConnectUI = new TonConnectUI({
      manifestUrl: window.location.origin + '/tonconnect-manifest.json',
      buttonRootId: 'tonconnect',
    });

    tonConnectUI.onStatusChange(async (wallet) => {
      try {
        const address = wallet?.account?.address;
        if (!address) {
          setAddress('');
          setStatus('Кошелёк отключен');
          return;
        }

        setAddress(address);
        setStatus('Подключен. Регистрируем…');

        const result = await registerWallet(address);
        setStatus(result?.created ? 'Зарегистрирован' : 'Уже зарегистрирован');
      } catch (e) {
        setStatus(`Ошибка: ${e instanceof Error ? e.message : 'unknown error'}`);
      }
    });
  }

  window.addEventListener('DOMContentLoaded', init);
})();


