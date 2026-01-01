(() => {
  const API_BASE = window.location.origin + '/api/v1';
  const TOKEN_KEY = 'soulpull_token';
  const UI_BUILD = 'ui-20260101-6';

  const el = (id) => document.getElementById(id);
  const statusEl = el('status');
  const addrEl = el('wallet-address');
  const toastEl = el('toast');

  const tgWarningEl = el('tg-warning');
  const tgUserEl = el('tg-user');
  const tgUserAvatarEl = el('tg-user-avatar');
  const tgUserNameEl = el('tg-user-name');
  const tgUserUsernameEl = el('tg-user-username');
  const buildBadgeEl = el('build-badge');

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

  function getTelegramWebApp() {
    return window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  }

  function getHashParams() {
    try {
      const h = String(window.location.hash || '');
      if (!h || h.length <= 1) return new URLSearchParams('');
      return new URLSearchParams(h.startsWith('#') ? h.slice(1) : h);
    } catch (_) {
      return new URLSearchParams('');
    }
  }

  function getTelegramInitDataFromUrl() {
    // Telegram may pass init data as `tgWebAppData` in query or hash.
    try {
      const sp = new URLSearchParams(window.location.search || '');
      const hp = getHashParams();
      const raw = sp.get('tgWebAppData') || hp.get('tgWebAppData');
      if (!raw) return null;
      return decodeURIComponent(raw);
    } catch (_) {
      return null;
    }
  }

  function isTelegramUserAgent() {
    try {
      return /Telegram/i.test(navigator.userAgent || '');
    } catch (_) {
      return false;
    }
  }

  function parseTelegramUserFromInitData(initData) {
    try {
      const sp = new URLSearchParams(String(initData || ''));
      const raw = sp.get('user');
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_) {
      return null;
    }
  }

  function getTelegramInitData(tg) {
    if (tg && tg.initData) return tg.initData;
    return getTelegramInitDataFromUrl();
  }

  function extractTelegramUser(tg) {
    // tg may be null (Telegram Desktop sometimes doesn't inject WebApp object),
    // but initData can still be present in URL as tgWebAppData.
    const u1 = tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user : null;
    if (u1) return u1;
    const initData = getTelegramInitData(tg);
    if (initData) return parseTelegramUserFromInitData(initData);
    return null;
  }

  function renderTelegramUser(tg) {
    // Render from either WebApp object or tgWebAppData URL param.
    const initData = getTelegramInitData(tg);
    const u = extractTelegramUser(tg);

    // Let Telegram know we are ready to be shown.
    if (tg) {
      try {
        tg.ready();
      } catch (_) {
        // ignore
      }
    }

    if (!u) {
      // Show a small badge so it's obvious what we detected.
      const where = tg ? 'Telegram WebApp' : initData ? 'Telegram initData' : 'Telegram';
      if (tgUserNameEl) tgUserNameEl.textContent = where;
      if (tgUserUsernameEl) tgUserUsernameEl.textContent = initData ? 'user missing in initData' : 'initData missing';
      if (tgUserAvatarEl) {
        tgUserAvatarEl.removeAttribute('src');
        tgUserAvatarEl.classList.add('hidden');
      }
      if (tg || initData || isTelegramUserAgent()) show(tgUserEl);
      else hide(tgUserEl);
      return null;
    }

    const name = [u.first_name, u.last_name].filter(Boolean).join(' ').trim();
    const username = u.username ? `@${u.username}` : '';
    const photoUrl = u.photo_url || '';

    if (tgUserNameEl) tgUserNameEl.textContent = name || username || 'Telegram user';
    if (tgUserUsernameEl) tgUserUsernameEl.textContent = username || (u.id ? `id: ${u.id}` : '');

    if (tgUserAvatarEl) {
      if (photoUrl) {
        tgUserAvatarEl.src = photoUrl;
        tgUserAvatarEl.classList.remove('hidden');
      } else {
        tgUserAvatarEl.removeAttribute('src');
        tgUserAvatarEl.classList.add('hidden');
      }
    }

    show(tgUserEl);
    return u;
  }

  function updateTelegramAvailabilityUI(tg) {
    const hasWebApp = !!tg;
    const initData = getTelegramInitData(tg);
    const hasInitData = !!initData;
    const isTgUA = isTelegramUserAgent() || !!getTelegramInitDataFromUrl();
    if (hasWebApp || hasInitData) {
      hide(tgWarningEl);
    } else {
      // Distinguish "opened outside Telegram" from "opened in Telegram, but not as WebApp".
      if (tgWarningEl) {
        tgWarningEl.textContent = isTgUA
          ? 'Открыто в Telegram, но не как WebApp. Откройте через кнопку WebApp в боте, чтобы подтянуть профиль.'
          : 'Откройте через Telegram WebApp, чтобы привязать Telegram.';
      }
      show(tgWarningEl);
    }
    if (btnTelegramVerify) btnTelegramVerify.disabled = !hasInitData;
  }

  function setupTelegramUI() {
    // Telegram Desktop sometimes injects WebApp a bit later than DOMContentLoaded.
    // Retry a few times to avoid false negatives (warning shown + no user badge).
    let tries = 0;
    const maxTries = 80; // ~20s
    const delayMs = 250;

    const tick = () => {
      const tg = getTelegramWebApp();
      updateTelegramAvailabilityUI(tg);
      renderTelegramUser(tg);

      // Stop when we have WebApp or we exhausted retries.
      if (tg || tries >= maxTries) return;
      tries += 1;
      setTimeout(tick, delayMs);
    };

    tick();
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

    if (buildBadgeEl) buildBadgeEl.textContent = `MVP · ${UI_BUILD}`;

    // Telegram is optional for now (we'll enforce later).
    // 1) Render TG user badge (name/@username/photo) automatically when opened inside Telegram WebApp.
    // 2) Show/hide warning & enable/disable link button based on TG availability.
    setupTelegramUI();

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
    let tokenRefreshPromise = null;
    let tokenChecked = false;

    async function refreshMeFromToken() {
      const savedToken = localStorage.getItem(TOKEN_KEY);
      if (!savedToken) {
        tokenChecked = true;
        return;
      }
      try {
        const u = await me(savedToken);
        currentToken = savedToken;
        currentProfile = u;
        renderProfile(u);
        isLoggedIn = true;
        tokenChecked = true;
      } catch (_) {
        localStorage.removeItem(TOKEN_KEY);
        currentToken = null;
        currentProfile = null;
        isLoggedIn = false;
        tokenChecked = true;
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
        inviterInfoEl.textContent = u.inviter?.telegram_id ? String(u.inviter.telegram_id) : '—';
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
        const r = u.referrals || {};
        const slots = r.slots || {};
        const eligible = r.eligible_payout ? 'yes' : 'no';
        cabStatsEl.textContent =
          `invited=${s.invited_count || 0}, paid=${s.paid_count || 0}, payouts=${s.payouts_count || 0}, points=${s.points || 0}` +
          ` | slots=${slots.used ?? '—'}/${slots.limit ?? '—'}, l1_confirmed=${r.confirmed_l1 ?? '—'}, payout_ok=${eligible}`;
      }

      if (status === 'ACTIVE') {
        showScreen('cabinet');
        setStatus('logged in');
      } else {
        showScreen('onboarding');
        setStatus('logged in');
      }

      // Payment/intent gating (business rules): Telegram + referrer + author code are required
      const hasTg = !!u.telegram?.id;
      const hasReferrer = !!u.inviter?.telegram_id;
      const hasCode = !!u.author_code;
      if (btnPayCreate) btnPayCreate.disabled = !(hasTg && hasReferrer && hasCode);
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

    // 1) Start token refresh ASAP. This prevents a common race:
    // TonConnect restores wallet quickly (without tonProof), `onStatusChange` fires,
    // and we must NOT force-disconnect if the user already has a valid token.
    tokenRefreshPromise = refreshMeFromToken().finally(() => {
      // 2) Always prepare tonProof for the next connect attempt (fresh payload, 5m TTL).
      prepareTonProof();
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
          // If token exists (or is still being checked), we must NOT disconnect,
          // otherwise the user sees "connection reset" on every refresh.
          const hasSavedToken = !!localStorage.getItem(TOKEN_KEY);
          if (isLoggedIn || hasSavedToken || !tokenChecked) {
            if (tokenRefreshPromise) await tokenRefreshPromise;
            if (isLoggedIn) {
              setStatus('logged in');
              return;
            }
          }

          // No valid token -> require a fresh connect with tonProof.
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
        const tg2 = getTelegramWebApp();
        const initData = getTelegramInitData(tg2);
        if (!initData) return setStatus('Ошибка: Telegram initData отсутствует');
        setStatus('telegram verify…');
        try {
          await postWithBearer('/telegram/verify', currentToken, { initData });
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
        if (!v) return setStatus('Ошибка: referrer пустой');
        if (!/^\d+$/.test(v)) return setStatus('Ошибка: нужен telegram_id (только цифры)');
        setStatus('saving inviter…');
        try {
          await postWithBearer('/inviter/apply', currentToken, { inviter: v });
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
        // enforce required inputs
        if (!currentProfile?.telegram?.id) return setStatus('Ошибка: сначала привяжите Telegram');
        if (!currentProfile?.inviter?.telegram_id) return setStatus('Ошибка: укажите кто пригласил (telegram_id)');
        if (!currentProfile?.author_code) return setStatus('Ошибка: введите код автора');
        setStatus('creating payment…');
        try {
          // SSOT: create Participation(PENDING) + payment intent in one step
          lastPaymentIntent = await postWithBearer('/participation/create', currentToken, {});
          if (paymentInfo) {
            const ton = Number(lastPaymentIntent.amount || '0') / 1e9;
            const pid = lastPaymentIntent.participation_id ? `, participation_id: ${lastPaymentIntent.participation_id}` : '';
            const slots = lastPaymentIntent.slots_used != null ? `, slots_used: ${lastPaymentIntent.slots_used}/3` : '';
            paymentInfo.textContent = `receiver: ${lastPaymentIntent.receiver}, amount: ${ton} TON, valid_until: ${lastPaymentIntent.valid_until}, comment: ${lastPaymentIntent.comment}${pid}${slots}`;
          }
          if (btnPaySend) show(btnPaySend);
          setStatus('payment created');
        } catch (e) {
          // Surface 409 referrer_limit nicely if backend returns it as error string
          const msg = e instanceof Error ? e.message : 'payment create error';
          setStatus(`Ошибка: ${msg}`);
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


