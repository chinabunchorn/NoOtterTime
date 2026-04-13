import sqlite3

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        gender TEXT,
        age INTEGER,
        field_of_interest TEXT,
        study_goal TEXT,
        created_at DATETIME
    )
    """)

    conn.commit()
    conn.close()