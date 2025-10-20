# #!/bin/bash
# echo "🚀 Starting Telegram Bot..."

# # Активуємо середовище Railway
# source /app/.venv/bin/activate

# # Перевіримо, чи існує база
# if [ ! -f "users.db" ]; then
#   echo "📦 Створюємо нову базу users.db..."
#   touch users.db
# fi

# # Запуск
# python main.py

web: bash start.sh
