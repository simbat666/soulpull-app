# Soulpull Django Backend

Django-бэкенд для проекта Soulpull с API v1 и интеграцией TON Connect.

## Быстрый старт

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Создайте `.env` файл (скопируйте из `.env.example` и заполните):
```bash
cp .env.example .env
```

3. Выполните миграции:
```bash
python manage.py makemigrations
python manage.py migrate
```

4. Запустите сервер:
```bash
python manage.py runserver
```

5. Откройте в браузере: http://localhost:8000

## TON Connect

На главной странице доступна интеграция с TON Connect. При подключении кошелька происходит автоматическая регистрация пользователя через endpoint `/api/v1/register-wallet`.

## Установка

1. Создайте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
# или
venv\Scripts\activate  # для Windows
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл `.env` на основе `.env.example`:
```bash
# Скопируйте .env.example в .env и заполните значения
cp .env.example .env
```

4. Выполните миграции:
```bash
python manage.py makemigrations
python manage.py migrate
```

5. Создайте суперпользователя (опционально):
```bash
python manage.py createsuperuser
```

6. Запустите сервер разработки:
```bash
python manage.py runserver
```

## Структура проекта

- `backend/` - основной проект Django
- `api/` - приложение с моделями и API endpoints
- `manage.py` - скрипт управления Django

## API Endpoints

Все endpoints доступны по префиксу `/api/v1/`:

### Пользовательские endpoints:

- `POST /api/v1/register` - регистрация пользователя
- `POST /api/v1/wallet` - привязка кошелька
- `POST /api/v1/intent` - создание намерения участия
- `GET /api/v1/me?telegram_id=<id>` - информация о пользователе
- `POST /api/v1/payout` - создание запроса на выплату
- `POST /api/v1/confirm` - подтверждение транзакции
- `GET /api/v1/jetton/wallet?telegram_id=<id>` - адрес jetton кошелька (заглушка)

### Админские endpoints (требуют заголовок `X-Admin-Token`):

- `POST /api/v1/payout/mark` - изменение статуса выплаты

## Модели

- `UserProfile` - профиль пользователя (telegram_id уникальный)
- `AuthorCode` - коды автора для регистрации
- `Participation` - участие пользователя (tx_hash уникальный)
- `PayoutRequest` - запросы на выплату
- `RiskEvent` - события риска

## Переменные окружения

Создайте файл `.env` со следующими переменными:

```
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
SECRET_KEY=your-secret-key-here
X_ADMIN_TOKEN=your-admin-token-here
RECEIVER_WALLET=your-receiver-wallet-address
USDT_JETTON_MASTER=your-usdt-jetton-master-address
TONCENTER_API_KEY=your-toncenter-api-key
```

## Запуск с Gunicorn

Для production используйте Gunicorn:

```bash
gunicorn backend.wsgi:application --bind 0.0.0.0:8000
```



