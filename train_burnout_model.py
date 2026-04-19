import sqlite3
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib

# -----------------------------
# STEP 1: เชื่อมเข้า DB ที่สร้าง
# -----------------------------
conn = sqlite3.connect("database.db")

# -----------------------------
# STEP 2: Extract training dataset
# (same-day study behavior + mood evaluation)
# -----------------------------
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
ON DATE(s.start_time) = DATE(m.evaluated_at)

GROUP BY DATE(s.start_time)
"""

df = pd.read_sql_query(query, conn)
conn.close()

# หยุดถ้าบ่มี data ให้เทรนโมเดล
if df.empty:
    print("No training data available yet.")
    exit()

# -----------------------------
# STEP 3: Create burnout score
# -----------------------------

df["burnout_score"] = (
    df["exhaustion_score"]
    + df["cynicism_score"]
    + (3 - df["efficacy_score"])
)

# -----------------------------
# STEP 4: Convert score → label
# -----------------------------
def classify(score):
    if score <= 3:
        return 0      # Low risk
    elif score <= 6:
        return 1      # Medium risk
    else:
        return 2      # High risk

df["burnout_level"] = df["burnout_score"].apply(classify)

# -----------------------------
# STEP 5: drop column ที่ไม่ใช้ออก ไม่ต้องการให้ model เห็น label จริง
# -----------------------------
df = df.drop(columns=[
    "date",
    "exhaustion_score",
    "cynicism_score",
    "efficacy_score",
    "burnout_score"
])

# -----------------------------
# STEP 6: spilit dataset เป็น train/test
# -----------------------------
X = df.drop("burnout_level", axis=1)
y = df["burnout_level"]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)

# -----------------------------
# STEP 7: Train model
# -----------------------------
model = RandomForestClassifier(n_estimators=100,random_state=42)
model.fit(X_train, y_train)


# -----------------------------
# STEP 8: เช็ค accuracy
# -----------------------------
predictions = model.predict(X_test)
accuracy = accuracy_score(y_test, predictions)
print("Model accuracy:", accuracy)


# -----------------------------
# STEP 9: ถุย trained model กับ feature_columns ออกมาเป็นไฟล์ .pkl
# -----------------------------
joblib.dump(model, "burnout_model.pkl")
# จำ feature order ด้วย เพราะตอน predict ต้องเรียงให้เหมือนตอน train
feature_columns = X.columns.tolist()
joblib.dump(feature_columns, "model_features.pkl")

print("Model saved as burnout_model.pkl")
print("Feature order saved as model_features.pkl")