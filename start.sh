#!/bin/bash
echo "🚀 Starting Telegram Bot on Railway..."

# Активуємо віртуальне середовище Railway
if [ -f "/app/.venv/bin/activate" ]; then
    source /app/.venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️ Virtual environment not found, creating new one..."
    python3 -m venv /app/.venv
    source /app/.venv/bin/activate
    pip install -r requirements.txt
fi

# Перевіримо чи існує база
if [ ! -f "users.db" ]; then
  echo "📦 Creating users.db..."
  touch users.db
fi

# Запуск бота
python3 main.py
