import json
import sqlite3
from datetime import datetime, date, timedelta
from flask import Flask, request, render_template, redirect, url_for, session, flash
import bcrypt

from database import get_db
from models import init_db

app = Flask(__name__)
app.secret_key = "your_secret_key"

#First DB setup once
init_db()

#-----------------SIGN UP LOGIN LOGOUT-------------------

@app.route("/signup", methods=["GET", "POST"])
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

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user:
            stored_hash = user["password_hash"].encode("utf-8")

            if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
                session["user"] = user["username"]
                return redirect(url_for("dashboard"))

        flash("Username or Password Incorrect", "error")
        return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

#---------------------DASHBOARD------------------------

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

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