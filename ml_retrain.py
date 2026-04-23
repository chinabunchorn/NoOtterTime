import libsql_experimental as sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib
from database import get_connection


def retrain_model():

    conn = get_connection()

    query = """
    SELECT 
        DATE(s.start_time) as date,
        SUM(s.actual_minutes) as total_minutes,
        SUM(s.actual_minutes - s.goal_minutes) as overwork_minutes,
        COUNT(s.session_id) as session_count,
        AVG(m.exhaustion_score) as exhaustion_score,
        AVG(m.cynicism_score) as cynicism_score,
        AVG(m.efficacy_score) as efficacy_score
    FROM study_sessions s

    JOIN mood_evaluations m
    ON DATE(s.start_time) <= DATE(m.evaluated_at)

    GROUP BY DATE(s.start_time)
    """

    df = pd.read_sql_query(query, conn)
    conn.close()


    df["burnout_score"] = (
        df["exhaustion_score"]
        + df["cynicism_score"]
        + (3 - df["efficacy_score"])
    )

    def classify(score):
        if score <= 3:
            return 0
        elif score <= 6:
            return 1
        else:
            return 2

    df["burnout_level"] = df["burnout_score"].apply(classify)

    df = df.drop(columns=[
        "date",
        "exhaustion_score",
        "cynicism_score",
        "efficacy_score",
        "burnout_score"
    ])

    X = df.drop("burnout_level", axis=1)
    y = df["burnout_level"]

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)

    joblib.dump(model, "burnout_model.pkl")
    joblib.dump(X.columns.tolist(), "model_features.pkl")

    print("Model retrained successfully")