#!/bin/bash
# Скрипт для проверки статуса сервера

echo "🔍 Проверка статуса сервера Soulpull..."
echo ""

# Проверка статуса systemd сервиса
echo "1. Статус systemd сервиса:"
sudo systemctl status soulpull-backend --no-pager -l | head -20
echo ""

# Проверка статуса nginx
echo "2. Статус nginx:"
sudo systemctl status nginx --no-pager -l | head -10
echo ""

# Проверка портов
echo "3. Проверка портов:"
echo "Порт 8000 (Django):"
sudo netstat -tlnp | grep :8000 || echo "  ❌ Порт 8000 не слушается"
echo ""
echo "Порт 80 (HTTP):"
sudo netstat -tlnp | grep :80 || echo "  ❌ Порт 80 не слушается"
echo ""
echo "Порт 443 (HTTPS):"
sudo netstat -tlnp | grep :443 || echo "  ❌ Порт 443 не слушается"
echo ""

# Проверка процессов
echo "4. Процессы Django/Gunicorn:"
ps aux | grep -E "(gunicorn|manage.py)" | grep -v grep || echo "  ❌ Процессы не найдены"
echo ""

# Проверка логов
echo "5. Последние ошибки из логов:"
if [ -f /var/log/soulpull-backend/error.log ]; then
    echo "--- Последние 10 строк error.log ---"
    tail -10 /var/log/soulpull-backend/error.log
else
    echo "  Лог файл не найден"
fi
echo ""

# Проверка доступности локально
echo "6. Проверка локальной доступности:"
curl -I http://localhost:8000 2>&1 | head -5 || echo "  ❌ Локальный сервер не отвечает"
echo ""

echo "✅ Проверка завершена"

