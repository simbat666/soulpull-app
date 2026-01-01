(() => {
  const API_BASE = window.location.origin + '/api/v1';
  const TOKEN_KEY = 'soulpull_token';
  const INVITER_KEY = 'soulpull_pending_inviter';

  const el = (id) => document.getElementById(id);
  const statusEl = el('status');
  const addrEl = el('wallet-address');
  const toastEl = el('toast');

  const tgWarningEl = el('tg-warning');

  const screenConnect = el('screen-connect');
  const screenOnboarding = el('screen-onboarding');
  const screenCabinet = el('screen-cabinet');

  const telegramInfoEl = el('telegram-info');
  const inviterInfoEl = el('inviter-info');
  const authorCodeInfoEl = el('author-code-info');

  const cabWalletEl = el('cab-wallet');
  const cabTelegramEl = el('cab-telegram');
  const cabInviterEl = el('cab-inviter');
  const cabAuthorCodeEl = el('cab-author-code');
  const cabStatusEl = el('cab-status');
  const cabStatsEl = el('cab-stats');

  const btnTelegramVerify = el('btn-telegram-verify');
  const inviterInput = el('inviter-input');
  const btnInviterApply = el('btn-inviter-apply');
  const authorCodeInput = el('author-code-input');
  const btnAuthorCodeApply = el('btn-author-code-apply');

  const btnPayCreate = el('btn-pay-create');
  const btnPaySend = el('btn-pay-send');
  const paymentInfo = el('payment-info');
  const txHashInput = el('tx-hash-input');
  const btnPayConfirm = el('btn-pay-confirm');
  const btnPayCreateOld = btnPayCreate;

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
    if (toastEl) toastEl.textContent = text;
  }

  function setAddress(text) {
    if (addrEl) addrEl.textContent = text || '';
  }

  function show(elm) {
    if (!elm) return;
    elm.classList.remove('hidden');
  }

  function hide(elm) {
    if (!elm) return;
    elm.classList.add('hidden');
  }

  function showScreen(which) {
    // which: 'connect' | 'onboarding' | 'cabinet'
    try {
      document.body.dataset.screen = which;
    } catch (_) {
      // ignore
    }
    if (which === 'connect') {
      show(screenConnect);
      hide(screenOnboarding);
      hide(screenCabinet);
      return;
    }
    if (which === 'onboarding') {
      hide(screenConnect);
      show(screenOnboarding);
      hide(screenCabinet);
      return;
    }
    hide(screenConnect);
    hide(screenOnboarding);
    show(screenCabinet);
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

  async function postWithBearer(path, token, body) {
    const res = await fetch(API_BASE + path, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.error || `${path} failed: ${res.status}`);
    return data;
  }

  async function getWithBearer(path, token) {
    const res = await fetch(API_BASE + path, {
      method: 'GET',
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.error || `${path} failed: ${res.status}`);
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

    // Telegram gate (SSOT): if not opened in Telegram WebApp, show only notice and stop.
    const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
    if (!tg || !tg.initData) {
      show(tgWarningEl);
      if (btnTelegramVerify) btnTelegramVerify.disabled = true;
      // Hard gate: don't allow actions outside Telegram
      showScreen('connect');
      setStatus('Откройте через Telegram WebApp');
      return;
    } else {
      hide(tgWarningEl);
      if (btnTelegramVerify) btnTelegramVerify.disabled = false;
    }

    // capture ?ref=... once
    try {
      const params = new URLSearchParams(window.location.search || '');
      const ref = (params.get('ref') || '').trim();
      if (ref) localStorage.setItem(INVITER_KEY, ref);
    } catch (_) {
      // ignore
    }

    setStatus('init');
    setAddress('');
    showScreen('connect');

    const tonConnectUI = new TonConnectUI({
      manifestUrl: window.location.origin + '/tonconnect-manifest.json',
      buttonRootId: 'tonconnect',
    });

    let isLoggedIn = false;
    let currentToken = null;
    let currentProfile = null;
    let lastPaymentIntent = null;

    async function refreshMeFromToken() {
      const savedToken = localStorage.getItem(TOKEN_KEY);
      if (!savedToken) return;
      try {
        const u = await me(savedToken);
        currentToken = savedToken;
        currentProfile = u;
        renderProfile(u);
        isLoggedIn = true;
      } catch (_) {
        localStorage.removeItem(TOKEN_KEY);
        currentToken = null;
        currentProfile = null;
        isLoggedIn = false;
      }
    }

    function renderProfile(u) {
      if (!u) return;
      const wa = u.wallet_address || '';
      setAddress(wa);
      if (telegramInfoEl) {
        telegramInfoEl.textContent = u.telegram?.username
          ? `@${u.telegram.username} (${u.telegram.id})`
          : u.telegram?.id
          ? String(u.telegram.id)
          : '—';
      }
      if (inviterInfoEl) {
        inviterInfoEl.textContent = u.inviter?.wallet_address || (u.inviter?.telegram_id ? String(u.inviter.telegram_id) : '—');
      }
      if (authorCodeInfoEl) authorCodeInfoEl.textContent = u.author_code || '—';

      const status = u.participation_status || 'NEW';

      if (cabWalletEl) cabWalletEl.textContent = wa || '—';
      if (cabTelegramEl) cabTelegramEl.textContent = telegramInfoEl ? telegramInfoEl.textContent : '—';
      if (cabInviterEl) cabInviterEl.textContent = inviterInfoEl ? inviterInfoEl.textContent : '—';
      if (cabAuthorCodeEl) cabAuthorCodeEl.textContent = u.author_code || '—';
      if (cabStatusEl) cabStatusEl.textContent = status;
      if (cabStatsEl) {
        const s = u.stats || {};
        cabStatsEl.textContent = `invited=${s.invited_count || 0}, paid=${s.paid_count || 0}, payouts=${s.payouts_count || 0}, points=${s.points || 0}`;
      }

      if (status === 'ACTIVE') {
        showScreen('cabinet');
        setStatus('logged in');
      } else {
        showScreen('onboarding');
        setStatus('logged in');
      }

      // SSOT: inviter is mandatory before participation/payment.
      const inviterOk = !!u.inviter?.set_at;
      if (btnPayCreate) btnPayCreate.disabled = !inviterOk;
      if (!inviterOk) setStatus('Нужно указать inviter (обязательно)');
    }

    async function applyPendingInviterIfAny() {
      if (!currentToken || !currentProfile) return;
      if (currentProfile.inviter?.set_at) return;
      const pending = localStorage.getItem(INVITER_KEY);
      if (!pending) return;
      try {
        await postWithBearer('/inviter/apply', currentToken, { inviter: pending });
        const u = await me(currentToken);
        currentProfile = u;
        renderProfile(u);
      } catch (_) {
        // ignore
      }
    }

    async function prepareTonProof() {
      setStatus('loading tonproof payload');
      tonConnectUI.setConnectRequestParameters({ state: 'loading' });
      try {
        const payload = await fetchTonproofPayload();
        tonConnectUI.setConnectRequestParameters({
          state: 'ready',
          value: { tonProof: payload },
        });
        if (!isLoggedIn) setStatus('ready');
      } catch (e) {
        tonConnectUI.setConnectRequestParameters(null);
        setStatus(`Ошибка: ${e instanceof Error ? e.message : 'tonproof payload error'}`);
      }
    }

    // 1) If we already have a token — we are logged in even if wallet restore doesn't include tonProof.
    refreshMeFromToken().finally(() => {
      // 2) Always prepare tonProof for the next connect attempt (fresh payload, 5m TTL).
      prepareTonProof();
      applyPendingInviterIfAny();
    });

    tonConnectUI.onStatusChange(async (wallet) => {
      try {
        const address = wallet?.account?.address;
        if (!address) {
          setAddress('');
          setStatus('wallet disconnected');
          showScreen('connect');
          return;
        }

        setAddress(address);
        setStatus('wallet connected');
        showScreen('onboarding');

        // Register wallet (legacy behavior, still required)
        try {
          await registerWallet(address);
        } catch (_) {
          // ignore registration errors for login flow; will be visible in logs if needed
        }

        const publicKey = wallet?.account?.publicKey;
        const proof = wallet?.connectItems?.tonProof?.proof;
        if (!publicKey || !proof) {
          // This happens on restore: wallet is connected but tonProof is not re-sent.
          // If we already have a valid token, that's OK (remain logged in).
          if (isLoggedIn) {
            setStatus('logged in');
            return;
          }
          // Otherwise, force a fresh connect flow with tonProof.
          setStatus('Ошибка: tonProof отсутствует. Переподключите кошелёк.');
          await prepareTonProof();
          try {
            await tonConnectUI.disconnect();
          } catch (_) {
            // ignore
          }
          return;
        }

        setStatus('verifying tonProof');
        const token = await verifyTonproof({
          walletAddress: address,
          publicKey,
          proof,
        });
        localStorage.setItem(TOKEN_KEY, token);
        currentToken = token;

        const u = await me(token);
        currentProfile = u;
        renderProfile(u);
        isLoggedIn = true;
      } catch (e) {
        setStatus(`Ошибка: ${e instanceof Error ? e.message : 'unknown error'}`);
      }
    });

    // UI actions
    if (btnTelegramVerify) {
      btnTelegramVerify.addEventListener('click', async () => {
        if (!currentToken) return setStatus('Ошибка: нет токена');
        const tg2 = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
        if (!tg2 || !tg2.initData) return setStatus('Ошибка: откройте через Telegram');
        setStatus('telegram verify…');
        try {
          await postWithBearer('/telegram/verify', currentToken, { initData: tg2.initData });
          const u = await me(currentToken);
          currentProfile = u;
          renderProfile(u);
          setStatus('telegram linked');
        } catch (e) {
          setStatus(`Ошибка: ${e instanceof Error ? e.message : 'telegram verify error'}`);
        }
      });
    }

    if (btnInviterApply) {
      btnInviterApply.addEventListener('click', async () => {
        if (!currentToken) return setStatus('Ошибка: нет токена');
        const v = (inviterInput?.value || '').trim();
        if (!v) return setStatus('Ошибка: inviter пустой');
        setStatus('saving inviter…');
        try {
          await postWithBearer('/inviter/apply', currentToken, { inviter: v });
          localStorage.removeItem(INVITER_KEY);
          const u = await me(currentToken);
          currentProfile = u;
          renderProfile(u);
          setStatus('inviter saved');
        } catch (e) {
          setStatus(`Ошибка: ${e instanceof Error ? e.message : 'inviter error'}`);
        }
      });
    }

    if (btnAuthorCodeApply) {
      btnAuthorCodeApply.addEventListener('click', async () => {
        if (!currentToken) return setStatus('Ошибка: нет токена');
        const v = (authorCodeInput?.value || '').trim();
        if (!v) return setStatus('Ошибка: code пустой');
        setStatus('applying author code…');
        try {
          await postWithBearer('/author-code/apply', currentToken, { code: v });
          const u = await me(currentToken);
          currentProfile = u;
          renderProfile(u);
          setStatus('author code applied');
        } catch (e) {
          setStatus(`Ошибка: ${e instanceof Error ? e.message : 'author code error'}`);
        }
      });
    }

    if (btnPayCreate) {
      btnPayCreate.addEventListener('click', async () => {
        if (!currentToken) return setStatus('Ошибка: нет токена');
        if (!currentProfile?.inviter?.set_at) return setStatus('Ошибка: inviter обязателен');
        setStatus('creating payment…');
        try {
          // SSOT: create Participation(PENDING) + payment intent in one step
          lastPaymentIntent = await postWithBearer('/participation/create', currentToken, {});
          if (paymentInfo) {
            const ton = Number(lastPaymentIntent.amount || '0') / 1e9;
            paymentInfo.textContent = `receiver: ${lastPaymentIntent.receiver}, amount: ${ton} TON, valid_until: ${lastPaymentIntent.valid_until}, comment: ${lastPaymentIntent.comment}`;
          }
          if (btnPaySend) show(btnPaySend);
          setStatus('payment created');
        } catch (e) {
          setStatus(`Ошибка: ${e instanceof Error ? e.message : 'payment create error'}`);
        }
      });
    }

    if (btnPaySend) {
      btnPaySend.addEventListener('click', async () => {
        if (!lastPaymentIntent) return setStatus('Ошибка: сначала создайте платёж');
        try {
          setStatus('opening wallet…');
          await tonConnectUI.sendTransaction({
            validUntil: lastPaymentIntent.valid_until,
            messages: [{ address: lastPaymentIntent.receiver, amount: String(lastPaymentIntent.amount) }],
          });
          setStatus('tx sent. paste tx hash below');
        } catch (e) {
          setStatus(`Ошибка: ${e instanceof Error ? e.message : 'send tx error'}`);
        }
      });
    }

    if (btnPayConfirm) {
      btnPayConfirm.addEventListener('click', async () => {
        if (!currentToken) return setStatus('Ошибка: нет токена');
        if (!currentProfile?.inviter?.set_at) return setStatus('Ошибка: inviter обязателен');
        const tx = (txHashInput?.value || '').trim();
        if (!tx) return setStatus('Ошибка: tx_hash пустой');
        setStatus('confirming payment…');
        try {
          await postWithBearer('/payments/confirm', currentToken, { tx_hash: tx });
          const u = await me(currentToken);
          currentProfile = u;
          renderProfile(u);
          setStatus('payment pending review');
        } catch (e) {
          setStatus(`Ошибка: ${e instanceof Error ? e.message : 'payment confirm error'}`);
        }
      });
    }
  }

  window.addEventListener('DOMContentLoaded', init);
})();


