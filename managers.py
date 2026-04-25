import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from models import Course, StudySession, MoodEvaluation
from database import get_db_connection


class BaseManager:
    """Parent class to handle DB connection encapsulation."""
    def __init__(self, db_path=None):
        # db_path is kept for backwards compatibility but not used with PostgreSQL
        pass

    def _get_connection(self):
        """Returns a PostgreSQL connection with RealDictCursor for dict-like row access."""
        conn = get_db_connection()
        return conn
    
    def _get_cursor(self, conn):
        """Returns a cursor that returns rows as dictionaries."""
        return conn.cursor(cursor_factory=RealDictCursor)

class StudyManager(BaseManager):

    # --- Courses ---

    def add_course(self, user_id, course_name):
        """Validates via Course model, then inserts into DB."""
        course = Course(course_name=course_name, user_id=user_id)
        course.validate_name()

        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute(
            'INSERT INTO courses (user_id, course_name) VALUES (%s, %s) RETURNING course_id',
            (course.get_user_id(), course.get_course_name())
        )
        course_id = cursor.fetchone()['course_id']
        conn.commit()
        conn.close()
        return course_id

    def get_courses(self, user_id):
        """Returns all courses belonging to a user."""
        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute(
            'SELECT course_id, course_name FROM courses WHERE user_id = %s',
            (user_id,)
        )
        courses = cursor.fetchall()
        conn.close()
        return [dict(row) for row in courses]

    # --- Study Sessions ---

    def save_study_session(self, user_id, data):
        """Validates via StudySession model, then inserts into DB."""
        session_obj = StudySession(
            course_id=data['course_id'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            goal_minutes=data['goal_minutes'],
            actual_minutes=data['actual_minutes'],
            task_type=data.get('task_type')
        )

        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute('''
            INSERT INTO study_sessions
            (user_id, course_id, start_time, end_time, goal_minutes, actual_minutes, task_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING session_id
        ''', (
            user_id,
            session_obj.get_course_id(),
            session_obj.get_start_time(),
            session_obj.get_end_time(),
            session_obj.get_goal_minutes(),
            session_obj.get_actual_minutes(),
            session_obj.get_task_type()
        ))
        session_id = cursor.fetchone()['session_id']
        conn.commit()
        conn.close()
        return session_id

    def get_study_history(self, user_id, limit=20):
        """Recent study sessions joined with course names."""
        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute('''
            SELECT s.*, c.course_name
            FROM study_sessions s
            JOIN courses c ON s.course_id = c.course_id
            WHERE s.user_id = %s
            ORDER BY s.start_time DESC
            LIMIT %s
        ''', (user_id, limit))
        sessions = cursor.fetchall()
        conn.close()
        return [dict(row) for row in sessions]

    # --- Analytics ---

    def get_weekly_study_summary(self, user_id, limit=12):
        """Aggregates study sessions into weekly summaries (last 12 weeks)."""
        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute('''
            SELECT
                EXTRACT(YEAR FROM start_time)::INT AS year,
                TO_CHAR(start_time, 'WW')::INT AS week_number,
                SUM(actual_minutes) AS total_minutes_studied,
                SUM(goal_minutes) AS total_goal_minutes,
                COUNT(session_id) AS total_sessions_completed
            FROM study_sessions
            WHERE user_id = %s
            GROUP BY EXTRACT(YEAR FROM start_time), TO_CHAR(start_time, 'WW')
            ORDER BY year DESC, week_number DESC
            LIMIT %s
        ''', (user_id, limit))
        weekly_summary = cursor.fetchall()
        conn.close()
        return [dict(row) for row in weekly_summary]

    def get_weekly_top_course(self, user_id, limit=12):
        """Returns the course with the highest study time per week."""
        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute('''
            WITH CourseWeeklySum AS (
                SELECT
                    EXTRACT(YEAR FROM s.start_time)::INT AS year,
                    TO_CHAR(s.start_time, 'WW')::INT AS week_number,
                    s.course_id,
                    c.course_name,
                    SUM(s.actual_minutes) AS total_minutes
                FROM study_sessions s
                JOIN courses c ON s.course_id = c.course_id
                WHERE s.user_id = %s
                GROUP BY EXTRACT(YEAR FROM s.start_time), TO_CHAR(s.start_time, 'WW'), s.course_id, c.course_name
            ),
            RankedCourses AS (
                SELECT *,
                    RANK() OVER (
                        PARTITION BY year, week_number
                        ORDER BY total_minutes DESC
                    ) as rank
                FROM CourseWeeklySum
            )
            SELECT year, week_number, course_name, total_minutes
            FROM RankedCourses
            WHERE rank = 1
            ORDER BY year DESC, week_number DESC
            LIMIT %s
        ''', (user_id, limit))
        top_courses = cursor.fetchall()
        conn.close()
        return [dict(row) for row in top_courses]

    def get_daily_course_breakdown(self, user_id, limit=30):
        """Study time grouped by date and course (for weekly calendar view)."""
        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute('''
            SELECT
                DATE(s.start_time) AS study_date,
                EXTRACT(DOW FROM s.start_time)::INT AS day_of_week,
                c.course_name,
                SUM(s.actual_minutes) AS total_minutes
            FROM study_sessions s
            JOIN courses c ON s.course_id = c.course_id
            WHERE s.user_id = %s
            GROUP BY DATE(s.start_time), s.course_id, c.course_name
            ORDER BY study_date DESC
            LIMIT %s
        ''', (user_id, limit))
        breakdown = cursor.fetchall()
        conn.close()
        return [dict(row) for row in breakdown]

    # --- Dashboard Helpers ---

    def get_streak(self, user_id):
        """Calculates the current consecutive study day streak."""
        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute('''
            SELECT DISTINCT DATE(start_time) as study_date
            FROM study_sessions
            WHERE user_id = %s
            ORDER BY study_date DESC
        ''', (user_id,))
        dates = cursor.fetchall()
        conn.close()

        if not dates:
            return 0

        streak = 0
        date_list = [row['study_date'] for row in dates]
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        if date_list[0] != today and date_list[0] != yesterday:
            return 0

        current_check_date = date_list[0]
        for study_date in date_list:
            if study_date == current_check_date:
                streak += 1
                current_check_date -= timedelta(days=1)
            else:
                break
        return streak

    def get_study_distribution(self, user_id, days=6):
        """Total study time per course for the last 7 days (pie chart data)."""
        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute('''
            SELECT c.course_name, SUM(s.actual_minutes) as total_minutes
            FROM study_sessions s
            JOIN courses c ON s.course_id = c.course_id
            WHERE s.user_id = %s AND s.start_time >= NOW() - INTERVAL '%s days'
            GROUP BY s.course_id, c.course_name
        ''', (user_id, days))
        distribution = cursor.fetchall()
        conn.close()
        return [dict(row) for row in distribution]

    def get_smart_suggestion(self, user_id, days=7):
        """Suggests the course most behind its weekly goal."""
        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute('''
            SELECT c.course_name, SUM(s.goal_minutes) - SUM(s.actual_minutes) AS deficit
            FROM study_sessions s
            JOIN courses c ON s.course_id = c.course_id
            WHERE s.user_id = %s AND s.start_time >= NOW() - INTERVAL '%s days'
            GROUP BY s.course_id, c.course_name
            ORDER BY deficit DESC
            LIMIT 1
        ''', (user_id, days))
        suggestion = cursor.fetchone()
        conn.close()

        if suggestion and suggestion['deficit'] > 0:
            return {
                "suggestion": f"Focus on {suggestion['course_name']}",
                "reason": "Behind weekly goal",
                "deficit_minutes": suggestion['deficit']
            }
        return {
            "suggestion": "Keep up the good work!",
            "reason": "All goals met or no data",
            "deficit_minutes": 0
        }

class MoodManager(BaseManager):

    def save_evaluation(self, user_id, eval_data):
        """Validates scores via MoodEvaluation model, then saves to DB."""
        mood = MoodEvaluation(
            exhaustion=eval_data['exhaustion_score'],
            cynicism=eval_data['cynicism_score'],
            efficacy=eval_data['efficacy_score']
        )

        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute('''
            INSERT INTO mood_evaluations
            (user_id, exhaustion_score, cynicism_score, efficacy_score, evaluated_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING evaluation_id
        ''', (
            user_id,
            mood._exhaustion_score,
            mood._cynicism_score,
            mood._efficacy_score,
            datetime.now()
        ))
        eval_id = cursor.fetchone()['evaluation_id']
        conn.commit()
        conn.close()

        burnout_risk = mood.calculate_burnout_risk()
        return eval_id, burnout_risk

    def get_mood_history(self, user_id, limit=10):
        """Returns recent mood evaluations for UI charts."""
        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute(
            'SELECT * FROM mood_evaluations WHERE user_id = %s ORDER BY evaluated_at DESC LIMIT %s',
            (user_id, limit)
        )
        moods = cursor.fetchall()
        conn.close()
        return [dict(row) for row in moods]

    def get_weekly_mood_summary(self, user_id, limit=12):
        """Aggregates mood scores into weekly averages (for burnout tracking chart)."""
        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute('''
            SELECT
                EXTRACT(YEAR FROM evaluated_at)::INT AS year,
                TO_CHAR(evaluated_at, 'WW')::INT AS week_number,
                ROUND(AVG(exhaustion_score)::NUMERIC, 1) AS avg_exhaustion,
                ROUND(AVG(cynicism_score)::NUMERIC, 1) AS avg_cynicism,
                ROUND(AVG(efficacy_score)::NUMERIC, 1) AS avg_efficacy,
                COUNT(evaluation_id) AS total_evaluations
            FROM mood_evaluations
            WHERE user_id = %s
            GROUP BY EXTRACT(YEAR FROM evaluated_at), TO_CHAR(evaluated_at, 'WW')
            ORDER BY year DESC, week_number DESC
            LIMIT %s
        ''', (user_id, limit))
        weekly_moods = cursor.fetchall()
        conn.close()
        return [dict(row) for row in weekly_moods]

    def get_training_data(self, user_id):
        """Joins study sessions + mood evaluations for the ML burnout prediction model."""
        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute('''
            SELECT
                DATE(s.start_time) as date,
                SUM(s.actual_minutes) as total_minutes,
                SUM(s.actual_minutes - s.goal_minutes) as overwork_minutes,
                COUNT(s.session_id) as session_count,
                m.exhaustion_score,
                m.cynicism_score,
                m.efficacy_score
            FROM study_sessions s
            JOIN mood_evaluations m ON DATE(s.start_time) = DATE(m.evaluated_at)
            WHERE s.user_id = %s
            GROUP BY DATE(s.start_time), m.exhaustion_score, m.cynicism_score, m.efficacy_score
            ORDER BY date DESC
        ''', (user_id,))
        data = cursor.fetchall()
        conn.close()
        return [dict(row) for row in data]


class AuthManager(BaseManager):

    def create_user(self, username, password_hash, gender, age, field_of_interest, study_goal):
        """Inserts a new user and returns their new user_id."""
        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute('''
            INSERT INTO users
            (username, password_hash, gender, age, field_of_interest, study_goal, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING user_id
        ''', (username, password_hash, gender, age, field_of_interest, study_goal, datetime.now()))
        new_user_id = cursor.fetchone()['user_id']
        conn.commit()
        conn.close()
        return new_user_id

    def find_user_by_username(self, username):
        """Fetches a single user row by username, or None if not found."""
        conn = self._get_connection()
        cursor = self._get_cursor(conn)
        cursor.execute(
            'SELECT * FROM users WHERE username = %s', (username,)
        )
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None