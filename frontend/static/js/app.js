/**
 * Soulpull MVP — Frontend Application (согласно ТЗ §8)
 * 
 * Экраны: E1 Start → E2 Wallet → E3 Referral → E4 Author → E5 Payment → E6 Progress
 * Forward-only: после E1/E2 возврат запрещён
 */

(function() {
  'use strict';

  // ============================================================================
  // STATE
  // ============================================================================
  
  const state = {
    // Forward-only flags
    leftStart: false,
    leftWallet: false,
    
    // User data (from Telegram WebApp or session)
    telegramId: null,
    username: null,
    
    // Wallet
    walletAddress: null,
    
    // Form inputs
    referrerTelegramId: null,
    authorCode: null,
    
    // Participation
    participationId: null,
    participationStatus: null,
    
    // Payment
    paymentIntent: null,
    
    // Admin
    adminToken: null,
  };

  // ============================================================================
  // CONSTANTS
  // ============================================================================

  const API_BASE = '/api/v1';
  const STORAGE_KEY_ADMIN = 'soulpull_admin_token';
  const STORAGE_KEY_STATE = 'soulpull_state';

  // ============================================================================
  // UTILS
  // ============================================================================

  function $(id) {
    return document.getElementById(id);
  }

  function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    const screen = $(screenId);
    if (screen) screen.classList.add('active');
  }

  function showToast(message, type = 'info') {
    const toast = $('toast');
    toast.textContent = message;
    toast.className = 'toast show ' + type;
    setTimeout(() => toast.classList.remove('show'), 3000);
  }

  function showBanner(elementId, message, show = true) {
    const el = $(elementId);
    if (!el) return;
    if (show) {
      el.textContent = message;
      el.classList.remove('hidden');
    } else {
      el.classList.add('hidden');
    }
  }

  async function api(endpoint, options = {}) {
    const url = API_BASE + endpoint;
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    
    if (state.adminToken) {
      headers['X-Admin-Token'] = state.adminToken;
    }
    
    try {
      const resp = await fetch(url, { ...options, headers });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || data.message || `HTTP ${resp.status}`);
      }
      return data;
    } catch (e) {
      console.error('API error:', e);
      throw e;
    }
  }

  function saveState() {
    try {
      const toSave = {
        telegramId: state.telegramId,
        username: state.username,
        walletAddress: state.walletAddress,
        referrerTelegramId: state.referrerTelegramId,
        authorCode: state.authorCode,
        participationId: state.participationId,
        leftStart: state.leftStart,
        leftWallet: state.leftWallet,
      };
      sessionStorage.setItem(STORAGE_KEY_STATE, JSON.stringify(toSave));
    } catch (e) {}
  }

  function loadState() {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY_STATE);
      if (saved) {
        const parsed = JSON.parse(saved);
        Object.assign(state, parsed);
      }
      const adminToken = localStorage.getItem(STORAGE_KEY_ADMIN);
      if (adminToken) state.adminToken = adminToken;
    } catch (e) {}
  }

  // ============================================================================
  // TELEGRAM WEBAPP
  // ============================================================================

  function initTelegram() {
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      
      const user = tg.initDataUnsafe?.user;
      if (user) {
        state.telegramId = user.id;
        state.username = user.username || user.first_name;
        console.log('Telegram user:', state.telegramId, state.username);
      }
      
      // Check start_param for referrer
      const startParam = tg.initDataUnsafe?.start_param;
      if (startParam && /^\d+$/.test(startParam)) {
        state.referrerTelegramId = startParam;
        $('input-referrer').value = startParam;
      }
      
      $('banner-not-telegram')?.classList.add('hidden');
    } else {
      // Not in Telegram - show warning
      $('banner-not-telegram')?.classList.remove('hidden');
      
      // Dev mode: allow manual telegram_id input
      const devTid = prompt('Dev mode: Enter telegram_id', '123456789');
      if (devTid && /^\d+$/.test(devTid)) {
        state.telegramId = parseInt(devTid);
        state.username = 'dev_user';
      }
    }
  }

  // ============================================================================
  // TONCONNECT
  // ============================================================================

  let tonConnectUI = null;

  async function initTonConnect() {
    try {
      const manifestUrl = window.location.origin + '/tonconnect-manifest.json?v=' + Date.now();
      
      tonConnectUI = new TON_CONNECT_UI.TonConnectUI({
        manifestUrl,
        buttonRootId: 'ton-connect-button',
      });

      tonConnectUI.onStatusChange(wallet => {
        if (wallet) {
          state.walletAddress = wallet.account.address;
          $('wallet-status')?.classList.remove('hidden');
          $('btn-wallet-next').disabled = false;
          console.log('Wallet connected:', state.walletAddress);
          
          // Link wallet to user
          if (state.telegramId) {
            registerAndLinkWallet();
          }
        } else {
          state.walletAddress = null;
          $('wallet-status')?.classList.add('hidden');
          $('btn-wallet-next').disabled = true;
        }
      });

      // Restore connection
      const connected = await tonConnectUI.connectionRestored;
      if (connected && tonConnectUI.wallet) {
        state.walletAddress = tonConnectUI.wallet.account.address;
        $('wallet-status')?.classList.remove('hidden');
        $('btn-wallet-next').disabled = false;
      }

    } catch (e) {
      console.error('TonConnect init error:', e);
      showToast('Ошибка подключения TonConnect', 'error');
    }
  }

  async function registerAndLinkWallet() {
    if (!state.telegramId || !state.walletAddress) return;
    
    try {
      // Register user
      await api('/register', {
        method: 'POST',
        body: JSON.stringify({
          telegram_id: state.telegramId,
          username: state.username,
        }),
      });
      
      // Link wallet
      await api('/wallet', {
        method: 'POST',
        body: JSON.stringify({
          telegram_id: state.telegramId,
          wallet: state.walletAddress,
        }),
      });
      
      console.log('User registered and wallet linked');
    } catch (e) {
      console.error('Register/link error:', e);
      // Non-fatal, continue
    }
  }

  // ============================================================================
  // SCREENS
  // ============================================================================

  // E1: Start
  function initScreenStart() {
    $('btn-start')?.addEventListener('click', () => {
      state.leftStart = true;
      saveState();
      showScreen('screen-wallet');
    });
  }

  // E2: Wallet
  function initScreenWallet() {
    $('btn-wallet-next')?.addEventListener('click', () => {
      if (!state.walletAddress) {
        showToast('Сначала подключите кошелёк', 'error');
        return;
      }
      state.leftWallet = true;
      saveState();
      showScreen('screen-referral');
    });
  }

  // E3: Referral
  function initScreenReferral() {
    $('btn-referral-back')?.addEventListener('click', () => {
      // Forward-only: can only go back if !leftWallet
      if (state.leftWallet) {
        showToast('Возврат невозможен', 'error');
        return;
      }
      showScreen('screen-wallet');
    });

    $('btn-referral-next')?.addEventListener('click', () => {
      const input = $('input-referrer');
      const value = (input?.value || '').trim();
      
      if (!value) {
        showToast('Введите telegram_id пригласившего', 'error');
        return;
      }
      
      if (!/^\d+$/.test(value)) {
        showToast('Только цифры', 'error');
        return;
      }
      
      if (value === String(state.telegramId)) {
        showToast('Нельзя пригласить себя', 'error');
        return;
      }
      
      state.referrerTelegramId = value;
      saveState();
      showScreen('screen-author');
    });
  }

  // E4: Author Code
  function initScreenAuthor() {
    $('btn-author-back')?.addEventListener('click', () => {
      showScreen('screen-referral');
    });

    $('btn-author-next')?.addEventListener('click', () => {
      const input = $('input-author-code');
      state.authorCode = (input?.value || '').trim() || null;
      saveState();
      showScreen('screen-payment');
    });
  }

  // E5: Payment
  function initScreenPayment() {
    $('btn-payment-back')?.addEventListener('click', () => {
      showScreen('screen-author');
    });

    $('btn-pay')?.addEventListener('click', async () => {
      try {
        showBanner('payment-error', '', false);
        $('btn-pay').disabled = true;
        $('btn-pay').textContent = 'Создаём платёж...';
        
        // Create intent
        const result = await api('/intent', {
          method: 'POST',
          body: JSON.stringify({
            telegram_id: state.telegramId,
            referrer_telegram_id: state.referrerTelegramId ? parseInt(state.referrerTelegramId) : null,
            author_code: state.authorCode,
          }),
        });
        
        state.participationId = result.participation.id;
        state.participationStatus = result.participation.status;
        saveState();
        
        // For MVP: show mock payment details
        $('payment-receiver').textContent = 'UQA...receiver';
        $('payment-comment').textContent = `Soulpull #${state.participationId}`;
        $('payment-details')?.classList.remove('hidden');
        $('btn-pay-send')?.classList.remove('hidden');
        $('btn-payment-next').disabled = false;
        
        showToast('Платёж создан!', 'success');
        
      } catch (e) {
        const errorMap = {
          'active_cycle': 'У вас уже есть активное участие',
          'referrer_limit': 'У пригласившего нет свободных слотов (3/3)',
          'referrer_not_found': 'Пригласивший не найден',
          'referrer_not_confirmed': 'Пригласивший ещё не оплатил',
          'self_referral': 'Нельзя пригласить себя',
        };
        const msg = errorMap[e.message] || e.message;
        showBanner('payment-error', '❌ ' + msg, true);
        $('btn-pay').disabled = false;
        $('btn-pay').textContent = '💳 Оплатить 15 USDT';
      }
    });

    $('btn-pay-send')?.addEventListener('click', async () => {
      if (!tonConnectUI) {
        showToast('TonConnect не инициализирован', 'error');
        return;
      }
      
      try {
        // TODO: Real JettonTransfer transaction
        // For MVP: simulate
        showToast('Транзакция отправлена (MVP симуляция)', 'success');
        $('btn-payment-next').disabled = false;
      } catch (e) {
        showToast('Ошибка отправки: ' + e.message, 'error');
      }
    });

    $('btn-payment-next')?.addEventListener('click', () => {
      showScreen('screen-progress');
      loadProgress();
    });
  }

  // E6: Progress
  async function loadProgress() {
    if (!state.telegramId) return;
    
    try {
      const data = await api(`/me?telegram_id=${state.telegramId}`);
      
      // Update status
      const status = data.participation?.status || 'NEW';
      const statusEl = $('participation-status');
      if (statusEl) {
        statusEl.textContent = status;
        statusEl.className = 'status-badge ' + status.toLowerCase();
      }
      
      // Update L1 count
      const l1Count = data.l1?.filter(r => r.paid).length || 0;
      $('l1-count').textContent = l1Count;
      
      // Update checklist
      const isConfirmed = status === 'CONFIRMED';
      const has3L1 = l1Count >= 3;
      const canPayout = data.eligible_payout;
      
      updateChecklistItem('check-paid', isConfirmed);
      updateChecklistItem('check-l1', has3L1);
      updateChecklistItem('check-payout', canPayout);
      
      // Enable payout button
      $('btn-payout').disabled = !canPayout;
      
    } catch (e) {
      console.error('Load progress error:', e);
    }
  }

  function updateChecklistItem(id, done) {
    const el = $(id);
    if (!el) return;
    el.className = 'checklist-icon ' + (done ? 'done' : 'pending');
    el.textContent = done ? '✓' : '○';
  }

  function initScreenProgress() {
    $('btn-tree')?.addEventListener('click', () => {
      showScreen('screen-tree');
      loadTree();
    });

    $('btn-payout')?.addEventListener('click', async () => {
      try {
        await api('/payout', {
          method: 'POST',
          body: JSON.stringify({ telegram_id: state.telegramId }),
        });
        showToast('Заявка на выплату создана!', 'success');
        $('btn-payout').disabled = true;
        $('btn-payout').textContent = 'Заявка отправлена';
      } catch (e) {
        showToast('Ошибка: ' + e.message, 'error');
      }
    });

    $('btn-strazh')?.addEventListener('click', () => {
      showScreen('screen-strazh');
      if (state.adminToken) {
        $('strazh-login')?.classList.add('hidden');
        $('strazh-panel')?.classList.remove('hidden');
        loadAdminData();
      }
    });

    $('btn-refresh')?.addEventListener('click', () => {
      loadProgress();
      showToast('Обновлено', 'success');
    });
  }

  // E7: Tree
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
      list.innerHTML = data.l1.map(r => `
        <li class="referral-item">
          <div class="referral-info">
            <div class="referral-avatar">${(r.username || '?')[0].toUpperCase()}</div>
            <div>
              <div class="referral-name">${r.username || 'User'}</div>
              <div class="referral-id">ID: ${r.telegram_id}</div>
            </div>
          </div>
          <span class="referral-status ${r.paid ? 'paid' : 'pending'}">
            ${r.paid ? '✓ Оплачено' : '⏳ Ожидает'}
          </span>
        </li>
      `).join('');
      
    } catch (e) {
      console.error('Load tree error:', e);
    }
  }

  function initScreenTree() {
    $('btn-tree-back')?.addEventListener('click', () => {
      showScreen('screen-progress');
    });
  }

  // E8: Strazh (Admin)
  async function loadAdminData() {
    try {
      const [pending, payouts] = await Promise.all([
        api('/admin/participations/pending'),
        api('/admin/payouts/open'),
      ]);
      
      renderPendingList(pending.items || []);
      renderPayoutList(payouts.items || []);
      
    } catch (e) {
      console.error('Load admin data error:', e);
      showToast('Ошибка загрузки: ' + e.message, 'error');
    }
  }

  function renderPendingList(items) {
    const container = $('pending-list');
    if (!container) return;
    
    if (items.length === 0) {
      container.innerHTML = '<p class="text-muted">Нет ожидающих</p>';
      return;
    }
    
    container.innerHTML = items.map(p => `
      <div class="admin-item" data-id="${p.id}">
        <div class="admin-item-header">
          <span class="admin-item-id">#${p.id}</span>
          <span class="status-badge ${p.status.toLowerCase()}">${p.status}</span>
        </div>
        <div class="admin-item-details">
          <strong>User:</strong> @${p.user.username || p.user.telegram_id}<br>
          <strong>Referrer:</strong> ${p.referrer ? '@' + (p.referrer.username || p.referrer.telegram_id) : 'N/A'}<br>
          <strong>Code:</strong> ${p.author_code || 'N/A'}
        </div>
        <div class="admin-actions">
          <input type="text" class="form-input" placeholder="tx_hash" style="flex:1">
          <button class="btn btn-success btn-sm" onclick="confirmParticipation(${p.id}, this)">✓</button>
          <button class="btn btn-danger btn-sm" onclick="rejectParticipation(${p.id}, this)">✗</button>
        </div>
      </div>
    `).join('');
  }

  function renderPayoutList(items) {
    const container = $('payout-list');
    if (!container) return;
    
    if (items.length === 0) {
      container.innerHTML = '<p class="text-muted">Нет заявок</p>';
      return;
    }
    
    container.innerHTML = items.map(p => `
      <div class="admin-item" data-id="${p.id}">
        <div class="admin-item-header">
          <span class="admin-item-id">#${p.id}</span>
          <span class="status-badge ${p.status.toLowerCase()}">${p.status}</span>
        </div>
        <div class="admin-item-details">
          <strong>User:</strong> @${p.user.username || p.user.telegram_id}<br>
          <strong>Wallet:</strong> ${p.user.wallet || 'N/A'}
        </div>
        <div class="admin-actions">
          <input type="text" class="form-input" placeholder="tx_hash" style="flex:1">
          <button class="btn btn-success btn-sm" onclick="markPayoutSent(${p.id}, this)">SENT</button>
        </div>
      </div>
    `).join('');
  }

  // Global admin functions
  window.confirmParticipation = async function(id, btn) {
    const txHash = btn.parentElement.querySelector('input').value.trim();
    try {
      await api('/confirm', {
        method: 'POST',
        body: JSON.stringify({ participation_id: id, tx_hash: txHash, decision: 'confirm' }),
      });
      showToast('Подтверждено!', 'success');
      loadAdminData();
    } catch (e) {
      showToast('Ошибка: ' + e.message, 'error');
    }
  };

  window.rejectParticipation = async function(id, btn) {
    const txHash = btn.parentElement.querySelector('input').value.trim();
    try {
      await api('/confirm', {
        method: 'POST',
        body: JSON.stringify({ participation_id: id, tx_hash: txHash, decision: 'reject' }),
      });
      showToast('Отклонено', 'success');
      loadAdminData();
    } catch (e) {
      showToast('Ошибка: ' + e.message, 'error');
    }
  };

  window.markPayoutSent = async function(id, btn) {
    const txHash = btn.parentElement.querySelector('input').value.trim();
    if (!txHash) {
      showToast('Введите tx_hash', 'error');
      return;
    }
    try {
      await api('/payout/mark', {
        method: 'POST',
        body: JSON.stringify({ payout_request_id: id, tx_hash: txHash }),
      });
      showToast('Отмечено SENT!', 'success');
      loadAdminData();
    } catch (e) {
      showToast('Ошибка: ' + e.message, 'error');
    }
  };

  function initScreenStrazh() {
    $('btn-admin-login')?.addEventListener('click', () => {
      const token = $('input-admin-token')?.value.trim();
      if (!token) {
        showToast('Введите токен', 'error');
        return;
      }
      state.adminToken = token;
      localStorage.setItem(STORAGE_KEY_ADMIN, token);
      $('strazh-login')?.classList.add('hidden');
      $('strazh-panel')?.classList.remove('hidden');
      loadAdminData();
    });

    $('btn-strazh-back')?.addEventListener('click', () => {
      showScreen('screen-progress');
    });
  }

  // ============================================================================
  // INIT
  // ============================================================================

  function determineInitialScreen() {
    // If returning user with participation, go to progress
    if (state.participationId) {
      return 'screen-progress';
    }
    // If wallet connected and left wallet screen, go to referral
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

  async function init() {
    console.log('Soulpull MVP v2.0 init');
    
    // Load saved state
    loadState();
    
    // Init Telegram
    initTelegram();
    
    // Init screens
    initScreenStart();
    initScreenWallet();
    initScreenReferral();
    initScreenAuthor();
    initScreenPayment();
    initScreenProgress();
    initScreenTree();
    initScreenStrazh();
    
    // Init TonConnect
    await initTonConnect();
    
    // Show initial screen
    const initialScreen = determineInitialScreen();
    showScreen(initialScreen);
    
    // If on progress screen, load data
    if (initialScreen === 'screen-progress') {
      loadProgress();
    }
  }

  // Start
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();

