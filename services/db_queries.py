from datetime import datetime, timedelta
from database import get_db_connection as get_postgres_connection

get_db_connection = get_postgres_connection


def get_user_courses(user_id):
    """get all courses"""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = 'SELECT course_id, course_name FROM courses WHERE user_id = %s'
    cursor.execute(query, (user_id,))
    courses = cursor.fetchall()
    conn.close()
    return [dict(row) for row in courses]


def add_course(user_id, course_name):
    """add new course and return new course_id"""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = 'INSERT INTO courses (user_id, course_name) VALUES (%s, %s) RETURNING course_id'
    cursor.execute(query, (user_id, course_name))
    course_id = cursor.fetchone()['course_id']
    conn.commit()
    conn.close()
    return course_id


def save_study_session(user_id, data):
    """Save study session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
        INSERT INTO study_sessions 
        (user_id, course_id, start_time, end_time, goal_minutes, actual_minutes, task_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING session_id
    '''
    cursor.execute(query, (
        user_id,
        data['course_id'],
        data['start_time'],
        data['end_time'],
        data['goal_minutes'],
        data['actual_minutes'],
        data['task_type']
    ))
    session_id = cursor.fetchone()['session_id']
    conn.commit()
    conn.close()
    return session_id


def get_study_history(user_id, limit=20):
    """recent study sessions joined with course names for dashboard"""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
        SELECT s.*, c.course_name 
        FROM study_sessions s
        JOIN courses c ON s.course_id = c.course_id
        WHERE s.user_id = %s
        ORDER BY s.start_time DESC
        LIMIT %s
    '''
    cursor.execute(query, (user_id, limit))
    sessions = cursor.fetchall()
    conn.close()
    return [dict(row) for row in sessions]


def get_weekly_study_summary(user_id, limit=12):
    """
    study sessions into weekly summaries. แสดงผลลัพธ์ 12 สัปดาห์ล่าสุดว่าเรียนอะไรเยอะสุด
    for 'Week by Week' bar charts on the frontend dashboard.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
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
    '''
    cursor.execute(query, (user_id, limit))
    weekly_summary = cursor.fetchall()
    conn.close()
    return [dict(row) for row in weekly_summary]


def get_weekly_top_course(user_id, limit=12):
    """course with highest study time for each week. เรียนอะไรเยอะสุดในสัปดาห์นั้น"""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
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
            SELECT 
                *,
                RANK() OVER (
                    PARTITION BY year, week_number 
                    ORDER BY total_minutes DESC
                ) as rank
            FROM CourseWeeklySum
        )
        SELECT 
            year, 
            week_number, 
            course_name, 
            total_minutes
        FROM RankedCourses
        WHERE rank = 1
        ORDER BY year DESC, week_number DESC
        LIMIT %s
    '''
    cursor.execute(query, (user_id, limit))
    top_courses = cursor.fetchall()
    conn.close()
    return [dict(row) for row in top_courses]


def get_daily_course_breakdown(user_id, limit=30):
    """
    study time grouped by date and course.
    for 'Weekly Calendar' study activities.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
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
    '''
    cursor.execute(query, (user_id, limit))
    breakdown = cursor.fetchall()
    conn.close()
    return [dict(row) for row in breakdown]


def save_mood_evaluation(user_id, data):
    """Saves mood evaluation."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query = '''
        INSERT INTO mood_evaluations 
        (user_id, exhaustion_score, cynicism_score, efficacy_score, evaluated_at)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING evaluation_id
    '''
    cursor.execute(query, (
        user_id,
        data['exhaustion_score'],
        data['cynicism_score'],
        data['efficacy_score'],
        now
    ))
    eval_id = cursor.fetchone()['evaluation_id']
    conn.commit()
    conn.close()
    return eval_id


def get_mood_history(user_id, limit=10):
    """UI charts and monitoring."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = 'SELECT * FROM mood_evaluations WHERE user_id = %s ORDER BY evaluated_at DESC LIMIT %s'
    cursor.execute(query, (user_id, limit))
    moods = cursor.fetchall()
    conn.close()
    return [dict(row) for row in moods]


def get_weekly_mood_summary(user_id, limit=12):
    """
    raw mood evaluations into weekly average
    for frontend charts track burnout
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
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
    '''
    cursor.execute(query, (user_id, limit))
    weekly_moods = cursor.fetchall()
    conn.close()
    return [dict(row) for row in weekly_moods]


def get_training_data(user_id):
    """dataset for the Machine Learning burnout prediction model."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
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
    '''
    cursor.execute(query, (user_id,))
    data = cursor.fetchall()
    conn.close()
    return [dict(row) for row in data]


def get_current_streak(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
        SELECT DISTINCT DATE(start_time) as study_date
        FROM study_sessions
        WHERE user_id = %s
        ORDER BY study_date DESC
    '''
    cursor.execute(query, (user_id,))
    dates = cursor.fetchall()
    conn.close()

    if not dates:
        return {"streak_days": 0}

    streak = 0
    date_list = []
    for row in dates:
        study_date = row['study_date']
        if isinstance(study_date, str):
            study_date = datetime.strptime(study_date, '%Y-%m-%d').date()
        date_list.append(study_date)
    
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    if date_list[0] != today and date_list[0] != yesterday:
        return {"streak_days": 0}

    current_check_date = date_list[0]
    
    for study_date in date_list:
        if study_date == current_check_date:
            streak += 1
            current_check_date -= timedelta(days=1)
        else:
            break
    
    return {"streak_days": streak}


def get_study_distribution(user_id, days=7):
    """
    Retrieves total study time per course for the Pie Chart.
    Defaults to evaluating the last 7 days.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
        SELECT 
            c.course_name,
            SUM(s.actual_minutes) as total_minutes
        FROM study_sessions s
        JOIN courses c ON s.course_id = c.course_id
        WHERE s.user_id = %s AND s.start_time >= NOW() - INTERVAL %s
        GROUP BY s.course_id, c.course_name
    '''
    modifier = f'{days} days'
    cursor.execute(query, (user_id, modifier))
    distribution = cursor.fetchall()
    conn.close()
    return [dict(row) for row in distribution]


def get_smart_suggestion(user_id, days=7):
    """
    อันนี้คือกะให้ suggest จาก ผลรวมของ goal ลบกับ ผลรวมของเวลาที่จับ
    ถ้าวิชาไหน ผลต่างเยอะ แปลว่าเรียนไม่ค่อยถึงเป้าหมายให้ suggest
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
        SELECT 
            c.course_name,
            SUM(s.goal_minutes) - SUM(s.actual_minutes) AS deficit
        FROM study_sessions s
        JOIN courses c ON s.course_id = c.course_id
        WHERE s.user_id = %s AND s.start_time >= NOW() - INTERVAL %s
        GROUP BY s.course_id, c.course_name
        ORDER BY deficit DESC
        LIMIT 1
    '''
    modifier = f'{days} days'
    cursor.execute(query, (user_id, modifier))
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


def create_schedule(user_id, data):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
        INSERT INTO schedules 
        (user_id, course_id, title, date, start_time, end_time)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING schedule_id
    '''
    cursor.execute(query, (
        user_id,
        data['course_id'],
        data.get('title', ''),
        data['date'],
        data.get('start_time'),
        data.get('end_time')
    ))
    schedule_id = cursor.fetchone()['schedule_id']
    conn.commit()
    conn.close()
    return schedule_id


def get_schedules(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
        SELECT s.*, c.course_name
        FROM schedules s
        JOIN courses c ON s.course_id = c.course_id
        WHERE s.user_id = %s
        ORDER BY s.date ASC
    '''
    cursor.execute(query, (user_id,))
    schedules = cursor.fetchall()
    conn.close()
    return [dict(row) for row in schedules]


def delete_schedule(user_id, schedule_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
        DELETE FROM schedules
        WHERE schedule_id = %s AND user_id = %s
    '''
    cursor.execute(query, (schedule_id, user_id))
    conn.commit()
    conn.close()