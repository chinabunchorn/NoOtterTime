import sqlite3
from flask import Flask, request, render_template, redirect, url_for, session, flash
from datetime import datetime
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

@app.route("/", methods=["GET", "POST"])
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

    return f"Welcome {session['user']}"

#---------------------RUN-----------------------
if __name__ == "__main__":
    app.run(debug=True)