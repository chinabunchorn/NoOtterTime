import json
import sqlite3
from datetime import datetime, date, timedelta
from flask import Flask, request, render_template, redirect, url_for, session, flash
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
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        gender = request.form["gender"]
        age = int(request.form["age"]) if request.form["age"] else None
        field_of_interest = request.form["field_of_interest"]
        study_goal = request.form["study_goal"]

        # Validation
        if not username or not password:
            flash("Username and password are required", "error")
            return redirect(url_for("signup"))

        if age is not None and (age < 0 or age > 120):
            flash("Invalid age", "error")
            return redirect(url_for("signup"))

        # Hash Password
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
                gender or "Not specified",
                age,
                field_of_interest or "",
                study_goal or "",
                datetime.now()
            ))

            conn.commit()

        except sqlite3.IntegrityError:
            flash("Username already exists", "error")
            return redirect(url_for("signup"))

        finally:
            cursor.close()
            conn.close()

        # Return to login if success
        flash("Account created successfully! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

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

    username = session["user"]
    conn = get_db()
    cursor = conn.cursor()

    # Get user_id
    cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
    user_row = cursor.fetchone()
    if not user_row:
        conn.close()
        return redirect(url_for("login"))
    user_id = user_row["user_id"]

    # --- Streak: count consecutive days with study sessions up to today ---
    cursor.execute("""
        SELECT DISTINCT DATE(start_time) AS day
        FROM study_sessions
        WHERE user_id = ?
        ORDER BY day DESC
    """, (user_id,))
    session_days = [row["day"] for row in cursor.fetchall()]
    streak = 0
    for i, d in enumerate(session_days):
        if d == (date.today() - timedelta(days=i)).isoformat():
            streak += 1
        else:
            break

    # --- Burnout label from latest mood evaluation ---
    cursor.execute("""
        SELECT exhaustion_score, cynicism_score, efficacy_score
        FROM mood_evaluations
        WHERE user_id = ?
        ORDER BY evaluated_at DESC
        LIMIT 1
    """, (user_id,))
    mood = cursor.fetchone()
    if mood:
        score = mood["exhaustion_score"] + mood["cynicism_score"] - mood["efficacy_score"]
        if score <= 2:
            burnout_label = "Low"
        elif score <= 5:
            burnout_label = "Medium"
        else:
            burnout_label = "High"
    else:
        burnout_label = "N/A"

    suggestions = {
        "Low":  "Keep it up! You're doing great. Stay consistent.",
        "Medium": "Take short breaks and make sure you get enough sleep.",
        "High": "Consider taking a rest day to recover and recharge.",
        "N/A":  "Log some study sessions to get personalised tips.",
    }
    suggestion = suggestions[burnout_label]

    # --- Weekly study hours (last 7 days) ---
    cursor.execute("""
        SELECT
            strftime('%m/%d', DATE(start_time)) AS day,
            SUM(actual_minutes) / 60.0          AS hours
        FROM study_sessions
        WHERE user_id = ?
          AND DATE(start_time) >= DATE('now', '-6 days')
        GROUP BY DATE(start_time)
        ORDER BY DATE(start_time)
    """, (user_id,))
    weekly_json = json.dumps([{"day": r["day"], "hours": r["hours"]}
                               for r in cursor.fetchall()])

    # --- Top 3 courses by total hours ---
    cursor.execute("""
        SELECT c.course_name, SUM(s.actual_minutes) / 60.0 AS hrs
        FROM study_sessions s
        JOIN courses c ON s.course_id = c.course_id
        WHERE s.user_id = ?
        GROUP BY c.course_id
        ORDER BY hrs DESC
        LIMIT 3
    """, (user_id,))
    courses = [{"course_name": r["course_name"], "hrs": r["hrs"]}
               for r in cursor.fetchall()]

    conn.close()

    return render_template(
        "dashboard.html",
        username=username,
        streak=streak,
        burnout={"label": burnout_label},
        suggestion=suggestion,
        weekly_json=weekly_json,
        courses=courses,
    )

#--------------------INDEX----------------------

@app.route("/")
def index():
    return render_template("index.html")

#---------------------RUN-----------------------
if __name__ == "__main__":
    app.run(debug=True)