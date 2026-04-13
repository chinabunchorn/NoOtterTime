import sqlite3
import bcrypt
from datetime import datetime, timedelta
from models import init_db  

def seed_database():
    init_db()  

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()


    try:
        cursor.executescript("""
            DELETE FROM mood_evaluations;
            DELETE FROM study_sessions;
            DELETE FROM courses;
            DELETE FROM users;
        """)

        # Create a test user (Password: 123456)
        hashed_pw = bcrypt.hashpw("123456".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        
        cursor.execute("""
            INSERT INTO users (user_id, username, password_hash, gender, age, field_of_interest, study_goal, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (1, "labubu", hashed_pw, "Male", 20, "Computer Science", "High GPA", datetime.now() - timedelta(days=7)))

        # Create courses associated with user_id = 1
        courses = [
            (1, 1, "CS254 Python Programming"),
            (2, 1, "CS213 Data Structures")
        ]
        cursor.executemany("INSERT INTO courses (course_id, user_id, course_name) VALUES (?, ?, ?)", courses)

        # Create study sessions with varied data for ML testing
        now = datetime.now()
        sessions = [
            # Normal session meeting the goal
            (1, 1, 1, now - timedelta(days=2, hours=3), now - timedelta(days=2, hours=2), 60, 60, "Lecture"),
            # Overworking session (actual > goal)
            (2, 1, 1, now - timedelta(days=1, hours=5), now - timedelta(days=1, hours=3), 60, 120, "Coding"),
            # Given up early session (actual < goal)
            (3, 1, 2, now - timedelta(hours=4), now - timedelta(hours=3, minutes=45), 120, 15, "Exam Prep")
        ]
        cursor.executemany("""
            INSERT INTO study_sessions (session_id, user_id, course_id, start_time, end_time, goal_minutes, actual_minutes, task_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, sessions)

        # Create mood evaluations
        evaluations = [
            # Normal mood at the start of the week
            (1, 1, 2, 2, 4, now - timedelta(days=2)),
            # Signs of burnout after heavy coding session
            (2, 1, 4, 3, 2, now - timedelta(days=1))
        ]
        cursor.executemany("""
            INSERT INTO mood_evaluations (evaluation_id, user_id, exhaustion_score, cynicism_score, efficacy_score, evaluated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, evaluations)

        conn.commit()
        print("Database seeding completed")

    except Exception as e:
        print(f"error occurred: {e}")
        conn.rollback()
    
    finally:
        conn.close()

if __name__ == "__main__":
    seed_database()