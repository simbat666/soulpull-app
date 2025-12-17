#!/bin/bash
# Скрипт для исправления проблем с сервером

set -e

echo "🔧 Исправление проблем с сервером..."
echo ""

cd /home/soulpull/soulpull-app

# 1. Активируем venv
echo "1. Активируем виртуальное окружение..."
source venv/bin/activate

# 2. Обновляем код
echo "2. Обновляем код из git..."
git pull origin main || echo "  ⚠️  Git pull не выполнен (возможно, нет изменений)"

# 3. Применяем миграции
echo "3. Применяем миграции..."
python manage.py migrate --noinput

# 4. Проверяем конфигурацию
echo "4. Проверяем конфигурацию..."
if [ ! -f .env ]; then
    echo "  ⚠️  Файл .env не найден! Создайте его из .env.example"
fi

# 5. Перезапускаем сервисы
echo "5. Перезапускаем сервисы..."
sudo systemctl restart soulpull-backend
sleep 2
sudo systemctl status soulpull-backend --no-pager | head -10

echo ""
echo "6. Перезагружаем nginx..."
sudo systemctl reload nginx
sudo systemctl status nginx --no-pager | head -5

echo ""
echo "✅ Сервер перезапущен!"
echo ""
echo "Проверьте статус:"
echo "  sudo systemctl status soulpull-backend"
echo "  sudo systemctl status nginx"
echo ""
echo "Проверьте логи:"
echo "  sudo journalctl -u soulpull-backend -n 50"
echo "  sudo tail -f /var/log/nginx/error.log"

