(() => {
  const API_BASE = window.location.origin + '/api/v1';
  const TOKEN_KEY = 'soulpull_token';
  const UI_BUILD = 'ui-20260101-11';

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

  const ADMIN_TOKEN_KEY = 'soulpull_admin_token';
  const adminTokenInput = el('admin-token');
  const btnAdminRefresh = el('btn-admin-refresh');
  const adminStatusEl = el('admin-status');
  const adminPendingEl = el('admin-pending');
  const adminPayoutsEl = el('admin-payouts');

  const btnOpenTonconnect = el('btn-open-tonconnect');
  const nextPillEl = el('next-pill');
  const chkWalletEl = el('chk-wallet');
  const chkTelegramEl = el('chk-telegram');
  const chkReferrerEl = el('chk-referrer');
  const chkCodeEl = el('chk-code');
  const chkPaidEl = el('chk-paid');
  const chkConfirmedEl = el('chk-confirmed');
  const btnNextAction = el('btn-next-action');
  const nextHintEl = el('next-hint');

  const btnPayoutRequest = el('btn-payout-request');
  const payoutHintEl = el('payout-hint');
  const payoutListEl = el('payout-list');
  const btnRefresh = el('btn-refresh');

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
    if (toastEl) toastEl.textContent = text;
  }

  function humanizeApiErrorMessage(msg) {
    const m = String(msg || '').trim();
    if (!m) return 'неизвестная ошибка';
    if (m === 'unauthorized' || m.includes('failed: 401')) return 'нет авторизации: подключите кошелёк и заново войдите (TonConnect + tonProof)';
    if (m.includes('failed: 403') || m === 'forbidden') return 'доступ запрещён (403)';
    if (m.includes('referrer_telegram_id must be digits')) return 'реферер должен быть telegram_id (только цифры), не @username и не адрес кошелька';
    if (m.includes('self_referral')) return 'нельзя указать себя как реферера';
    if (m.includes('inviter can not be changed after activation')) return 'реферера нельзя менять после активации';
    if (m.includes('author_code already applied')) return 'код автора уже применён (повторно нельзя)';
    if (m.includes('referrer_limit')) return 'у этого реферера закончились слоты (лимит 3/3)';
    return m;
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

  function setTag(elm, ok, text) {
    if (!elm) return;
    elm.textContent = text || (ok ? 'OK' : '—');
    elm.classList.remove('tag--ok', 'tag--bad', 'tag--warn');
    if (ok === true) elm.classList.add('tag--ok');
    else if (ok === false) elm.classList.add('tag--bad');
    else elm.classList.add('tag--warn');
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
    let currentWalletAddress = null;
    let tokenRefreshPromise = null;
    let tokenChecked = false;

    function debugTonConnectStorage() {
      try {
        const keys = Object.keys(localStorage || {});
        const tonKeys = keys.filter((k) => /ton|tonconnect/i.test(k));
        return tonKeys.length ? `storage:${tonKeys.length}` : 'storage:empty';
      } catch (_) {
        return 'storage:na';
      }
    }

    async function maybeAutoTelegramVerify(profile) {
      // If TG initData exists and profile isn't linked yet -> auto-link (no manual click).
      if (!currentToken) return;
      if (profile?.telegram?.id) return;

      const tg = getTelegramWebApp();
      const initData = getTelegramInitData(tg);
      if (!initData) return;

      try {
        if (btnTelegramVerify) {
          btnTelegramVerify.disabled = true;
          btnTelegramVerify.textContent = 'Привязка Telegram…';
        }
        await postWithBearer('/telegram/verify', currentToken, { initData });
        const u = await me(currentToken);
        currentProfile = u;
        renderProfile(u);
        setStatus('telegram linked');
      } catch (e) {
        // Leave a manual fallback button if auto-link failed.
        if (btnTelegramVerify) {
          btnTelegramVerify.disabled = false;
          btnTelegramVerify.textContent = 'Привязать Telegram';
        }
      }
    }

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
        await maybeAutoTelegramVerify(u);
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

    async function refreshAll() {
      if (!currentToken) {
        setStatus('нет токена (сначала подключите кошелёк)');
        return;
      }
      setStatus('refreshing…');
      try {
        const u = await me(currentToken);
        currentProfile = u;
        renderProfile(u);
        await maybeAutoTelegramVerify(u);
        // payout list
        try {
          const list = await getWithBearer('/payout/me', currentToken);
          if (payoutListEl) {
            const items = list?.items || [];
            payoutListEl.textContent = items.length ? items.map((x) => `#${x.id}:${x.status}`).join(', ') : '—';
          }
        } catch (_) {
          // ignore
        }
        setStatus('ok');
      } catch (e) {
        setStatus(`Ошибка: ${e instanceof Error ? e.message : 'refresh error'}`);
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
      const activePart = u.cycle?.active_participation || null;
      const isConfirmed = activePart && activePart.status === 'CONFIRMED';

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
      // Don't hard-disable the pay button: disabled buttons feel "dead" (no click feedback).
      // We still enforce rules inside the click handler with a clear status message.
      if (btnPayCreate) btnPayCreate.disabled = false;

      // Telegram button UX: hide/disable when already linked.
      if (btnTelegramVerify) {
        if (hasTg) {
          btnTelegramVerify.disabled = true;
          btnTelegramVerify.textContent = 'Telegram привязан';
        } else {
          // Keep enabled only if initData exists (or will be auto-linked soon)
          const initData = getTelegramInitData(getTelegramWebApp());
          btnTelegramVerify.disabled = !initData;
          btnTelegramVerify.textContent = 'Привязать Telegram';
        }
      }

      // Checklist / next action
      setTag(chkWalletEl, !!currentWalletAddress, currentWalletAddress ? 'OK' : 'нет');
      setTag(chkTelegramEl, hasTg, hasTg ? 'OK' : 'нужно');
      setTag(chkReferrerEl, hasReferrer, hasReferrer ? 'OK' : 'нужно');
      setTag(chkCodeEl, hasCode, hasCode ? 'OK' : 'нужно');
      setTag(chkPaidEl, !!lastPaymentIntent, lastPaymentIntent ? 'создано' : 'нет');
      setTag(chkConfirmedEl, isConfirmed ? true : null, isConfirmed ? 'CONFIRMED' : (activePart ? activePart.status : '—'));

      if (nextPillEl) {
        nextPillEl.textContent = isConfirmed ? 'Готово' : 'Шаги';
      }

      if (btnNextAction && nextHintEl) {
        let action = null;
        let hint = '';
        if (!currentWalletAddress) {
          action = () => btnOpenTonconnect?.click();
          hint = 'Шаг 1: подключите кошелёк через TonConnect (Tonkeeper).';
        } else if (!hasTg) {
          action = () => btnTelegramVerify?.click();
          hint = 'Шаг 2: нажмите «Привязать Telegram».';
        } else if (!hasReferrer) {
          action = () => inviterInput?.focus();
          hint = 'Шаг 3: введите telegram_id пригласившего и нажмите «Сохранить».';
        } else if (!hasCode) {
          action = () => authorCodeInput?.focus();
          hint = 'Шаг 4: введите код автора и нажмите «Применить».';
        } else if (!lastPaymentIntent) {
          action = () => btnPayCreate?.click();
          hint = 'Шаг 5: нажмите «Оплатить 3 USDT» (создастся intent).';
        } else {
          action = () => btnPaySend?.click();
          hint = 'Шаг 5: нажмите «Отправить через кошелёк» и подтвердите в Tonkeeper.';
        }
        nextHintEl.textContent = hint;
        btnNextAction.onclick = () => {
          try { action && action(); } catch (_) {}
        };
      }

      // Payout UI
      const eligible = !!u.referrals?.eligible_payout;
      if (btnPayoutRequest) btnPayoutRequest.disabled = !eligible;
      if (payoutHintEl) payoutHintEl.textContent = eligible ? 'Условия выполнены. Можно запросить выплату.' : 'Нужно: участие CONFIRMED + 3 подтверждённых L1.';
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
          currentWalletAddress = null;
          setAddress('');
          setStatus(`wallet disconnected (${debugTonConnectStorage()})`);
          showScreen('connect');
          return;
        }

        currentWalletAddress = address;
        setAddress(address);
        setStatus(`wallet connected (${debugTonConnectStorage()})`);
        showScreen('onboarding');
        if (currentProfile) renderProfile(currentProfile);

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
          // If token exists (or is still being checked), that's OK (stay logged in).
          const hasSavedToken = !!localStorage.getItem(TOKEN_KEY);
          if (isLoggedIn || hasSavedToken || !tokenChecked) {
            if (tokenRefreshPromise) await tokenRefreshPromise;
            if (isLoggedIn) {
              setStatus('logged in');
              return;
            }
          }

          // No valid token -> require a fresh connect with tonProof.
          // IMPORTANT: do NOT auto-disconnect on refresh, it looks like "TonConnect reset".
          setStatus('Нужна авторизация: откройте TonConnect и переподключите кошелёк.');
          await prepareTonProof();
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
        await maybeAutoTelegramVerify(u);
        isLoggedIn = true;
      } catch (e) {
        setStatus(`Ошибка: ${e instanceof Error ? e.message : 'unknown error'}`);
      }
    });

    // Explicit restore (some WebViews require awaiting it to reflect UI state)
    (async () => {
      try {
        if (tonConnectUI && tonConnectUI.connectionRestored && typeof tonConnectUI.connectionRestored.then === 'function') {
          await tonConnectUI.connectionRestored;
        } else if (tonConnectUI && typeof tonConnectUI.restoreConnection === 'function') {
          await tonConnectUI.restoreConnection();
        }
      } catch (_) {
        // ignore
      }
      try {
        const w = tonConnectUI?.wallet || tonConnectUI?.connectedWallet;
        const addr = w?.account?.address;
        if (addr && !currentWalletAddress) {
          currentWalletAddress = addr;
          setAddress(addr);
          setStatus(`wallet restored (${debugTonConnectStorage()})`);
          showScreen('onboarding');
          if (currentProfile) renderProfile(currentProfile);
        }
      } catch (_) {
        // ignore
      }
    })();

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
        if (!/^\d+$/.test(v)) {
          if (v.startsWith('@')) return setStatus('Ошибка: нужен telegram_id (цифры), а не @username');
          return setStatus('Ошибка: нужен telegram_id (только цифры)');
        }
        setStatus('saving inviter…');
        try {
          await postWithBearer('/inviter/apply', currentToken, { inviter: v });
          const u = await me(currentToken);
          currentProfile = u;
          renderProfile(u);
          setStatus('inviter saved');
        } catch (e) {
          const raw = e instanceof Error ? e.message : 'inviter error';
          setStatus(`Ошибка: ${humanizeApiErrorMessage(raw)}`);
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
          const raw = e instanceof Error ? e.message : 'author code error';
          setStatus(`Ошибка: ${humanizeApiErrorMessage(raw)}`);
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
            const usdt = Number(lastPaymentIntent.jetton_amount || '0') / 1e6;
            const gasTon = Number(lastPaymentIntent.forward_ton_nanotons || lastPaymentIntent.amount || '0') / 1e9;
            const pid = lastPaymentIntent.participation_id ? `, participation_id: ${lastPaymentIntent.participation_id}` : '';
            const slots = lastPaymentIntent.slots_used != null ? `, slots_used: ${lastPaymentIntent.slots_used}/3` : '';
            paymentInfo.textContent =
              `pay: ${usdt} USDT` +
              `, receiver: ${lastPaymentIntent.receiver_wallet || lastPaymentIntent.receiver}` +
              `, gas: ~${gasTon} TON` +
              `, valid_until: ${lastPaymentIntent.valid_until}` +
              `, comment: ${lastPaymentIntent.comment}${pid}${slots}`;
          }
          if (btnPaySend) show(btnPaySend);
          setStatus('payment created');
          if (currentProfile) renderProfile(currentProfile);
        } catch (e) {
          // Surface 409 referrer_limit nicely if backend returns it as error string
          const msg = e instanceof Error ? e.message : 'payment create error';
          setStatus(`Ошибка: ${humanizeApiErrorMessage(msg)}`);
        }
      });
    }

    if (btnPaySend) {
      btnPaySend.addEventListener('click', async () => {
        if (!lastPaymentIntent) return setStatus('Ошибка: сначала создайте платёж');
        if (!currentWalletAddress) return setStatus('Ошибка: кошелёк не подключен');
        if (!window.TonWeb) return setStatus('Ошибка: tonweb не загрузился');
        try {
          setStatus('opening wallet…');
          // 1) Resolve user's USDT jetton-wallet address via backend (Toncenter).
          const jwRes = await fetch(API_BASE + '/jetton/wallet', {
            method: 'GET',
            headers: { Authorization: `Bearer ${currentToken}` },
          });
          const jwData = await jwRes.json().catch(() => null);
          if (!jwRes.ok) throw new Error(jwData?.error || `jetton/wallet failed: ${jwRes.status}`);
          const userJettonWallet = jwData?.wallet_address;
          if (!userJettonWallet) throw new Error('jetton/wallet: missing wallet_address');

          // 2) Build JettonTransfer payload (op=0x0f8a7ea5) using tonweb.
          const TonWeb = window.TonWeb;
          const Cell = TonWeb.boc.Cell;
          const Address = TonWeb.utils.Address;

          const jettonAmount = String(lastPaymentIntent.jetton_amount || '');
          const receiverWallet = String(lastPaymentIntent.receiver_wallet || lastPaymentIntent.receiver || '');
          const forwardTon = String(lastPaymentIntent.forward_ton_nanotons || lastPaymentIntent.amount || '');
          const validUntil = Number(lastPaymentIntent.valid_until || 0);
          if (!jettonAmount || !receiverWallet || !forwardTon || !validUntil) throw new Error('payment intent incomplete');

          const body = new Cell();
          body.bits.writeUint(0x0f8a7ea5, 32); // transfer op
          body.bits.writeUint(0, 64); // query_id
          body.bits.writeCoins(jettonAmount); // jetton amount (USDT units)
          body.bits.writeAddress(new Address(receiverWallet)); // destination owner
          body.bits.writeAddress(new Address(currentWalletAddress)); // response destination
          body.bits.writeBit(0); // no custom payload
          body.bits.writeCoins('1'); // forward TON amount inside payload (minimal)
          body.bits.writeBit(1); // forward payload in ref
          body.refs.push(new Cell()); // empty payload

          const payloadB64 = TonWeb.utils.bytesToBase64(body.toBoc(false));

          // 3) Send transaction to user's jetton-wallet with attached TON for gas.
          await tonConnectUI.sendTransaction({
            validUntil,
            messages: [{ address: userJettonWallet, amount: forwardTon, payload: payloadB64 }],
          });

          setStatus('tx sent. paste tx hash below');
          if (currentProfile) renderProfile(currentProfile);
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

    if (btnOpenTonconnect) {
      btnOpenTonconnect.addEventListener('click', async () => {
        try {
          // Open modal list (TonConnect UI)
          if (tonConnectUI && tonConnectUI.openModal) {
            await tonConnectUI.openModal();
            return;
          }
        } catch (_) {}
        // fallback: user can use top-right button
      });
    }

    if (btnPayoutRequest) {
      btnPayoutRequest.addEventListener('click', async () => {
        if (!currentToken) return setStatus('Ошибка: нет токена');
        setStatus('payout request…');
        try {
          await postWithBearer('/payout/request', currentToken, {});
          setStatus('payout requested');
          const list = await getWithBearer('/payout/me', currentToken);
          if (payoutListEl) {
            const items = list?.items || [];
            payoutListEl.textContent = items.length ? items.map((x) => `#${x.id}:${x.status}`).join(', ') : '—';
          }
        } catch (e) {
          setStatus(`Ошибка: ${e instanceof Error ? e.message : 'payout request error'}`);
        }
      });
    }

    // Admin panel (Strazh)
    function setAdminStatus(t) {
      if (adminStatusEl) adminStatusEl.textContent = t || '';
    }

    function getAdminToken() {
      const v = (adminTokenInput?.value || '').trim() || localStorage.getItem(ADMIN_TOKEN_KEY) || '';
      return String(v || '').trim();
    }

    function setAdminToken(v) {
      const t = String(v || '').trim();
      if (adminTokenInput) adminTokenInput.value = t;
      if (t) localStorage.setItem(ADMIN_TOKEN_KEY, t);
    }

    async function adminGet(path) {
      const tok = getAdminToken();
      if (!tok) throw new Error('нет X-Admin-Token');
      const res = await fetch(API_BASE + path, { method: 'GET', headers: { 'X-Admin-Token': tok } });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.error || `${path} failed: ${res.status}`);
      return data;
    }

    async function adminPost(path, body) {
      const tok = getAdminToken();
      if (!tok) throw new Error('нет X-Admin-Token');
      const res = await fetch(API_BASE + path, {
        method: 'POST',
        headers: { 'X-Admin-Token': tok, 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.error || `${path} failed: ${res.status}`);
      return data;
    }

    function renderAdminLists(pending, payouts) {
      if (adminPendingEl) {
        const items = pending?.items || [];
        adminPendingEl.innerHTML =
          '<b>Pending participations</b><br/>' +
          (items.length
            ? items
                .map((p) => {
                  const who = p.user?.telegram_username ? '@' + p.user.telegram_username : (p.user?.telegram_id ? 'tg:' + p.user.telegram_id : '—');
                  const ref = p.referrer?.telegram_id ? 'ref:' + p.referrer.telegram_id : 'ref:—';
                  return (
                    `<div class="mt">` +
                    `<div class="mono">#${p.id} ${who} ${ref} code=${p.author_code || '—'} amt=${(p.amount_usd_cents || 0) / 100}$</div>` +
                    `<div class="field mt">` +
                    `<input class="input" id="admin-tx-${p.id}" placeholder="tx_hash" />` +
                    `<button class="btn" data-admin-confirm="${p.id}">Confirm</button>` +
                    `<button class="btn" data-admin-reject="${p.id}">Reject</button>` +
                    `</div>` +
                    `</div>`
                  );
                })
                .join('')
            : '<span class="muted">—</span>');
      }
      if (adminPayoutsEl) {
        const items = payouts?.items || [];
        adminPayoutsEl.innerHTML =
          '<b>Payout requests</b><br/>' +
          (items.length
            ? items
                .map((p) => {
                  const who = p.user?.telegram_username ? '@' + p.user.telegram_username : (p.user?.telegram_id ? 'tg:' + p.user.telegram_id : '—');
                  return (
                    `<div class="mt">` +
                    `<div class="mono">#${p.id} ${who} amt=${(p.amount_usd_cents || 0) / 100}$ status=${p.status}</div>` +
                    `<div class="field mt">` +
                    `<input class="input" id="admin-payouttx-${p.id}" placeholder="tx_hash (send 1 USDT)" />` +
                    `<button class="btn" data-admin-payout-sent="${p.id}">Sent</button>` +
                    `<button class="btn" data-admin-payout-reject="${p.id}">Reject</button>` +
                    `</div>` +
                    `</div>`
                  );
                })
                .join('')
            : '<span class="muted">—</span>');
      }
    }

    if (btnRefresh) {
      btnRefresh.addEventListener('click', refreshAll);
    }

    async function refreshAdmin() {
      try {
        const tok = (adminTokenInput?.value || '').trim();
        if (tok) setAdminToken(tok);
        setAdminStatus('loading…');
        const pending = await adminGet('/admin/participations/pending');
        const payouts = await adminGet('/admin/payouts/open');
        renderAdminLists(pending, payouts);
        setAdminStatus('ok');
      } catch (e) {
        setAdminStatus(`Ошибка: ${e instanceof Error ? e.message : 'admin error'}`);
      }
    }

    if (adminTokenInput) {
      const saved = localStorage.getItem(ADMIN_TOKEN_KEY);
      if (saved) adminTokenInput.value = saved;
    }
    if (btnAdminRefresh) btnAdminRefresh.addEventListener('click', refreshAdmin);

    document.addEventListener('click', async (ev) => {
      const t = ev.target;
      if (!(t instanceof HTMLElement)) return;
      const confirmId = t.getAttribute('data-admin-confirm');
      const rejectId = t.getAttribute('data-admin-reject');
      const payoutSentId = t.getAttribute('data-admin-payout-sent');
      const payoutRejectId = t.getAttribute('data-admin-payout-reject');

      try {
        if (confirmId) {
          const tx = (document.getElementById(`admin-tx-${confirmId}`)?.value || '').trim();
          await adminPost('/participation/confirm', { participation_id: Number(confirmId), decision: 'confirm', tx_hash: tx });
          await refreshAdmin();
        } else if (rejectId) {
          const tx = (document.getElementById(`admin-tx-${rejectId}`)?.value || '').trim();
          await adminPost('/participation/confirm', { participation_id: Number(rejectId), decision: 'reject', tx_hash: tx });
          await refreshAdmin();
        } else if (payoutSentId) {
          const tx = (document.getElementById(`admin-payouttx-${payoutSentId}`)?.value || '').trim();
          await adminPost('/payout/mark', { payout_request_id: Number(payoutSentId), decision: 'sent', tx_hash: tx });
          await refreshAdmin();
        } else if (payoutRejectId) {
          await adminPost('/payout/mark', { payout_request_id: Number(payoutRejectId), decision: 'reject' });
          await refreshAdmin();
        }
      } catch (e) {
        setAdminStatus(`Ошибка: ${e instanceof Error ? e.message : 'admin action error'}`);
      }
    });
  }

  window.addEventListener('DOMContentLoaded', init);
})();


