import sqlite3

db_path = "users.db"

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 1. Додаємо колонку без значення за замовчуванням
try:
    cur.execute("ALTER TABLE users ADD COLUMN last_active DATETIME;")
    print("✅ Колонку last_active додано.")
except sqlite3.OperationalError as e:
    print(f"⚠️ {e}")

# 2. Оновлюємо всі записи, щоб не були NULL
cur.execute("UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE last_active IS NULL;")
conn.commit()
conn.close()

print("✅ Поле last_active заповнено поточним часом.")
