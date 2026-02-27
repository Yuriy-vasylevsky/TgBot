# #!/bin/bash
# echo "🚀 Starting Telegram Bot on Railway..."

# # Активуємо віртуальне середовище Railway
# if [ -f "/app/.venv/bin/activate" ]; then
#     source /app/.venv/bin/activate
#     echo "✅ Virtual environment activated"
# else
#     echo "⚠️ Virtual environment not found, creating new one..."
#     python3 -m venv /app/.venv
#     source /app/.venv/bin/activate
#     pip install -r requirements.txt
# fi

# # Перевіримо чи існує база
# if [ ! -f "users.db" ]; then
#   echo "📦 Creating users.db..."
#   touch users.db
# fi

# # Запуск бота
# python3 main.py
#!/bin/bash
echo "🚀 Starting Telegram Bot on Railway..."

# Активуємо venv
if [ -f "/app/.venv/bin/activate" ]; then
    source /app/.venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️ Creating venv..."
    python3 -m venv /app/.venv
    source /app/.venv/bin/activate
    pip install -r requirements.txt
fi

# Створюємо папку volume (Railway її монтує, але mkdir безпечніше)
mkdir -p /app/data
chmod 777 /app/data

DB_PATH="/app/data/users.db"

if [ ! -f "$DB_PATH" ]; then
  echo "📦 Creating persistent users.db in /app/data..."
  touch "$DB_PATH"
  chmod 666 "$DB_PATH"
fi

echo "💾 Database: $DB_PATH"

# Запуск
python3 main.py