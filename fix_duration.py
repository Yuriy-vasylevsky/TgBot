import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "users.db"

def add_duration_column():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Перевіримо, чи є колонка вже
    cursor.execute("PRAGMA table_info(weekly_tasks)")
    columns = [col[1] for col in cursor.fetchall()]

    if "duration" in columns:
        print("✅ Колонка 'duration' уже існує.")
    else:
        try:
            cursor.execute("ALTER TABLE weekly_tasks ADD COLUMN duration TEXT")
            conn.commit()
            print("✅ Колонка 'duration' успішно додана!")
        except Exception as e:
            print("⚠️ Помилка при додаванні колонки:", e)

    conn.close()

if __name__ == "__main__":
    add_duration_column()
