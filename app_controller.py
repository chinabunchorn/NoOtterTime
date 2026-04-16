import sqlite3
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import bcrypt

from managers import StudyManager, MoodManager, AuthManager
from database import init_db  


class AppController:
    def __init__(self, db_path="database.db"):
        self._app = Flask(__name__)
        self._app.secret_key = "your_secret_key"
        CORS(self._app, supports_credentials=True)

        self._auth_manager = AuthManager(db_path)
        self._study_manager = StudyManager(db_path)
        self._mood_manager = MoodManager(db_path)

        init_db()

        self._register_routes()

    def _get_user_id(self):
        """Returns (user_id, None) on success or (None, error_response) on failure."""
        user_id = session.get("user_id")
        if not user_id:
            return None, (jsonify({"error": "Unauthorized"}), 401)
        return user_id, None

    def _register_routes(self):

        @self._app.route("/api/signup", methods=["POST"])
        def signup():
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

            hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

            try:
                new_user_id = self._auth_manager.create_user(
                    username, hashed_pw, gender, age, field_of_interest, study_goal
                )
            except sqlite3.IntegrityError:
                return jsonify({"error": "Username already exists"}), 409

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
            except ValueError as e:
                return jsonify({"error": str(e)}), 400

            return jsonify({
                "status": "success",
                "evaluation_id": eval_id,
                "current_risk": risk_level  
            }), 201

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

    # --------------------------------------------------
    # ▶️ Run
    # --------------------------------------------------

    def run(self):
        self._app.run(debug=True)


if __name__ == "__main__":
    controller = AppController()
    controller.run()