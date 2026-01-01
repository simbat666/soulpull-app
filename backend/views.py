import json
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone


def index(request):
    # In some production deploy setups templates may be missing from the final artifact,
    # which would crash the whole homepage with 500. Keep "/" resilient: if template
    # rendering fails, fall back to an inline HTML that boots the same static app.
    try:
        return render(request, "index.html")
    except Exception:
        html = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Soulpull</title>
    <link rel="stylesheet" href="/static/app.css?v=ui-20260101-2" />
  </head>
  <body class="app" data-screen="connect">
    <div class="bg">
      <div class="bg__blob bg__blob--1"></div>
      <div class="bg__blob bg__blob--2"></div>
      <div class="bg__grid"></div>
    </div>

    <header class="topbar">
      <div class="topbar__left">
        <div class="logo">
          <span class="logo__mark">S</span>
          <span class="logo__text">Soulpull</span>
        </div>
        <div class="badge">MVP</div>
        <div class="tg-user hidden" id="tg-user">
          <img class="tg-user__avatar" id="tg-user-avatar" alt="Telegram avatar" />
          <div class="tg-user__meta">
            <div class="tg-user__name" id="tg-user-name"></div>
            <div class="tg-user__username" id="tg-user-username"></div>
          </div>
        </div>
      </div>
      <div class="topbar__right">
        <div class="tonconnect-slot" id="tonconnect"></div>
      </div>
    </header>

    <main class="container">
      <div id="tg-warning" class="notice hidden">
        Откройте через Telegram WebApp, чтобы привязать Telegram.
      </div>

      <div class="steps">
        <div class="steps__item" data-step="connect">
          <div class="steps__dot"></div>
          <div class="steps__label">Connect</div>
        </div>
        <div class="steps__line"></div>
        <div class="steps__item" data-step="onboarding">
          <div class="steps__dot"></div>
          <div class="steps__label">Onboarding</div>
        </div>
        <div class="steps__line"></div>
        <div class="steps__item" data-step="cabinet">
          <div class="steps__dot"></div>
          <div class="steps__label">Cabinet</div>
        </div>
      </div>

      <div class="layout">
        <section class="panel panel--main">
          <section id="screen-connect" class="screen">
            <div class="hero">
              <h1 class="hero__title">Подключите кошелёк</h1>
              <p class="hero__sub">
                Кошелёк = аккаунт. Мы делаем авторизацию через <span class="kbd">TON Proof</span>.
              </p>
              <div class="hero__hint">
                Нажмите кнопку TonConnect в правом верхнем углу и выберите кошелёк.
              </div>
            </div>
          </section>

          <section id="screen-onboarding" class="screen hidden">
            <div class="hero hero--compact">
              <h1 class="hero__title">Онбординг</h1>
              <p class="hero__sub">Заполните данные и оплатите билет, чтобы активировать участие.</p>
            </div>

            <div class="cards">
              <div class="card card--glass">
                <div class="card__head">
                  <div class="card__title">Сессия</div>
                  <div class="pill" id="status">init</div>
                </div>
                <div class="kv">
                  <div class="kv__row">
                    <div class="kv__k">Wallet</div>
                    <div class="kv__v mono" id="wallet-address"></div>
                  </div>
                  <div class="kv__row">
                    <div class="kv__k">Telegram</div>
                    <div class="kv__v" id="telegram-info">—</div>
                  </div>
                  <div class="kv__row">
                    <div class="kv__k">Inviter</div>
                    <div class="kv__v" id="inviter-info">—</div>
                  </div>
                  <div class="kv__row">
                    <div class="kv__k">Author code</div>
                    <div class="kv__v" id="author-code-info">—</div>
                  </div>
                </div>
              </div>

              <div class="card">
                <div class="card__head">
                  <div class="card__title">Telegram WebApp</div>
                  <div class="card__desc">Привязка профиля Telegram к кошельку.</div>
                </div>
                <button id="btn-telegram-verify" class="btn btn-indigo">Привязать Telegram</button>
              </div>

              <div class="card">
                <div class="card__head">
                  <div class="card__title">Кто пригласил</div>
                  <div class="card__desc">telegram_id / wallet / @username (MVP).</div>
                </div>
                <div class="field">
                  <input id="inviter-input" class="input" placeholder="Например: 123456789" />
                  <button id="btn-inviter-apply" class="btn">Сохранить</button>
                </div>
              </div>

              <div class="card">
                <div class="card__head">
                  <div class="card__title">Код автора</div>
                  <div class="card__desc">Можно применить один раз.</div>
                </div>
                <div class="field">
                  <input id="author-code-input" class="input" placeholder="Например: INDIGO15" />
                  <button id="btn-author-code-apply" class="btn">Применить</button>
                </div>
              </div>

              <div class="card card--accent">
                <div class="card__head">
                  <div class="card__title">Билет</div>
                  <div class="card__desc">MVP: создаём intent, отправляем, подтверждаем tx hash.</div>
                </div>
                <div class="stack">
                  <button id="btn-pay-create" class="btn btn-indigo btn-lg">Оплатить билет</button>
                  <div id="payment-info" class="muted"></div>
                  <button id="btn-pay-send" class="btn mt hidden">Отправить через кошелёк</button>
                  <div class="field mt">
                    <input id="tx-hash-input" class="input" placeholder="Tx hash (для MVP)" />
                    <button id="btn-pay-confirm" class="btn">Подтвердить</button>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section id="screen-cabinet" class="screen hidden">
            <div class="hero hero--compact">
              <h1 class="hero__title">Кабинет</h1>
              <p class="hero__sub">Ваш профиль и статус участия.</p>
            </div>

            <div class="card card--glass">
              <div class="kv">
                <div class="kv__row"><div class="kv__k">Wallet</div><div class="kv__v mono" id="cab-wallet">—</div></div>
                <div class="kv__row"><div class="kv__k">Telegram</div><div class="kv__v" id="cab-telegram">—</div></div>
                <div class="kv__row"><div class="kv__k">Inviter</div><div class="kv__v" id="cab-inviter">—</div></div>
                <div class="kv__row"><div class="kv__k">Author code</div><div class="kv__v" id="cab-author-code">—</div></div>
                <div class="kv__row"><div class="kv__k">Status</div><div class="kv__v" id="cab-status">—</div></div>
                <div class="kv__row"><div class="kv__k">Stats</div><div class="kv__v" id="cab-stats">—</div></div>
              </div>
            </div>
          </section>
        </section>

        <aside class="panel panel--side">
          <div class="card card--glass">
            <div class="card__head">
              <div class="card__title">Подсказки</div>
              <div class="card__desc">Что делать дальше</div>
            </div>
            <ul class="tips">
              <li><b>Connect</b>: подключите кошелёк через TonConnect.</li>
              <li><b>Login</b>: подтвердите TON Proof (всё происходит автоматически).</li>
              <li><b>Onboarding</b>: привяжите Telegram, inviter и код автора.</li>
              <li><b>Ticket</b>: создайте платёж и подтвердите tx hash.</li>
            </ul>
          </div>

          <div class="card">
            <div class="card__head">
              <div class="card__title">Статус</div>
              <div class="card__desc">Живые обновления</div>
            </div>
            <div class="toast" id="toast">init</div>
          </div>
        </aside>
      </div>
    </main>
    <script src="https://unpkg.com/@tonconnect/ui@2.0.0/dist/tonconnect-ui.min.js"></script>
    <script src="/static/js/app.js?v=app-20260101-2"></script>
  </body>
</html>
"""
        return HttpResponse(html, content_type="text/html; charset=utf-8")


def tonconnect_manifest(request):
    """
    Serve JSON from root `tonconnect-manifest.json` (NOT via static).
    """
    manifest_path: Path = settings.BASE_DIR / "tonconnect-manifest.json"  # type: ignore[attr-defined]
    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return JsonResponse(data)
    except FileNotFoundError:
        return JsonResponse({"error": "manifest not found"}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({"error": "manifest invalid json"}, status=500)


def _now_iso():
    return timezone.now().isoformat()


