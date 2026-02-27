#!/bin/bash
echo "🚀 Starting Telegram Bot on Railway..."

# venv
if [ -f "/app/.venv/bin/activate" ]; then
    source /app/.venv/bin/activate
    echo "✅ Venv activated"
else
    echo "⚠️ Creating venv..."
    python3 -m venv /app/.venv
    source /app/.venv/bin/activate
    pip install -r requirements.txt
fi

mkdir -p /data
chmod 777 /data

DB_PATH="/data/users.db"

# 🔥 Авто-виправлення порожньої бази
if [ -f "$DB_PATH" ] && [ ! -s "$DB_PATH" ]; then
    echo "🗑️ DB file is empty (0 bytes) — deleting to recreate with tables"
    rm -f "$DB_PATH"
fi

if [ ! -f "$DB_PATH" ]; then
    echo "📦 Creating NEW users.db..."
    touch "$DB_PATH"
fi

echo "💾 Database: $DB_PATH (size: $(du -sh "$DB_PATH" 2>/dev/null || echo '0B'))"
chmod 666 "$DB_PATH"

# Діагностика
echo "📁 /data contents:"
ls -la /data

python3 main.py