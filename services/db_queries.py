import sqlite3
from datetime import datetime, timedelta

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row 
    return conn


def get_user_courses(user_id):
    """get all courses"""
    conn = get_db_connection()
    query = 'SELECT course_id, course_name FROM courses WHERE user_id = ?'
    courses = conn.execute(query, (user_id,)).fetchall()
    conn.close()
    return [dict(row) for row in courses]

def add_course(user_id, course_name):
    """add new course and return new course_id"""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = 'INSERT INTO courses (user_id, course_name) VALUES (?, ?)'
    cursor.execute(query, (user_id, course_name))
    course_id = cursor.lastrowid
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
        VALUES (?, ?, ?, ?, ?, ?, ?)
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
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id

def get_study_history(user_id, limit=20):
    """recent study sessions joined with course names for dashboard"""
    conn = get_db_connection()
    query = '''
        SELECT s.*, c.course_name 
        FROM study_sessions s
        JOIN courses c ON s.course_id = c.course_id
        WHERE s.user_id = ?
        ORDER BY s.start_time DESC
        LIMIT ?
    '''
    sessions = conn.execute(query, (user_id, limit)).fetchall()
    conn.close()
    return [dict(row) for row in sessions]

def get_weekly_study_summary(user_id, limit=12):
    """
    study sessions into weekly summaries. แสดงผลลัพธ์ 12 สัปดาห์ล่าสุดว่าเรียนอะไรเยอะสุด
    for 'Week by Week' bar charts on the frontend dashboard.
    """
    conn = get_db_connection()
    
    query = '''
        SELECT 
            STRFTIME('%Y', start_time) AS year,
            STRFTIME('%W', start_time) AS week_number,
            SUM(actual_minutes) AS total_minutes_studied,
            SUM(goal_minutes) AS total_goal_minutes,
            COUNT(session_id) AS total_sessions_completed
        FROM study_sessions
        WHERE user_id = ?
        GROUP BY year, week_number
        ORDER BY year DESC, week_number DESC
        LIMIT ?
    '''
    
    weekly_summary = conn.execute(query, (user_id, limit)).fetchall()
    conn.close()
    
    return [dict(row) for row in weekly_summary]

def get_weekly_top_course(user_id, limit=12):

    """course with highest study time for each week. เรียนอะไรเยอะสุดในสัปดาห์นั้น"""
    conn = get_db_connection()
    
    query = '''
        WITH CourseWeeklySum AS (
            SELECT 
                STRFTIME('%Y', s.start_time) AS year,
                STRFTIME('%W', s.start_time) AS week_number,
                s.course_id,
                c.course_name,
                SUM(s.actual_minutes) AS total_minutes
            FROM study_sessions s
            JOIN courses c ON s.course_id = c.course_id
            WHERE s.user_id = ?
            GROUP BY year, week_number, s.course_id
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
        LIMIT ?
    '''
    
    top_courses = conn.execute(query, (user_id, limit)).fetchall()
    conn.close()
    
    return [dict(row) for row in top_courses]

def get_daily_course_breakdown(user_id, limit=30):
    """
    study time grouped by date and course.
    for 'Weekly Calendar' study activities.
    """
    conn = get_db_connection()
    
    # GROUP BY DATE() ensures we separate Monday's Python study from Tuesday's Python study.
    # STRFTIME('%w') returns 0-6 (0=Sunday, 1=Monday, etc.) to help Frontend place it on a calendar.
    query = '''
        SELECT 
            DATE(s.start_time) AS study_date,
            STRFTIME('%w', s.start_time) AS day_of_week,
            c.course_name,
            SUM(s.actual_minutes) AS total_minutes
        FROM study_sessions s
        JOIN courses c ON s.course_id = c.course_id
        WHERE s.user_id = ?
        GROUP BY study_date, s.course_id
        ORDER BY study_date DESC
        LIMIT ?
    '''
    
    breakdown = conn.execute(query, (user_id, limit)).fetchall()
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
        VALUES (?, ?, ?, ?, ?)
    '''
    cursor.execute(query, (
        user_id, 
        data['exhaustion_score'], 
        data['cynicism_score'], 
        data['efficacy_score'], 
        now
    ))
    eval_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return eval_id

def get_mood_history(user_id, limit=10):
    """UI charts and monitoring."""
    conn = get_db_connection()
    query = 'SELECT * FROM mood_evaluations WHERE user_id = ? ORDER BY evaluated_at DESC LIMIT ?'
    moods = conn.execute(query, (user_id, limit)).fetchall()
    conn.close()
    return [dict(row) for row in moods]

def get_weekly_mood_summary(user_id, limit=12):
    """
    raw mood evaluations into weekly average
    for frontend charts track burnout
    """
    conn = get_db_connection()
    
    query = '''
        SELECT 
            STRFTIME('%Y', evaluated_at) AS year,
            STRFTIME('%W', evaluated_at) AS week_number,
            ROUND(AVG(exhaustion_score), 1) AS avg_exhaustion,
            ROUND(AVG(cynicism_score), 1) AS avg_cynicism,
            ROUND(AVG(efficacy_score), 1) AS avg_efficacy,
            COUNT(evaluation_id) AS total_evaluations
        FROM mood_evaluations
        WHERE user_id = ?
        GROUP BY year, week_number
        ORDER BY year DESC, week_number DESC
        LIMIT ?
    '''
    
    weekly_moods = conn.execute(query, (user_id, limit)).fetchall()
    conn.close()
    
    return [dict(row) for row in weekly_moods]

def get_training_data(user_id):
    """dataset for the Machine Learning burnout prediction model."""
    conn = get_db_connection()
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
        WHERE s.user_id = ?
        GROUP BY DATE(s.start_time)
        ORDER BY date DESC
    '''
    data = conn.execute(query, (user_id,)).fetchall()
    conn.close()
    return [dict(row) for row in data]

def get_current_streak(user_id):

    conn = get_db_connection()
    query = '''
        SELECT DISTINCT DATE(start_time) as study_date
        FROM study_sessions
        WHERE user_id = ?
        ORDER BY study_date DESC
    '''
    dates = conn.execute(query, (user_id,)).fetchall()
    conn.close()

    if not dates:
        return {"streak_days": 0}

    streak = 0
    date_list = [datetime.strptime(row['study_date'], '%Y-%m-%d').date() for row in dates]
    
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
    query = '''
        SELECT 
            c.course_name, 
            SUM(s.actual_minutes) as total_minutes
        FROM study_sessions s
        JOIN courses c ON s.course_id = c.course_id
        WHERE s.user_id = ? AND s.start_time >= date('now', ?)
        GROUP BY s.course_id
    '''
    modifier = f'-{days} days'
    distribution = conn.execute(query, (user_id, modifier)).fetchall()
    conn.close()
    
    return [dict(row) for row in distribution]


def get_smart_suggestion(user_id, days=7):
    """
    อันนี้คือกะให้ suggest จาก ผลรวมของ goal ลบกับ ผลรวมของเวลาที่จับ
    ถ้าวิชาไหน ผลต่างเยอะ แปลว่าเรียนไม่ค่อยถึงเป้าหมายให้ suggest
    """
    conn = get_db_connection()
    query = '''
        SELECT 
            c.course_name,
            SUM(s.goal_minutes) - SUM(s.actual_minutes) AS deficit
        FROM study_sessions s
        JOIN courses c ON s.course_id = c.course_id
        WHERE s.user_id = ? AND s.start_time >= date('now', ?)
        GROUP BY s.course_id
        ORDER BY deficit DESC
        LIMIT 1
    '''
    modifier = f'-{days} days'
    suggestion = conn.execute(query, (user_id, modifier)).fetchone()
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

def create_schedule(user_id, data) :
    conn = get_db_connection()
    cursor = conn.cursor()

    query = '''
        INSERT INTO schedules 
        (user_id, course_id, title, date, start_time, end_time)
        VALUES (?, ?, ?, ?, ?, ?)
    '''

    cursor.execute(query, (
        user_id,
        data['course_id'],
        data.get('title', ''),
        data['date'],
        data.get('start_time'),
        data.get('end_time')
    ))

    schedule_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return schedule_id

def get_schedules(user_id):
    conn = get_db_connection()

    query = '''
        SELECT s.*, c.course_name
        FROM schedules s
        JOIN courses c ON s.course_id = c.course_id
        WHERE s.user_id = ?
        ORDER BY s.date ASC
    '''

    schedules = conn.execute(query, (user_id,)).fetchall()
    conn.close()

    return [dict(row) for row in schedules]

def delete_schedule(user_id, schedule_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = '''
        DELETE FROM schedules
        WHERE schedule_id = ? AND user_id = ?
    '''

    cursor.execute(query, (schedule_id, user_id))
    conn.commit()
    conn.close()