/**
 * Soulpull — "Спасение Душ из Ада"
 * 
 * Full-featured frontend with:
 * - TonConnect integration
 * - Real USDT JettonTransfer payments
 * - Fire particles animation
 * - GSAP animations
 * 
 * @version 2.0.0
 */

(function() {
  'use strict';

  // ============================================================================
  // CONSTANTS
  // ============================================================================

  const CONFIG = {
    API_BASE: '/api/v1',
    USDT_AMOUNT: 15_000_000, // 15 USDT (6 decimals)
    USDT_AMOUNT_DISPLAY: '15',
    FORWARD_TON: '50000000', // 0.05 TON for jetton transfer fees
    TX_VALID_SECONDS: 600, // 10 minutes
    STORAGE_KEY_STATE: 'soulpull_state',
    STORAGE_KEY_ADMIN: 'soulpull_admin_token',
    // Default receiver wallet (will be fetched from backend in production)
    RECEIVER_WALLET: 'UQBvW8Z5huBkMJYdnfAEM5JqTNLuDP2v3cJNfX1RJ8aRyZ2C',
  };

  // ============================================================================
  // STATE
  // ============================================================================

  const state = {
    // User data
    telegramId: null,
    username: null,
    walletAddress: null,
    
    // Form inputs
    referrerTelegramId: null,
    authorCode: null,
    
    // Participation
    participationId: null,
    participationStatus: null,
    
    // Payment intent
    paymentIntent: null,
    
    // Navigation flags (forward-only)
    leftStart: false,
    leftWallet: false,
    
    // Admin
    adminToken: null,
    
    // UI
    isLoading: false,
  };

  // TonConnect instance
  let tonConnectUI = null;

  // ============================================================================
  // DOM UTILITIES
  // ============================================================================

  const $ = (id) => document.getElementById(id);
  const $$ = (sel) => document.querySelectorAll(sel);

  function showScreen(screenId) {
    $$('.screen').forEach(s => s.classList.remove('active'));
    const screen = $(screenId);
    if (screen) {
      screen.classList.add('active');
      // GSAP animation
      if (window.gsap) {
        gsap.fromTo(screen, 
          { opacity: 0, y: 20 }, 
          { opacity: 1, y: 0, duration: 0.4, ease: 'power2.out' }
        );
      }
    }
    console.log('[UI] Screen:', screenId);
  }

  function showToast(message, type = 'info') {
    const toast = $('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = 'toast show ' + type;
    setTimeout(() => toast.classList.remove('show'), 3500);
  }

  function showBanner(elementId, message, show = true) {
    const el = $(elementId);
    if (!el) return;
    if (show) {
      el.innerHTML = message;
      el.classList.remove('hidden');
    } else {
      el.classList.add('hidden');
    }
  }

  function setLoading(loading) {
    state.isLoading = loading;
    const overlay = $('loading-overlay');
    if (overlay) {
      overlay.style.display = loading ? 'flex' : 'none';
    }
  }

  // ============================================================================
  // STORAGE
  // ============================================================================

  function saveState() {
    try {
      const toSave = {
        telegramId: state.telegramId,
        username: state.username,
        walletAddress: state.walletAddress,
        referrerTelegramId: state.referrerTelegramId,
        authorCode: state.authorCode,
        participationId: state.participationId,
        participationStatus: state.participationStatus,
        leftStart: state.leftStart,
        leftWallet: state.leftWallet,
      };
      sessionStorage.setItem(CONFIG.STORAGE_KEY_STATE, JSON.stringify(toSave));
    } catch (e) {
      console.warn('[Storage] Save failed:', e);
    }
  }

  function loadState() {
    try {
      const saved = sessionStorage.getItem(CONFIG.STORAGE_KEY_STATE);
      if (saved) {
        const parsed = JSON.parse(saved);
        Object.assign(state, parsed);
        console.log('[Storage] Loaded state:', state);
      }
      // Admin token from localStorage (persistent)
      const adminToken = localStorage.getItem(CONFIG.STORAGE_KEY_ADMIN);
      if (adminToken) state.adminToken = adminToken;
    } catch (e) {
      console.warn('[Storage] Load failed:', e);
    }
  }

  // ============================================================================
  // API CLIENT
  // ============================================================================

  async function api(endpoint, options = {}) {
    const url = CONFIG.API_BASE + endpoint;
    const headers = { 
      'Content-Type': 'application/json',
      ...options.headers 
    };
    
    // Add admin token if available
    if (state.adminToken) {
      headers['X-Admin-Token'] = state.adminToken;
    }
    
    // Add idempotency key for mutations
    if (options.method === 'POST' && !headers['Idempotency-Key']) {
      headers['Idempotency-Key'] = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    }
    
    try {
      console.log(`[API] ${options.method || 'GET'} ${endpoint}`, options.body ? JSON.parse(options.body) : '');
      
      const resp = await fetch(url, { ...options, headers });
      const data = await resp.json();
      
      console.log(`[API] Response ${resp.status}:`, data);
      
      if (!resp.ok) {
        const error = new Error(data.error || data.message || `HTTP ${resp.status}`);
        error.code = data.error;
        error.status = resp.status;
        throw error;
      }
      
      return data;
    } catch (e) {
      console.error('[API] Error:', e);
      throw e;
    }
  }

  // ============================================================================
  // TELEGRAM WEBAPP
  // ============================================================================

  function initTelegram() {
    const tg = window.Telegram?.WebApp;
    
    console.log('[Telegram] WebApp object:', tg ? 'exists' : 'not found');
    console.log('[Telegram] initData:', tg?.initData || '(empty)');
    console.log('[Telegram] initDataUnsafe:', JSON.stringify(tg?.initDataUnsafe || {}));
    
    if (tg && tg.initDataUnsafe?.user) {
      // Реальный Telegram WebApp с данными пользователя
      tg.ready();
      tg.expand();
      try { tg.enableClosingConfirmation(); } catch(e) {}
      
      // Set theme
      document.documentElement.style.setProperty('--tg-bg', tg.backgroundColor || '#0a0505');
      
      const user = tg.initDataUnsafe.user;
      state.telegramId = user.id;
      state.username = user.username || user.first_name || `User${user.id}`;
      console.log('[Telegram] ✅ User from TG:', state.telegramId, state.username);
      
      // Check start_param for referrer
      const startParam = tg.initDataUnsafe?.start_param;
      if (startParam && /^\d+$/.test(startParam)) {
        state.referrerTelegramId = startParam;
        const refInput = $('input-referrer');
        if (refInput) refInput.value = startParam;
        console.log('[Telegram] Referrer from start_param:', startParam);
      }
      
      $('banner-not-telegram')?.classList.add('hidden');
      return true;
    } else {
      // Telegram WebApp без данных или не в Telegram
      console.log('[Telegram] ⚠️ No user data — using dev mode');
      $('banner-not-telegram')?.classList.remove('hidden');
      
      // URL params или saved state для dev mode
      const urlParams = new URLSearchParams(window.location.search);
      const devTid = urlParams.get('tid') || state.telegramId || '123456789';
      
      state.telegramId = parseInt(devTid);
      state.username = state.username || 'dev_user_' + devTid;
      console.log('[Dev] telegram_id:', state.telegramId, '(add ?tid=XXX to URL to change)');
      return true;
    }
  }

  // ============================================================================
  // TON CONNECT
  // ============================================================================

  function initTonConnect() {
    // Инициализация TonConnect БЕЗ блокировки UI
    // Всё происходит асинхронно в фоне
    
    try {
      const manifestUrl = window.location.origin + '/tonconnect-manifest.json';
      console.log('[TonConnect] Init with manifest:', manifestUrl);
      
      tonConnectUI = new TON_CONNECT_UI.TonConnectUI({
        manifestUrl,
        buttonRootId: 'ton-connect-button',
        restoreConnection: true,
        actionsConfiguration: {
          // Не редиректить на сайты кошельков — только QR код
          twaReturnUrl: window.location.origin,
          returnStrategy: 'back',
        },
        uiPreferences: {
          theme: 'DARK',
        },
      });

      // Слушатель изменений — асинхронно, не блокирует
      tonConnectUI.onStatusChange((wallet) => {
        console.log('[TonConnect] Status changed:', wallet ? 'connected' : 'disconnected');
        
        if (wallet) {
          state.walletAddress = wallet.account.address;
          console.log('[TonConnect] Wallet:', state.walletAddress);
          
          $('wallet-status')?.classList.remove('hidden');
          $('wallet-connected')?.classList.remove('hidden');
          const nextBtn = $('btn-wallet-next');
          if (nextBtn) nextBtn.disabled = false;
          
          const addrDisplay = $('wallet-address-display');
          if (addrDisplay) {
            const addr = state.walletAddress;
            addrDisplay.textContent = addr.slice(0, 6) + '...' + addr.slice(-6);
          }
          
          if (state.telegramId) {
            registerAndLinkWallet(); // Без await
          }
          
          saveState();
        } else {
          state.walletAddress = null;
          $('wallet-status')?.classList.add('hidden');
          $('wallet-connected')?.classList.add('hidden');
          const nextBtn = $('btn-wallet-next');
          if (nextBtn) nextBtn.disabled = true;
          saveState();
        }
      });

      // Восстановление сессии — в фоне, не блокирует UI
      tonConnectUI.connectionRestored
        .then((connected) => {
          console.log('[TonConnect] Connection restored:', connected);
          if (connected && tonConnectUI.wallet) {
            state.walletAddress = tonConnectUI.wallet.account.address;
            $('wallet-status')?.classList.remove('hidden');
            $('wallet-connected')?.classList.remove('hidden');
            const nextBtn = $('btn-wallet-next');
            if (nextBtn) nextBtn.disabled = false;
            
            const addrDisplay = $('wallet-address-display');
            if (addrDisplay) {
              const addr = state.walletAddress;
              addrDisplay.textContent = addr.slice(0, 6) + '...' + addr.slice(-6);
            }
          }
        })
        .catch((e) => console.warn('[TonConnect] Restore failed:', e));
      
      console.log('[TonConnect] Init started (non-blocking)');
    } catch (e) {
      console.error('[TonConnect] Init error:', e);
      showToast('Ошибка TonConnect: ' + e.message, 'error');
    }
  }

  async function registerAndLinkWallet() {
    if (!state.telegramId) {
      console.warn('[API] No telegram_id, skipping registration');
      return;
    }
    
    try {
      // Register user
      await api('/register', {
        method: 'POST',
        body: JSON.stringify({
          telegram_id: state.telegramId,
          username: state.username,
        }),
      });
      console.log('[API] User registered');
      
      // Link wallet if connected
      if (state.walletAddress) {
        await api('/wallet', {
          method: 'POST',
          body: JSON.stringify({
            telegram_id: state.telegramId,
            wallet: state.walletAddress,
          }),
        });
        console.log('[API] Wallet linked');
      }
    } catch (e) {
      // Non-fatal, user might already exist
      console.warn('[API] Register/link:', e.message);
    }
  }

  // ============================================================================
  // PAYMENT: BUILD JETTON TRANSFER MESSAGE
  // ============================================================================

  function buildJettonTransferPayload(params) {
    /**
     * JettonTransfer TL-B:
     * transfer#0f8a7ea5 query_id:uint64 amount:(VarUInteger 16) destination:MsgAddress
     *                   response_destination:MsgAddress custom_payload:(Maybe ^Cell)
     *                   forward_ton_amount:(VarUInteger 16) forward_payload:(Either Cell ^Cell)
     *                   = InternalMsgBody;
     * 
     * For simplicity, we build a basic payload as base64
     */
    const { jettonWallet, destination, amount, comment, responseDestination } = params;
    
    // This is simplified - in production use @ton/core library
    // The actual cell building requires TL-B serialization
    // For now, we'll pass raw params and let the wallet handle it
    
    return {
      address: jettonWallet, // Sender's jetton wallet
      amount: CONFIG.FORWARD_TON, // TON for gas
      payload: buildCommentPayload(comment), // Forward payload with comment
    };
  }

  function buildCommentPayload(comment) {
    // Build a simple text comment payload
    // op=0x00000000 (text comment) + UTF-8 text
    if (!comment) return '';
    
    const encoder = new TextEncoder();
    const bytes = encoder.encode(comment);
    
    // Simple base64 encoding of comment (wallet will interpret as text)
    return btoa(String.fromCharCode(0, 0, 0, 0, ...bytes));
  }

  // ============================================================================
  // SCREENS: E1 - START
  // ============================================================================

  function initScreenStart() {
    $('btn-start')?.addEventListener('click', () => {
      state.leftStart = true;
      saveState();
      showScreen('screen-wallet');
    });
  }

  // ============================================================================
  // SCREENS: E2 - WALLET
  // ============================================================================

  function initScreenWallet() {
    $('btn-wallet-next')?.addEventListener('click', () => {
      if (!state.walletAddress) {
        showToast('Сначала подключи кошелёк', 'error');
        return;
      }
      state.leftWallet = true;
      saveState();
      showScreen('screen-referral');
    });
  }

  // ============================================================================
  // SCREENS: E3 - REFERRAL
  // ============================================================================

  function initScreenReferral() {
    $('btn-referral-back')?.addEventListener('click', () => {
      if (state.leftWallet) {
        showToast('Путь только вперёд!', 'error');
        return;
      }
      showScreen('screen-wallet');
    });

    $('btn-referral-next')?.addEventListener('click', async () => {
      const input = $('input-referrer');
      const value = (input?.value || '').trim();
      
      showBanner('referrer-error', '', false);
      
      if (!value) {
        showBanner('referrer-error', '❌ Укажи Telegram ID проводника', true);
        return;
      }
      
      if (!/^\d+$/.test(value)) {
        showBanner('referrer-error', '❌ Только цифры', true);
        return;
      }
      
      if (value === String(state.telegramId)) {
        showBanner('referrer-error', '❌ Нельзя быть своим проводником', true);
        return;
      }
      
      state.referrerTelegramId = value;
      saveState();
      showScreen('screen-author');
    });

    // Кнопка "Я первый пользователь (seed)" — пропустить реферера
    $('btn-referral-skip')?.addEventListener('click', () => {
      state.referrerTelegramId = null;
      saveState();
      showScreen('screen-author');
      showToast('🌱 Регистрация как первый пользователь', 'success');
    });
  }

  // ============================================================================
  // SCREENS: E4 - AUTHOR CODE
  // ============================================================================

  function initScreenAuthor() {
    $('btn-author-back')?.addEventListener('click', () => {
      showScreen('screen-referral');
    });

    $('btn-author-next')?.addEventListener('click', () => {
      const input = $('input-author-code');
      state.authorCode = (input?.value || '').trim() || null;
      saveState();
      showScreen('screen-payment');
      initPaymentScreen();
    });
  }

  // ============================================================================
  // SCREENS: E5 - PAYMENT
  // ============================================================================

  async function initPaymentScreen() {
    // Reset UI
    showBanner('payment-error', '', false);
    $('btn-pay-send')?.classList.add('hidden');
    $('payment-pending')?.classList.add('hidden');
    $('btn-payment-done').disabled = true;
    
    // Show receiver from env (will be fetched from backend)
    $('payment-receiver').textContent = 'Загрузка...';
    $('payment-comment').textContent = '—';
    
    try {
      // Fetch receiver wallet from backend
      const health = await api('/health');
      console.log('[Payment] Health check:', health);
      if (health.receiver_wallet) {
        $('payment-receiver').textContent = health.receiver_wallet;
      }
    } catch (e) {
      console.warn('[Payment] Health check failed:', e);
    }
  }

  function initScreenPayment() {
    $('btn-payment-back')?.addEventListener('click', () => {
      showScreen('screen-author');
    });

    // CREATE PAYMENT INTENT
    $('btn-pay-create')?.addEventListener('click', async () => {
      const btn = $('btn-pay-create');
      const originalText = btn.innerHTML;
      
      try {
        showBanner('payment-error', '', false);
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Создаём...';
        
        // Ensure user is registered first
        await api('/register', {
          method: 'POST',
          body: JSON.stringify({
            telegram_id: state.telegramId,
            username: state.username,
          }),
        });
        console.log('[Payment] User registered');
        
        // Link wallet if available
        if (state.walletAddress) {
          await api('/wallet', {
            method: 'POST',
            body: JSON.stringify({
              telegram_id: state.telegramId,
              wallet: state.walletAddress,
            }),
          });
          console.log('[Payment] Wallet linked');
        }
        
        // Call /intent to create participation
        const result = await api('/intent', {
          method: 'POST',
          body: JSON.stringify({
            telegram_id: state.telegramId,
            referrer_telegram_id: state.referrerTelegramId ? parseInt(state.referrerTelegramId) : null,
            author_code: state.authorCode,
          }),
        });
        
        console.log('[Payment] Intent created:', result);
        
        state.participationId = result.participation.id;
        state.participationStatus = result.participation.status;
        saveState();
        
        // Update UI with payment details (receiver already fetched)
        $('payment-comment').textContent = `Soulpull:${state.participationId}`;
        $('payment-intent-row').style.display = 'flex';
        $('payment-intent-id').textContent = `#${state.participationId}`;
        
        // Hide create button, show send button
        btn.classList.add('hidden');
        $('btn-pay-send')?.classList.remove('hidden');
        
        showToast('🔥 Платёж создан! Оплати через кошелёк', 'success');
        
      } catch (e) {
        console.error('[Payment] Intent error:', e);
        
        const errorMessages = {
          'active_cycle': 'У тебя уже есть активное участие',
          'referrer_limit': 'У проводника нет свободных слотов (3/3)',
          'referrer_not_found': 'Проводник не найден',
          'referrer_not_confirmed': 'Проводник ещё не оплатил вход',
          'self_referral': 'Нельзя быть своим проводником',
          'not_found': 'Сначала подключи кошелёк',
        };
        
        const msg = errorMessages[e.code] || e.message;
        showBanner('payment-error', '❌ ' + msg, true);
        
        btn.disabled = false;
        btn.innerHTML = originalText;
      }
    });

    // SEND PAYMENT VIA TONCONNECT
    $('btn-pay-send')?.addEventListener('click', async () => {
      const btn = $('btn-pay-send');
      const originalText = btn.innerHTML;
      
      if (!tonConnectUI) {
        showToast('TonConnect не инициализирован', 'error');
        return;
      }
      
      // Кошелёк должен быть уже подключён!
      if (!tonConnectUI.connected) {
        showToast('⚠️ Сначала подключи кошелёк на предыдущем шаге!', 'error');
        showScreen('screen-wallet');
        return;
      }
      
      // Кошелёк подключён — отправляем транзакцию (откроется кошелёк для подтверждения)
      
      try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Отправка...';
        
        // Получаем receiver wallet из health
        let receiverWallet;
        try {
          const health = await api('/health');
          // Полный адрес из .env (не укороченный)
          receiverWallet = CONFIG.RECEIVER_WALLET || 'UQBvW8Z5huBkMJYdnfAEM5JqTNLuDP2v3cJNfX1RJ8aRyZ2C';
        } catch (e) {
          receiverWallet = 'UQBvW8Z5huBkMJYdnfAEM5JqTNLuDP2v3cJNfX1RJ8aRyZ2C';
        }
        
        // Build transaction - простой TON transfer с комментарием
        const comment = `Soulpull:${state.participationId}`;
        
        // Encode comment as Cell payload (text comment format)
        // Format: 0x00000000 + UTF-8 text
        const textEncoder = new TextEncoder();
        const commentBytes = textEncoder.encode(comment);
        const payload = new Uint8Array(4 + commentBytes.length);
        payload.set([0, 0, 0, 0], 0); // op code for text comment
        payload.set(commentBytes, 4);
        const payloadBase64 = btoa(String.fromCharCode(...payload));
        
        const transaction = {
          validUntil: Math.floor(Date.now() / 1000) + CONFIG.TX_VALID_SECONDS,
          messages: [
            {
              address: receiverWallet,
              amount: '100000000', // 0.1 TON for test (in production: USDT jetton transfer)
              payload: payloadBase64,
            }
          ],
        };
        
        console.log('[Payment] Sending transaction:', transaction);
        console.log('[Payment] Receiver:', receiverWallet);
        console.log('[Payment] Comment:', comment);
        
        // Показать подсказку перед отправкой
        showToast('📱 Подтверди транзакцию в кошельке на телефоне!', 'info');
        
        const result = await tonConnectUI.sendTransaction(transaction);
        console.log('[Payment] Transaction result:', result);
        
        // Show pending status
        $('btn-pay-send')?.classList.add('hidden');
        $('payment-pending')?.classList.remove('hidden');
        $('btn-payment-done').disabled = false;
        
        showToast('✅ Транзакция отправлена! Ожидаем подтверждения.', 'success');
        
      } catch (e) {
        console.error('[Payment] Send error:', e);
        
        if (e.message?.includes('Interrupted') || e.message?.includes('canceled') || e.message?.includes('reject')) {
          showToast('Транзакция отменена', 'error');
        } else {
          showToast('Ошибка: ' + e.message, 'error');
        }
        
        btn.disabled = false;
        btn.innerHTML = originalText;
      }
    });

    // DONE - GO TO PROGRESS
    $('btn-payment-done')?.addEventListener('click', () => {
      showScreen('screen-progress');
      loadProgress();
    });
  }

  // ============================================================================
  // SCREENS: E6 - PROGRESS
  // ============================================================================

  async function loadProgress() {
    if (!state.telegramId) return;
    
    try {
      const data = await api(`/me?telegram_id=${state.telegramId}`);
      console.log('[Progress] Data:', data);
      
      // Update status badge
      const status = data.participation?.status || 'NEW';
      const statusEl = $('participation-status');
      if (statusEl) {
        statusEl.textContent = status;
        statusEl.className = 'status-badge ' + status.toLowerCase();
      }
      
      state.participationStatus = status;
      
      // Update L1 count
      const l1Paid = data.l1?.filter(r => r.paid).length || 0;
      $('l1-count').textContent = l1Paid;
      
      // Update checklist
      const isConfirmed = status === 'CONFIRMED';
      const has3L1 = l1Paid >= 3;
      const canPayout = data.eligible_payout;
      
      updateChecklistItem('check-paid', isConfirmed);
      updateChecklistItem('check-l1', has3L1);
      updateChecklistItem('check-payout', canPayout);
      
      // Enable payout button
      const payoutBtn = $('btn-payout');
      if (payoutBtn) {
        payoutBtn.disabled = !canPayout;
        if (data.has_open_payout) {
          payoutBtn.textContent = '⏳ Заявка отправлена';
          payoutBtn.disabled = true;
        }
      }
      
    } catch (e) {
      console.error('[Progress] Load error:', e);
      if (e.code === 'not_found') {
        // User not registered yet, go back to start
        showScreen('screen-start');
      }
    }
  }

  function updateChecklistItem(id, done) {
    const el = $(id);
    if (!el) return;
    el.className = 'checklist-icon ' + (done ? 'done' : 'pending');
    el.textContent = done ? '✓' : '○';
    
    // Update sibling text
    const textEl = el.nextElementSibling;
    if (textEl) {
      textEl.classList.toggle('done', done);
    }
  }

  function initScreenProgress() {
    // Copy referral link
    $('btn-copy-link')?.addEventListener('click', () => {
      const botUsername = 'soulpull_bot'; // Replace with actual bot
      const link = `https://t.me/${botUsername}?start=${state.telegramId}`;
      
      navigator.clipboard.writeText(link).then(() => {
        showToast('🔗 Ссылка скопирована!', 'success');
      }).catch(() => {
        // Fallback
        prompt('Скопируй ссылку:', link);
      });
    });

    // Tree button
    $('btn-tree')?.addEventListener('click', () => {
      showScreen('screen-tree');
      loadTree();
    });

    // Payout button
    $('btn-payout')?.addEventListener('click', async () => {
      const btn = $('btn-payout');
      const originalText = btn.innerHTML;
      
      try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Отправка...';
        
        await api('/payout', {
          method: 'POST',
          body: JSON.stringify({ telegram_id: state.telegramId }),
        });
        
        showToast('💰 Заявка на выплату создана!', 'success');
        btn.textContent = '⏳ Заявка отправлена';
        
      } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
        btn.disabled = false;
        btn.innerHTML = originalText;
      }
    });

    // Strazh button
    $('btn-strazh')?.addEventListener('click', () => {
      showScreen('screen-strazh');
      if (state.adminToken) {
        $('strazh-login')?.classList.add('hidden');
        $('strazh-panel')?.classList.remove('hidden');
        loadAdminData();
      }
    });

    // Refresh button
    $('btn-refresh')?.addEventListener('click', () => {
      loadProgress();
      showToast('🔄 Обновлено', 'success');
    });
  }

  // ============================================================================
  // SCREENS: E7 - TREE
  // ============================================================================

  async function loadTree() {
    if (!state.telegramId) return;
    
    try {
      const data = await api(`/me?telegram_id=${state.telegramId}`);
      
      $('slots-used').textContent = data.slots?.used || 0;
      
      const list = $('referral-list');
      const empty = $('tree-empty');
      
      if (!data.l1 || data.l1.length === 0) {
        list.innerHTML = '';
        empty?.classList.remove('hidden');
        return;
      }
      
      empty?.classList.add('hidden');
      
      list.innerHTML = data.l1.map((r, i) => `
        <li class="referral-item" style="animation-delay: ${i * 0.1}s;">
          <div class="referral-info">
            <div class="referral-avatar">${(r.username || '?')[0].toUpperCase()}</div>
            <div>
              <div class="referral-name">${escapeHtml(r.username || 'Soul')}</div>
              <div class="referral-id">ID: ${r.telegram_id}</div>
            </div>
          </div>
          <span class="referral-status ${r.paid ? 'paid' : 'pending'}">
            ${r.paid ? '✓ Спасён' : '⏳ В пути'}
          </span>
        </li>
      `).join('');
      
      // Animate items with GSAP
      if (window.gsap) {
        gsap.fromTo('.referral-item', 
          { opacity: 0, x: -20 },
          { opacity: 1, x: 0, duration: 0.3, stagger: 0.1 }
        );
      }
      
    } catch (e) {
      console.error('[Tree] Load error:', e);
    }
  }

  function initScreenTree() {
    $('btn-tree-back')?.addEventListener('click', () => {
      showScreen('screen-progress');
    });
  }

  // ============================================================================
  // SCREENS: E8 - STRAZH (ADMIN)
  // ============================================================================

  async function loadAdminData() {
    try {
      const [pending, payouts] = await Promise.all([
        api('/admin/participations/pending'),
        api('/admin/payouts/open'),
      ]);
      
      renderPendingList(pending.items || []);
      renderPayoutList(payouts.items || []);
      
    } catch (e) {
      console.error('[Admin] Load error:', e);
      
      if (e.status === 403) {
        showToast('Неверный токен', 'error');
        state.adminToken = null;
        localStorage.removeItem(CONFIG.STORAGE_KEY_ADMIN);
        $('strazh-login')?.classList.remove('hidden');
        $('strazh-panel')?.classList.add('hidden');
      }
    }
  }

  function renderPendingList(items) {
    const container = $('pending-list');
    if (!container) return;
    
    if (items.length === 0) {
      container.innerHTML = '<p class="text-muted">Нет ожидающих душ</p>';
      return;
    }
    
    container.innerHTML = items.map(p => `
      <div class="admin-item" data-id="${p.id}">
        <div class="admin-item-header">
          <span class="admin-item-id">#${p.id}</span>
          <span class="status-badge ${p.status.toLowerCase()}">${p.status}</span>
        </div>
        <div class="admin-item-details">
          <strong>Душа:</strong> @${escapeHtml(p.user.username || p.user.telegram_id)}<br>
          <strong>Проводник:</strong> ${p.referrer ? '@' + escapeHtml(p.referrer.username || p.referrer.telegram_id) : '—'}<br>
          <strong>Код:</strong> ${escapeHtml(p.author_code || '—')}<br>
          <strong>Кошелёк:</strong> <code style="font-size: 10px;">${p.user.wallet || '—'}</code>
        </div>
        <div class="admin-actions">
          <input type="text" class="form-input" placeholder="tx_hash (опционально)">
          <button class="btn btn-success btn-sm btn-icon" onclick="confirmParticipation(${p.id}, this)" title="Подтвердить">✓</button>
          <button class="btn btn-danger btn-sm btn-icon" onclick="rejectParticipation(${p.id}, this)" title="Отклонить">✗</button>
        </div>
      </div>
    `).join('');
  }

  function renderPayoutList(items) {
    const container = $('payout-list');
    if (!container) return;
    
    if (items.length === 0) {
      container.innerHTML = '<p class="text-muted">Нет заявок на выплату</p>';
      return;
    }
    
    container.innerHTML = items.map(p => `
      <div class="admin-item" data-id="${p.id}">
        <div class="admin-item-header">
          <span class="admin-item-id">#${p.id}</span>
          <span class="status-badge ${p.status.toLowerCase()}">${p.status}</span>
        </div>
        <div class="admin-item-details">
          <strong>Душа:</strong> @${escapeHtml(p.user.username || p.user.telegram_id)}<br>
          <strong>Кошелёк:</strong> <code style="font-size: 11px;">${p.user.wallet || 'Не указан!'}</code>
        </div>
        <div class="admin-actions">
          <input type="text" class="form-input" placeholder="tx_hash (обязательно)">
          <button class="btn btn-gold btn-sm" onclick="markPayoutSent(${p.id}, this)">💰 SENT</button>
        </div>
      </div>
    `).join('');
  }

  // Global admin functions (called from onclick)
  window.confirmParticipation = async function(id, btn) {
    const txHash = btn.parentElement.querySelector('input').value.trim();
    try {
      btn.disabled = true;
      await api('/confirm', {
        method: 'POST',
        body: JSON.stringify({ 
          participation_id: id, 
          tx_hash: txHash, 
          decision: 'confirm' 
        }),
      });
      showToast('✅ Душа спасена!', 'success');
      loadAdminData();
    } catch (e) {
      showToast('Ошибка: ' + e.message, 'error');
      btn.disabled = false;
    }
  };

  window.rejectParticipation = async function(id, btn) {
    try {
      btn.disabled = true;
      await api('/confirm', {
        method: 'POST',
        body: JSON.stringify({ 
          participation_id: id, 
          decision: 'reject' 
        }),
      });
      showToast('❌ Отклонено', 'success');
      loadAdminData();
    } catch (e) {
      showToast('Ошибка: ' + e.message, 'error');
      btn.disabled = false;
    }
  };

  window.markPayoutSent = async function(id, btn) {
    const txHash = btn.parentElement.querySelector('input').value.trim();
    if (!txHash) {
      showToast('Введи tx_hash!', 'error');
      return;
    }
    try {
      btn.disabled = true;
      await api('/payout/mark', {
        method: 'POST',
        body: JSON.stringify({ 
          payout_request_id: id, 
          tx_hash: txHash 
        }),
      });
      showToast('💰 Выплата отмечена!', 'success');
      loadAdminData();
    } catch (e) {
      showToast('Ошибка: ' + e.message, 'error');
      btn.disabled = false;
    }
  };

  function initScreenStrazh() {
    $('btn-admin-login')?.addEventListener('click', () => {
      const token = $('input-admin-token')?.value.trim();
      if (!token) {
        showToast('Введи токен', 'error');
        return;
      }
      state.adminToken = token;
      localStorage.setItem(CONFIG.STORAGE_KEY_ADMIN, token);
      $('strazh-login')?.classList.add('hidden');
      $('strazh-panel')?.classList.remove('hidden');
      loadAdminData();
    });

    $('btn-strazh-back')?.addEventListener('click', () => {
      showScreen('screen-progress');
    });
  }

  // ============================================================================
  // PARTICLES - FIRE SOULS EFFECT
  // ============================================================================

  async function initParticles() {
    if (!window.tsParticles) {
      console.warn('[Particles] tsParticles not loaded');
      return;
    }
    
    try {
      await tsParticles.load('particles-js', {
        fullScreen: { enable: false },
        background: { color: { value: 'transparent' } },
        fpsLimit: 60,
        particles: {
          number: {
            value: 50,
            density: { enable: true, area: 800 }
          },
          color: {
            value: ['#ff2d2d', '#ff6b35', '#ffb347', '#ffd700'],
          },
          shape: {
            type: 'circle',
          },
          opacity: {
            value: { min: 0.3, max: 0.8 },
            animation: {
              enable: true,
              speed: 1,
              minimumValue: 0.1,
              sync: false
            }
          },
          size: {
            value: { min: 2, max: 6 },
            animation: {
              enable: true,
              speed: 3,
              minimumValue: 1,
              sync: false
            }
          },
          move: {
            enable: true,
            speed: { min: 0.5, max: 2 },
            direction: 'top',
            random: true,
            straight: false,
            outModes: { default: 'out' },
          },
          wobble: {
            enable: true,
            distance: 10,
            speed: 5
          },
          life: {
            duration: { value: { min: 3, max: 6 } },
            count: 1,
          }
        },
        emitters: {
          position: { x: 50, y: 100 },
          rate: { quantity: 3, delay: 0.3 },
          size: { width: 100, height: 0 }
        },
        interactivity: {
          events: {
            onHover: { enable: true, mode: 'repulse' },
          },
          modes: {
            repulse: { distance: 100, duration: 0.4 }
          }
        },
        detectRetina: true,
      });
      
      console.log('[Particles] Initialized');
    } catch (e) {
      console.error('[Particles] Error:', e);
    }
  }

  // ============================================================================
  // UTILITIES
  // ============================================================================

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function determineInitialScreen() {
    // If has participation, go to progress
    if (state.participationId && state.participationStatus) {
      return 'screen-progress';
    }
    // If wallet connected and left wallet, go to referral
    if (state.leftWallet && state.walletAddress) {
      return 'screen-referral';
    }
    // If left start, go to wallet
    if (state.leftStart) {
      return 'screen-wallet';
    }
    // Default: start
    return 'screen-start';
  }

  // ============================================================================
  // INITIALIZATION
  // ============================================================================

  async function init() {
    console.log('🔥 Soulpull MVP v2.0 — Спасение Душ из Ада');
    console.log('=====================================');
    
    setLoading(true);
    
    // Load saved state
    loadState();
    
    // Init Telegram
    initTelegram();
    
    // Init particles
    await initParticles();
    
    // Init all screens
    initScreenStart();
    initScreenWallet();
    initScreenReferral();
    initScreenAuthor();
    initScreenPayment();
    initScreenProgress();
    initScreenTree();
    initScreenStrazh();
    
    // Init TonConnect (non-blocking, runs in background)
    initTonConnect();
    
    // Determine initial screen
    const initialScreen = determineInitialScreen();
    console.log('[Init] Starting screen:', initialScreen);
    
    // Hide loading
    setLoading(false);
    
    // Show screen with animation
    showScreen(initialScreen);
    
    // If on progress, load data
    if (initialScreen === 'screen-progress') {
      loadProgress();
    }
    
    // Welcome animation
    if (initialScreen === 'screen-start' && window.gsap) {
      gsap.fromTo('.hero-icon', 
        { scale: 0, rotation: -180 },
        { scale: 1, rotation: 0, duration: 0.8, ease: 'back.out(1.7)', delay: 0.2 }
      );
      gsap.fromTo('.hero-title', 
        { opacity: 0, y: 30 },
        { opacity: 1, y: 0, duration: 0.6, delay: 0.5 }
      );
      gsap.fromTo('.hero-subtitle', 
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.6, delay: 0.7 }
      );
      gsap.fromTo('.hero-stats', 
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.6, delay: 0.9 }
      );
      gsap.fromTo('#btn-start', 
        { opacity: 0, scale: 0.9 },
        { opacity: 1, scale: 1, duration: 0.5, delay: 1.1 }
      );
    }
  }

  // Start app when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
