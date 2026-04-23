import os
import libsql_experimental as sqlite3

def get_connection():
    db_url = os.environ.get("libsql://noottertime-db-pawit-billamas.aws-us-east-1.turso.io", "database.db")
    auth_token = os.environ.get("eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3NzY5MzQwODIsImlkIjoiMDE5ZGI5ODUtNDEwMS03OGNlLWE1ZGYtZDRjOTA4NWRkMGUzIiwicmlkIjoiY2VmNjRjZmQtYTZjMS00NzYzLWFhOGQtMTc2ZTk0YmExNjQ1In0.omgpXcoIhItJ3UYWCQ4-QByaCwY6S-00ZYSMenOGBW_Yh7N9cebydeu-l4T6nJV3-VXeF7rXhbLX0fpW1hZsBQ", "")
    if db_url.startswith("libsql://") or db_url.startswith("https://"):
        return sqlite3.connect(db_url, auth_token=auth_token)
    else:
        return sqlite3.connect(db_url)

def init_db():
    conn = get_connection()
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

    #5. Schedules stuff
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schedules (
        schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        title TEXT,
        date TEXT NOT NULL,
        start_time TEXT,
        end_time TEXT
    )
    """)

    conn.commit()
    conn.close()
    print("Database create with all tables")