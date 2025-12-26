# Soulpull (minimal Django 4.2 backend)

Минимальный “100% работает” Django 4.2 скелет под прод (gunicorn за nginx / cloudflare).

## Endpoints

- **GET /** → HTML из `templates/index.html` (“Soulpull: server ok”)
- **GET /tonconnect-manifest.json** → JSON из файла `tonconnect-manifest.json` (читается с диска)
- **GET /api/v1/health** → `200` JSON: `{status:"ok", host, debug, time}`
- **POST /api/v1/register-wallet** → JSON `{wallet_address}` → create/update в SQLite (wallet уникальный)
- **GET /api/v1/me?wallet_address=...** → JSON пользователя
- **GET /api/v1/ton-proof/payload** → выдать nonce (payload) для TonConnect `ton_proof` (кладётся в session)
- **POST /api/v1/ton-proof/verify** → проверить `ton_proof` и создать server-side session (`ton_address`, `ton_public_key`)

Все API endpoints помечены `@csrf_exempt`, чтобы POST работал без CSRF на старте.

## Локальный запуск

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env

python manage.py makemigrations
python manage.py migrate

python manage.py runserver 0.0.0.0:8000
```

## Frontend (React + TON Connect UI)

Фронтенд лежит в `frontend/` (Vite + React + `@tonconnect/ui-react`).

### Dev (2 терминала)

Терминал 1 (Django):

```bash
python manage.py runserver 0.0.0.0:8000
```

Терминал 2 (Vite):

```bash
cd frontend
npm install
npm run dev
```

Открывай `http://127.0.0.1:5173` — Vite проксирует `/api/*` и `/tonconnect-manifest.json` на Django.

### Prod-like (сборка и раздача через Django)

```bash
cd frontend
npm install
npm run build
```

После сборки Django начнёт отдавать React на `GET /` (через Vite manifest + `/static/*`).

### TON Proof domain

По умолчанию домен для `ton_proof` берётся из `request.get_host()` (без порта).
Для прод-окружения можно зафиксировать домен:

```bash
export TON_PROOF_DOMAIN=refnet.click
export TON_PROOF_TTL_SECONDS=600
```

## Проверка (curl)

### Локально

```bash
curl -i http://127.0.0.1:8000/
curl -i http://127.0.0.1:8000/tonconnect-manifest.json
curl -i http://127.0.0.1:8000/api/v1/health

curl -i -X POST http://127.0.0.1:8000/api/v1/register-wallet \
  -H "Content-Type: application/json" \
  -d '{"wallet_address":"EQC_TEST_WALLET"}'

curl -i "http://127.0.0.1:8000/api/v1/me?wallet_address=EQC_TEST_WALLET"
```

### По домену

```bash
curl -i https://refnet.click/
curl -i https://refnet.click/tonconnect-manifest.json
curl -i https://refnet.click/api/v1/health

curl -i -X POST https://refnet.click/api/v1/register-wallet \
  -H "Content-Type: application/json" \
  -d '{"wallet_address":"EQC_TEST_WALLET"}'

curl -i "https://refnet.click/api/v1/me?wallet_address=EQC_TEST_WALLET"
```

## Прод (gunicorn)

Пример:

```bash
gunicorn backend.wsgi:application --bind 127.0.0.1:8000 --workers 2 --timeout 30
```

Nginx/Cloudflare должны прокидывать `X-Forwarded-Proto: https` — в `backend/settings.py` включено:
`SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO','https')` и `USE_X_FORWARDED_HOST = True`.


