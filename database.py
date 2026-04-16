import sqlite3

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # 1. Users Table
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

    # 2. Courses Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        course_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        course_name TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """)

    # 3. Study Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS study_sessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        course_id INTEGER,
        start_time DATETIME,
        end_time DATETIME,
        goal_minutes REAL,
        actual_minutes REAL,
        task_type TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (course_id) REFERENCES courses (course_id)
    )
    """)

    # 4. Mood Evaluations Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mood_evaluations (
        evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        exhaustion_score INTEGER,
        cynicism_score INTEGER,
        efficacy_score INTEGER,
        evaluated_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """)

    conn.commit()
    conn.close()
    print("Database create with all tables")