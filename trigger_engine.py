from datetime import datetime, timedelta
from database import get_connection as get_db_connection
import joblib
import pandas as pd

# โหลด trained model มาใช้
model = joblib.load("burnout_model.pkl")
feature_order = joblib.load("model_features.pkl")

def weekly_trigger(user_id):

    conn = get_db_connection()
    cursor = conn.cursor()
# ตรวจสอบว่า user ประเมินไปล่าสุดเมื่อไหร่
    cursor.execute("""
        SELECT MAX(evaluated_at)
        FROM mood_evaluations
        WHERE user_id = ?
    """, (user_id,))

    last_eval = cursor.fetchone()[0]
    conn.close()
# ถ้ายังไม่เคยประเมินเลย trigger
    if last_eval is None:
        return True
# ถ้าเคยประเมินแล้ว แต่เกิน 7 วันก็ trigger
    last_eval = datetime.fromisoformat(last_eval)
    return datetime.now() - last_eval >= timedelta(days=7)


def late_night_trigger(user_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DATE(start_time)
        FROM study_sessions
        WHERE user_id = ?
        AND time(start_time) >= '20:00'
        ORDER BY start_time DESC
        LIMIT 3
    """, (user_id,))
#Example result: วันที่เรียนหลัง 20:00 เรียกมา ล่าสุดยังไม่เช็คว่าติดกันมั้ย
#April 13
#April 12
#April 11
    rows = cursor.fetchall()
    conn.close()
# ถ้าน้อยกว้า 3 ครั้งก็ไม่ trigger
    if len(rows) < 3:
        return False

    dates = [datetime.fromisoformat(r[0]) for r in rows]

    return (
        (dates[0] - dates[1]).days == 1 and
        (dates[1] - dates[2]).days == 1
    )

# ฟีเจอร์ที่ใช้มี 3 ตัว: total_minutes, overwork_minutes, session_count
def get_latest_features(user_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            SUM(actual_minutes),
            SUM(actual_minutes - goal_minutes),
            COUNT(session_id)
        FROM study_sessions
        WHERE user_id = ?
        AND DATE(start_time) = DATE('now')
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row[0] is None:
        return None
    features_dict = {
        "total_minutes": row[0],
        "overwork_minutes": row[1],
        "session_count": row[2]
        }
    # เรียงฟีเจอร์ให้ตรงกับตอน train
    ordered_features = pd.DataFrame(
        [[features_dict[col] for col in feature_order]],
        columns=feature_order
    )
    return ordered_features

#   use trained ML model to detect burnout risk
def ml_trigger(user_id):
# ดึงฟีเจอร์ล่าสุดมา
    features = get_latest_features(user_id)

    if features is None:
        return False
# predict burnout level (0,1,2) จากฟีเจอร์
    prediction = model.predict(features)
# trigger ถ้า burnout level สูง (2)
    return prediction[0] == 2

# main function ที่จะเรียกใน app.py เพื่อเช็คว่าtrigger form มั้ย
def should_trigger_mood_form(user_id):

    if weekly_trigger(user_id):
        return True

    if late_night_trigger(user_id):
        return True

    if ml_trigger(user_id):
        return True

    return False