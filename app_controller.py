import os
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import bcrypt
from werkzeug.exceptions import HTTPException

from managers import StudyManager, MoodManager, AuthManager
from database import init_db  

import joblib
import numpy as np
import pandas as pd
from ml_retrain import retrain_model

try:
    burnout_model = joblib.load("burnout_model.pkl")
    feature_order = joblib.load("model_features.pkl")
except FileNotFoundError:
    burnout_model = None
    feature_order = []

from trigger_engine import should_trigger_mood_form


class AppController:
    def __init__(self):
        self._app = Flask(__name__)
        self._app.secret_key = "your_secret_key"

        self._app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
        self._app.config["SESSION_COOKIE_SECURE"] = False

        CORS(self._app, supports_credentials=True)

        self._auth_manager = AuthManager()
        self._study_manager = StudyManager()
        self._mood_manager = MoodManager()

        init_db()

        self._register_error_handlers()
        self._register_routes()

    def _register_error_handlers(self):
        @self._app.errorhandler(Exception)
        def handle_api_exception(error):
            if not request.path.startswith("/api/"):
                raise error

            if isinstance(error, HTTPException):
                return jsonify({"error": error.description}), error.code

            self._app.logger.exception("Unhandled API error on %s", request.path)
            return jsonify({"error": "Internal server error"}), 500

    def _get_user_id(self):
        """Returns (user_id, None) on success or (None, error_response) on failure."""
        user_id = session.get("user_id")
        if not user_id:
            return None, (jsonify({"error": "Unauthorized"}), 401)
        return user_id, None

    def _register_routes(self):
        frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

        @self._app.route("/")
        def index():
            return send_from_directory(frontend_dir, "index.html")

        @self._app.route("/favicon.ico")
        def favicon():
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "images")
            return send_from_directory(static_dir, "logo.png", mimetype="image/png")

        @self._app.route("/<path:filename>")
        def serve_frontend(filename):
            return send_from_directory(frontend_dir, filename)

        @self._app.route("/api/signup", methods=["POST"])
        def signup():
            self._app.logger.info("Signup request received")
            data = request.get_json()
            if not data:
                return jsonify({"error": "Request body must be JSON"}), 400

            username = data.get("username", "").strip().lower()
            password = data.get("password", "")
            gender = data.get("gender", "Not specified")
            field_of_interest = data.get("field_of_interest", "")
            study_goal = data.get("study_goal", "")

            try:
                age = int(data.get("age")) if data.get("age") else None
            except ValueError:
                return jsonify({"error": "Age must be a valid number"}), 400

            if not username or not password:
                return jsonify({"error": "Username and password are required"}), 400
            if age is not None and (age < 0 or age > 120):
                return jsonify({"error": "Invalid age"}), 400

            self._app.logger.info("Signup validated for username=%s", username)
            hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

            try:
                new_user_id = self._auth_manager.create_user(
                    username, hashed_pw, gender, age, field_of_interest, study_goal
                )
            except Exception as e:
                self._app.logger.exception("Signup failed while creating user username=%s", username)
                if "UNIQUE constraint" in str(e):
                    return jsonify({"error": "Username already exists"}), 409
                raise e

            self._app.logger.info("Signup succeeded for username=%s user_id=%s", username, new_user_id)
            return jsonify({
                "status": "success",
                "message": "Account created successfully",
                "user_id": new_user_id
            }), 201

        @self._app.route("/api/login", methods=["POST"])
        def login():
            data = request.get_json()
            if not data:
                return jsonify({"error": "Request body must be JSON"}), 400

            username = data.get("username", "").strip().lower()
            password = data.get("password", "")

            if not username or not password:
                return jsonify({"error": "Username and password are required"}), 400

            user = self._auth_manager.find_user_by_username(username)

            if user and bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
                session["user_id"] = user["user_id"]
                session["username"] = user["username"]
                return jsonify({
                    "status": "success",
                    "message": "Logged in successfully",
                    "user_id": user["user_id"]
                }), 200

            return jsonify({"error": "Username or Password Incorrect"}), 401

        @self._app.route("/api/logout", methods=["POST"])
        def logout():
            session.clear()
            return jsonify({"status": "success", "message": "Logged out successfully"}), 200

        @self._app.route("/api/me", methods=["GET"])
        def me():
            user_id, err = self._get_user_id()
            if err: return err

            return jsonify({"status": "success", "data": {"username": session.get("username")}}), 200

        @self._app.route("/api/courses", methods=["GET"])
        def get_courses():
            user_id, err = self._get_user_id()
            if err: return err

            courses = self._study_manager.get_courses(user_id)
            return jsonify({"status": "success", "data": courses}), 200

        @self._app.route("/api/courses", methods=["POST"])
        def create_course():
            user_id, err = self._get_user_id()
            if err: return err

            data = request.get_json()
            if not data or not data.get("course_name"):
                return jsonify({"error": "Course name is required"}), 400

            try:
                new_id = self._study_manager.add_course(user_id, data["course_name"])
            except ValueError as e:
                return jsonify({"error": str(e)}), 400

            return jsonify({"status": "success", "course_id": new_id}), 201

        @self._app.route("/api/sessions", methods=["POST"])
        def log_session():
            user_id, err = self._get_user_id()
            if err: return err

            data = request.get_json()
            required_fields = ["course_id", "start_time", "end_time", "goal_minutes", "actual_minutes", "task_type"]
            for field in required_fields:
                if field not in data:
                    return jsonify({"error": f"Missing required field: '{field}'"}), 400

            try:
                session_id = self._study_manager.save_study_session(user_id, data)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400

            return jsonify({"status": "success", "session_id": session_id}), 201

        @self._app.route("/api/sessions/history", methods=["GET"])
        def session_history():
            user_id, err = self._get_user_id()
            if err: return err

            limit = request.args.get("limit", default=20, type=int)
            history = self._study_manager.get_study_history(user_id, limit)
            return jsonify({"status": "success", "data": history}), 200

        @self._app.route("/api/analytics/weekly-study", methods=["GET"])
        def weekly_study_summary():
            user_id, err = self._get_user_id()
            if err: return err

            summary = self._study_manager.get_weekly_study_summary(user_id)
            return jsonify({"status": "success", "data": summary}), 200

        @self._app.route("/api/analytics/daily-hours", methods=["GET"])
        def daily_hours():
            user_id, err = self._get_user_id()
            if err: return err

            conn = self._study_manager._get_connection()
            cursor = conn.cursor()
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
            data = [{"day": r["day"], "hours": r["hours"]} for r in cursor.fetchall()]
            conn.close()
            return jsonify({"status": "success", "data": data}), 200

        @self._app.route("/api/analytics/daily-breakdown", methods=["GET"])
        def daily_breakdown():
            user_id, err = self._get_user_id()
            if err: return err

            breakdown = self._study_manager.get_daily_course_breakdown(user_id)
            return jsonify({"status": "success", "data": breakdown}), 200

        @self._app.route("/api/analytics/top-courses", methods=["GET"])
        def top_weekly_courses():
            user_id, err = self._get_user_id()
            if err: return err

            top = self._study_manager.get_weekly_top_course(user_id)
            return jsonify({"status": "success", "data": top}), 200

        @self._app.route("/api/dashboard/overview", methods=["GET"])
        def dashboard_overview():
            user_id, err = self._get_user_id()
            if err: return err

            streak = self._study_manager.get_streak(user_id)
            distribution = self._study_manager.get_study_distribution(user_id, days=7)
            suggestion = self._study_manager.get_smart_suggestion(user_id, days=7)

            return jsonify({
                "status": "success",
                "data": {
                    "streak": streak,
                    "pie_chart": distribution,
                    "smart_suggestion": suggestion
                }
            }), 200

        @self._app.route("/api/moods", methods=["POST"])
        def post_mood():
            user_id, err = self._get_user_id()
            if err: return err

            data = request.get_json()
            required_fields = ["exhaustion_score", "cynicism_score", "efficacy_score"]
            for field in required_fields:
                if field not in data:
                    return jsonify({"error": f"Missing required field: '{field}'"}), 400

            try:
                eval_id, risk_level = self._mood_manager.save_evaluation(user_id, data)
                retrain_model()

                global burnout_model
                burnout_model = joblib.load("burnout_model.pkl")
            except ValueError as e:
                return jsonify({"error": str(e)}), 400

            return jsonify({
                "status": "success",
                "evaluation_id": eval_id,
                "current_risk": risk_level  
            }), 201

        @self._app.route("/api/moods/burnout", methods=["GET"])
        def burnout_status():

            user_id, err = self._get_user_id()
            if err:
                return err
                
            if burnout_model is None:
                return jsonify({
                    "status": "success",
                    "data": {"label": "Not enough data"}
                }), 200

            training_rows = self._mood_manager.get_training_data(user_id)

            if not training_rows:
                return jsonify({
                    "status": "success",
                    "data": {"label": "Not enough data"}
                }), 200

            latest = training_rows[0]

            feature_vector = pd.DataFrame(
                [[latest[f] for f in feature_order]],
                columns=feature_order
            )

            prediction = burnout_model.predict(feature_vector)[0]

            label_map = {
                0: "Low risk",
                1: "Medium risk",
                2: "High risk"
            }

            return jsonify({
                "status": "success",
                "data": {
                    "label": label_map[prediction]
                }
            }), 200

        @self._app.route("/api/moods/history", methods=["GET"])
        def mood_history():
            user_id, err = self._get_user_id()
            if err: return err

            limit = request.args.get("limit", default=10, type=int)
            history = self._mood_manager.get_mood_history(user_id, limit)
            return jsonify({"status": "success", "data": history}), 200

        @self._app.route("/api/moods/summary/weekly", methods=["GET"])
        def weekly_mood_summary():
            user_id, err = self._get_user_id()
            if err: return err

            summary = self._mood_manager.get_weekly_mood_summary(user_id)
            return jsonify({"status": "success", "data": summary}), 200

        @self._app.route("/api/ml/training-data", methods=["GET"])
        def ml_dataset():
            user_id, err = self._get_user_id()
            if err: return err

            dataset = self._mood_manager.get_training_data(user_id)
            return jsonify({"status": "success", "data": dataset}), 200
        
        @self._app.route("/api/schedules", methods=["POST"])
        def create_schedule():
            user_id, err = self._get_user_id()
            if err: return err

            data = request.get_json()

            required=["course_id", "date"]
            for f in required :
                if f not in data:
                    return jsonify({"error" : f"Missing {f}"}), 400
                
            conn = self._study_manager._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO schedules (user_id, course_id, title, date, start_time, end_time)
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING schedule_id
            """, (
                user_id,
                data["course_id"],
                data.get("title", ""),
                data["date"],
                data.get("start_time"),
                data.get("end_time")
            ))

            inserted = cursor.fetchone()
            if isinstance(inserted, dict):
                schedule_id = inserted["schedule_id"]
            elif isinstance(inserted, (list, tuple)) and inserted:
                schedule_id = inserted[0]
            else:
                schedule_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return jsonify({"status": "success", "schedule_id": schedule_id}), 201
        
        @self._app.route("/api/schedules", methods=["GET"])
        def get_schedules():
            user_id, err = self._get_user_id()
            if err: return err

            conn = self._study_manager._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT s.*, c.course_name
                FROM schedules s
                JOIN courses c ON s.course_id = c.course_id
                WHERE s.user_id = ?
            """, (user_id,))

            data = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return jsonify({"status": "success", "data": data}), 200
        
        @self._app.route("/api/schedules/<int:schedule_id>", methods=["DELETE"])
        def delete_schedule(schedule_id):
            user_id, err = self._get_user_id()
            if err: return err

            conn = self._study_manager._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM schedules
                WHERE schedule_id = ? AND user_id = ?
            """, (schedule_id, user_id))

            conn.commit()
            conn.close()

            return jsonify({"status": "success"}), 200
        
        @self._app.route("/api/moods/should-trigger", methods=["GET"])
        def check_mood_trigger():

            user_id, err = self._get_user_id()
            if err:
                return err

            trigger = should_trigger_mood_form(user_id)

            return jsonify({
                "status": "success",
                "data": {
                "should_trigger": trigger
            }
            }), 200

    # --------------------------------------------------
    # ▶️ Run
    # --------------------------------------------------

    def run(self):
        port = int(os.environ.get("PORT", 5000))
        self._app.run(host="0.0.0.0", port=port, debug=False)

# Instantiate the controller globally so Gunicorn can access the Flask app object
controller = AppController()
app = controller._app

if __name__ == "__main__":
    controller.run()
