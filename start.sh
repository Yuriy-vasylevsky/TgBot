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

# ========== ДІАГНОСТИКА VOLUME ==========
mkdir -p /data
echo "📁 Volume /data contents BEFORE start:"
ls -la /data

DB_PATH="/data/users.db"
echo "💾 Database path: $DB_PATH"

if [ -f "$DB_PATH" ]; then
    echo "✅ DB file exists! Size: $(du -sh "$DB_PATH" | cut -f1)"
else
    echo "📦 Creating NEW users.db..."
    touch "$DB_PATH"
fi

# Права (дуже важливо!)
chmod 777 /data 2>/dev/null || true
chmod 666 "$DB_PATH" 2>/dev/null || true
echo "🔐 Permissions set to 666/777"

echo "📁 Volume /data contents AFTER chmod:"
ls -la /data
# =======================================

python3 main.py