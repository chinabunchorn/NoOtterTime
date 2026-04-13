import sqlite3
from flask import Flask, request, jsonify, session
from datetime import datetime
import bcrypt
from flask_cors import CORS

from database import get_db
import services.db_queries as db
from models import init_db

app = Flask(__name__)
app.secret_key = "your_secret_key"
CORS(app, supports_credentials=True)

# First DB setup once
init_db()

# ==========================================
# 🔐 AUTHENTICATION ROUTES
# ==========================================

@app.route("/api/signup", methods=["POST"])
def signup():
    """Handles user registration and returns JSON status."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    username = data.get("username", "").strip().lower()
    password = data.get("password", "")
    gender = data.get("gender", "Not specified")
    
    try:
        age = int(data.get("age")) if data.get("age") else None
    except ValueError:
        return jsonify({"error": "Age must be a valid number"}), 400
        
    field_of_interest = data.get("field_of_interest", "")
    study_goal = data.get("study_goal", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    if age is not None and (age < 0 or age > 120):
        return jsonify({"error": "Invalid age"}), 400

    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO users 
            (username, password_hash, gender, age, field_of_interest, study_goal, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            username,
            hashed_pw.decode("utf-8"),
            gender,
            age,
            field_of_interest,
            study_goal,
            datetime.now()
        ))
        conn.commit()
        new_user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already exists"}), 409
    finally:
        cursor.close()
        conn.close()

    return jsonify({
        "status": "success", 
        "message": "Account created successfully",
        "user_id": new_user_id
    }), 201


@app.route("/api/login", methods=["POST"])
def login():
    """Authenticates user and establishes a session."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    username = data.get("username", "").strip().lower()
    password = data.get("password", "")

    if not username or not password:
         return jsonify({"error": "Username and password are required"}), 400

    conn = get_db()
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()

    if user:
        stored_hash = user["password_hash"].encode("utf-8")

        if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            
            return jsonify({
                "status": "success", 
                "message": "Logged in successfully",
                "user_id": user["user_id"]
            }), 200

    return jsonify({"error": "Username or Password Incorrect"}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    """Clears the user session."""
    session.clear() 
    return jsonify({"status": "success", "message": "Logged out successfully"}), 200


# ==========================================
# 📘 COURSE MANAGEMENT
# ==========================================

@app.route("/api/courses", methods=["GET"])
def get_courses():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    courses = db.get_user_courses(user_id)
    return jsonify({"status": "success", "data": courses}), 200

@app.route("/api/courses", methods=["POST"])
def create_course():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    course_name = data.get("course_name")
    
    if not course_name:
        return jsonify({"error": "Course name is required"}), 400

    new_id = db.add_course(user_id, course_name)
    return jsonify({"status": "success", "course_id": new_id}), 201


# ==========================================
# ⏱️ STUDY SESSIONS & ANALYTICS
# ==========================================

@app.route("/api/sessions", methods=["POST"])
def log_session():
    user_id = session.get("user_id")
    if not user_id: return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    
    required_fields = ["course_id", "start_time", "end_time", "goal_minutes", "actual_minutes", "task_type"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: '{field}'"}), 400

    session_id = db.save_study_session(user_id, data)
    return jsonify({"status": "success", "session_id": session_id}), 201

@app.route("/api/sessions/history", methods=["GET"])
def session_history():
    user_id = session.get("user_id")
    if not user_id: return jsonify({"error": "Unauthorized"}), 401

    limit = request.args.get("limit", default=20, type=int)
    history = db.get_study_history(user_id, limit)
    return jsonify({"status": "success", "data": history}), 200

@app.route("/api/analytics/weekly-study", methods=["GET"])
def weekly_study_summary():
    user_id = session.get("user_id")
    if not user_id: return jsonify({"error": "Unauthorized"}), 401

    summary = db.get_weekly_study_summary(user_id)
    return jsonify({"status": "success", "data": summary}), 200

@app.route("/api/analytics/daily-breakdown", methods=["GET"])
def daily_breakdown():
    user_id = session.get("user_id")
    if not user_id: return jsonify({"error": "Unauthorized"}), 401

    breakdown = db.get_daily_course_breakdown(user_id)
    return jsonify({"status": "success", "data": breakdown}), 200

@app.route("/api/analytics/top-courses", methods=["GET"])
def top_weekly_courses():
    user_id = session.get("user_id")
    if not user_id: return jsonify({"error": "Unauthorized"}), 401

    top = db.get_weekly_top_course(user_id)
    return jsonify({"status": "success", "data": top}), 200


# ==========================================
# 🏠 DASHBOARD OVERVIEW
# ==========================================

@app.route("/api/dashboard/overview", methods=["GET"])
def dashboard_overview():
    user_id = session.get("user_id")
    if not user_id: return jsonify({"error": "Unauthorized"}), 401

    streak = db.get_current_streak(user_id)
    distribution = db.get_study_distribution(user_id, days=7)
    suggestion = db.get_smart_suggestion(user_id, days=7)

    return jsonify({
        "status": "success",
        "data": {
            "streak": streak["streak_days"],
            "pie_chart": distribution,
            "smart_suggestion": suggestion
        }
    }), 200


# ==========================================
# 🧠 MOOD & ML DATA
# ==========================================

@app.route("/api/moods", methods=["POST"])
def post_mood():
    user_id = session.get("user_id")
    if not user_id: return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    
    required_fields = ["exhaustion_score", "cynicism_score", "efficacy_score"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: '{field}'"}), 400

    eval_id = db.save_mood_evaluation(user_id, data)
    return jsonify({"status": "success", "evaluation_id": eval_id}), 201

@app.route("/api/moods/history", methods=["GET"])
def mood_history():
    user_id = session.get("user_id")
    if not user_id: return jsonify({"error": "Unauthorized"}), 401

    limit = request.args.get("limit", default=10, type=int)
    history = db.get_mood_history(user_id, limit)
    return jsonify({"status": "success", "data": history}), 200

@app.route("/api/moods/summary/weekly", methods=["GET"])
def weekly_mood_summary():
    user_id = session.get("user_id")
    if not user_id: return jsonify({"error": "Unauthorized"}), 401

    summary = db.get_weekly_mood_summary(user_id)
    return jsonify({"status": "success", "data": summary}), 200

@app.route("/api/ml/training-data", methods=["GET"])
def ml_dataset():
    user_id = session.get("user_id")
    if not user_id: return jsonify({"error": "Unauthorized"}), 401

    dataset = db.get_training_data(user_id)
    return jsonify({"status": "success", "data": dataset}), 200

#---------------------RUN-----------------------
if __name__ == "__main__":
    app.run(debug=True)