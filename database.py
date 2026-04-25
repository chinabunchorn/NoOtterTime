import psycopg2
import os

def get_db_connection():
    """
    Establishes a PostgreSQL connection from DATABASE_URL environment variable.
    Falls back to default parameters if DATABASE_URL is not set.
    psycopg2 handles the full URL directly, including any SSL requirements.
    """
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # psycopg2 can read the full URL directly, automatically handling ?sslmode=require
        conn = psycopg2.connect(database_url)
    else:
        # Default local connection for development
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='nootter_time',
            user='postgres',
            password='postgres'
        )
    
    return conn


def init_db():
    """Initialize PostgreSQL database with required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        gender TEXT,
        age INTEGER,
        field_of_interest TEXT,
        study_goal TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. Courses Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        course_id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        course_name TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    )
    """)

    # 3. Study Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS study_sessions (
        session_id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP NOT NULL,
        goal_minutes NUMERIC NOT NULL,
        actual_minutes NUMERIC NOT NULL,
        task_type TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
        FOREIGN KEY (course_id) REFERENCES courses (course_id) ON DELETE CASCADE
    )
    """)

    # 4. Mood Evaluations Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mood_evaluations (
        evaluation_id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        exhaustion_score INTEGER NOT NULL,
        cynicism_score INTEGER NOT NULL,
        efficacy_score INTEGER NOT NULL,
        evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    )
    """)

    # 5. Schedules Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schedules (
        schedule_id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        title TEXT,
        date TEXT NOT NULL,
        start_time TEXT,
        end_time TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
        FOREIGN KEY (course_id) REFERENCES courses (course_id) ON DELETE CASCADE
    )
    """)

    conn.commit()
    conn.close()
    print("Database initialized with all tables")