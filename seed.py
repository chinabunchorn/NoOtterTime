import libsql as sqlite3
import bcrypt
from datetime import datetime, timedelta
import random
from database import init_db, get_connection


def seed_database():

    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.executescript("""
            DELETE FROM mood_evaluations;
            DELETE FROM study_sessions;
            DELETE FROM courses;
            DELETE FROM users;
        """)

        # Create test user
        hashed_pw = bcrypt.hashpw("123456".encode(), bcrypt.gensalt()).decode()

        cursor.execute("""
            INSERT INTO users
            (user_id, username, password_hash, gender, age, field_of_interest, study_goal, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            1,
            "labubu",
            hashed_pw,
            "Male",
            20,
            "Computer Science",
            "High GPA",
            datetime.now() - timedelta(days=30)
        ))

        # Courses
        courses = [
            (1, 1, "CS254 Python Programming"),
            (2, 1, "CS213 Data Structures")
        ]

        cursor.executemany("""
            INSERT INTO courses
            (course_id, user_id, course_name)
            VALUES (?, ?, ?)
        """, courses)

        session_id = 1
        evaluation_id = 1

        now = datetime.now()

        for i in range(30):   # 30 training days

            day = now - timedelta(days=i)

            session_count = random.randint(1, 3)

            total_minutes = 0
            overwork_minutes = 0

            for _ in range(session_count):

                goal = random.choice([45, 60, 90, 120])

                actual = goal + random.choice([
                    -30, -15, 0, 10, 20, 45
                ])

                actual = max(5, actual)

                start_time = day.replace(hour=random.randint(9, 22))
                end_time = start_time + timedelta(minutes=actual)

                cursor.execute("""
                    INSERT INTO study_sessions
                    (session_id, user_id, course_id, start_time, end_time,
                     goal_minutes, actual_minutes, task_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    1,
                    random.choice([1, 2]),
                    start_time,
                    end_time,
                    goal,
                    actual,
                    "Study"
                ))

                total_minutes += actual
                overwork_minutes += (actual - goal)

                session_id += 1

            # Generate mood based on workload pattern

            if total_minutes > 200:
                exhaustion = 3
                cynicism = 3
                efficacy = 1

            elif total_minutes > 120:
                exhaustion = 2
                cynicism = 2
                efficacy = 2

            else:
                exhaustion = 1
                cynicism = 1
                efficacy = 3

            cursor.execute("""
                INSERT INTO mood_evaluations
                (evaluation_id, user_id,
                 exhaustion_score,
                 cynicism_score,
                 efficacy_score,
                 evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                evaluation_id,
                1,
                exhaustion,
                cynicism,
                efficacy,
                day
            ))

            evaluation_id += 1

        conn.commit()

        print("ML training dataset seeded successfully")

    except Exception as e:

        print("Seeding failed:", e)
        conn.rollback()

    finally:

        conn.close()


if __name__ == "__main__":
    seed_database()