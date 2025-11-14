# backend/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from models import get_db
from ml_engine import predict_risk, get_model_version, rebuild_model
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import json

app = Flask(__name__)
CORS(app)

# -------------------------
# DB INIT / UTILS
# -------------------------
def ensure_tables():
    """
    Create supplemental tables used by new features:
    - settings (key,value)
    - audit_log (id, time, user, action, details)
    - alerts (id, student_name, risk_score, record_id, created_at)
    """
    db = get_db()
    cur = db.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        `key` VARCHAR(100) PRIMARY KEY,
        `value` VARCHAR(255)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        username VARCHAR(100),
        action VARCHAR(100),
        details TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_name VARCHAR(100),
        risk_score FLOAT,
        record_id INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    # default threshold if not present
    cur.execute("SELECT value FROM settings WHERE `key`='risk_threshold'")
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO settings (`key`,`value`) VALUES (%s,%s)", ("risk_threshold", "0.6"))
    # model version
    cur.execute("SELECT value FROM settings WHERE `key`='model_version'")
    mv = cur.fetchone()
    if not mv:
        cur.execute("INSERT INTO settings (`key`,`value`) VALUES (%s,%s)", ("model_version", "1"))
    db.commit()
    cur.close()
    db.close()

def get_setting(key, default=None):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT value FROM settings WHERE `key`=%s", (key,))
    r = cur.fetchone()
    cur.close()
    db.close()
    return r[0] if r else default

def set_setting(key, value):
    db = get_db()
    cur = db.cursor()
    cur.execute("REPLACE INTO settings (`key`,`value`) VALUES (%s,%s)", (key, str(value)))
    db.commit()
    cur.close()
    db.close()

def audit(username, action, details=""):
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO audit_log (username, action, details) VALUES (%s,%s,%s)",
                (username, action, json.dumps(details) if not isinstance(details, str) else details))
    db.commit()
    cur.close()
    db.close()

# ensure tables exist at startup
ensure_tables()

# ================================
# UTILITY FUNCTIONS (existing)
# ================================
def get_user(username):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cur.fetchone()
    cur.close()
    db.close()
    return user

def valid_student(student_name):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE username=%s AND role='student'", (student_name,))
    count = cur.fetchone()[0]
    cur.close()
    db.close()
    return count > 0

def fetch_user_record(username, password):
    user = get_user(username)
    if not user:
        return None
    stored_pw = user.get("password") or ""
    if stored_pw.startswith("pbkdf2:") or stored_pw.startswith("argon2:"):
        if check_password_hash(stored_pw, password):
            return user
    elif stored_pw == password:
        return user
    return None

# ================================
# LOGIN
# ================================
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")

    user = fetch_user_record(username, password)
    if user:
        audit(username, "login", {"success": True})
        return jsonify({"success": True, "role": user["role"], "username": user["username"]})
    else:
        audit(username or "unknown", "login", {"success": False})
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

# ================================
# ADD SINGLE RECORD
# ================================
@app.route('/api/add_record', methods=['POST'])
def add_record():
    data = request.get_json() or {}
    student_name = data.get("student_name")
    marks = data.get("marks", 0)
    attendance = data.get("attendance", 0)
    course = data.get("course", "")
    instructor = data.get("instructor", "")

    if not valid_student(student_name):
        audit(instructor or "unknown", "add_record", {"student": student_name, "status": "invalid_student"})
        return jsonify({"success": False, "message": f"'{student_name}' is not a valid student"}), 400

    risk = predict_risk(marks, attendance)

    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO records (student_name, marks, attendance, risk_score, course, instructor_name)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (student_name, marks, attendance, risk, course, instructor))
    rec_id = cur.lastrowid
    db.commit()
    cur.close()
    db.close()

    # create alert if above threshold
    threshold = float(get_setting("risk_threshold", 0.6))
    if risk >= threshold:
        db = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO alerts (student_name, risk_score, course, instructor_name)
            VALUES (%s, %s, %s, %s)
        """, (student_name, risk, course, instructor))
        db.commit()
        cur.close()
        db.close()

    audit(instructor or "unknown", "add_record", {"student": student_name, "risk": risk, "record_id": rec_id})
    return jsonify({"success": True, "risk_score": risk})

# ================================
# ADD MULTIPLE RECORDS (CSV)
# ================================
@app.route('/api/add_records', methods=['POST'])
def add_records():
    data = request.get_json() or {}
    records = data.get("records", [])
    instructor = data.get("instructor", "")

    db = get_db()
    cur = db.cursor()
    inserted_count = 0
    created_alerts = 0

    for rec in records:
        student_name = rec.get("student_name")
        if not student_name:
            continue
        marks = rec.get("marks", 0) or 0
        attendance = rec.get("attendance", 0) or 0
        course = rec.get("course", "")

        if not valid_student(student_name):
            continue  # skip invalid students

        risk = predict_risk(marks, attendance)

        # store record
        cur.execute("""
            INSERT INTO records (student_name, marks, attendance, risk_score, course, instructor_name)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (student_name, marks, attendance, risk, course, instructor))

        inserted_count += 1

        # CREATE ALERT if risk ≥ threshold
        threshold = float(get_setting("risk_threshold", 0.6))
        if risk >= threshold:
            cur2 = db.cursor()
            cur2.execute("""
                INSERT INTO alerts (student_name, risk_score, course, instructor_name)
                VALUES (%s, %s, %s, %s)
            """, (student_name, risk, course, instructor))
            cur2.close()
            created_alerts += 1

    db.commit()
    cur.close()
    db.close()

    audit(instructor or "unknown", "bulk_add_records", {"processed": inserted_count, "alerts": created_alerts})
    return jsonify({"success": True, "processed": inserted_count})

# ================================
# STUDENT DASHBOARD DATA
# ================================
@app.route('/api/student/<username>', methods=['GET'])
def student_data(username):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT course, marks, attendance, risk_score, instructor_name, timestamp
        FROM records
        WHERE student_name = %s
        ORDER BY timestamp DESC
    """, (username,))
    rows = cur.fetchall()
    cur.close()
    db.close()
    return jsonify(rows)


# ================================
# INSTRUCTOR DASHBOARD DATA
# ================================
@app.route('/api/instructor/<username>', methods=['GET'])
def instructor_data(username):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT id, student_name, marks, attendance, risk_score, course, timestamp
        FROM records
        WHERE instructor_name = %s
        ORDER BY timestamp DESC
    """, (username,))
    rows = cur.fetchall()
    cur.close()
    db.close()
    return jsonify(rows)


# ================================
# ADMIN DASHBOARD DATA
# ================================
@app.route('/api/all_records', methods=['GET'])
def all_records():
    db = get_db()
    df = pd.read_sql("SELECT * FROM records", db)
    db.close()
    return df.to_json(orient='records')


# ================================
# EXPORT ANONYMIZED REPORT (ADMIN)
# ================================
@app.route('/api/export', methods=['GET'])
def export_csv():
    db = get_db()
    df = pd.read_sql("SELECT * FROM records", db)

    df["student_alias"] = df["student_name"].apply(lambda x: f"sid_{abs(hash(x)) % 10000}")
    df.drop(columns=["student_name"], inplace=True)

    path = "report_anonymized.csv"
    df.to_csv(path, index=False)
    db.close()

    audit("admin", "export_report", {"path": path})
    return jsonify({"success": True, "path": path})


# ================================
# ALERTS & AUDIT ENDPOINTS
# ================================
@app.route('/api/alerts', methods=['GET'])
def list_alerts():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT id, student_name, risk_score, record_id, created_at FROM alerts ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    db.close()
    return jsonify(rows)

@app.route('/api/audit_logs', methods=['GET'])
def get_audit_logs():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT id, event_time, username, action, details FROM audit_log ORDER BY event_time DESC LIMIT 500")
    rows = cur.fetchall()
    cur.close()
    db.close()
    return jsonify(rows)


# ================================
# SETTINGS ENDPOINTS (risk threshold & model version)
# ================================
@app.route('/api/settings', methods=['GET'])
def settings_get():
    threshold = float(get_setting("risk_threshold", 0.6))
    model_version = get_setting("model_version", "1")
    return jsonify({"risk_threshold": threshold, "model_version": model_version})

@app.route('/api/settings', methods=['POST'])
def settings_post():
    data = request.get_json() or {}
    key = data.get("key")
    value = data.get("value")
    if not key:
        return jsonify({"success": False, "message": "key required"}), 400
    set_setting(key, value)
    audit(data.get("username", "admin"), "update_setting", {"key": key, "value": value})
    return jsonify({"success": True, "key": key, "value": value})


# ================================
# LMS INGEST SIMULATION
# ================================
@app.route('/api/ingest_lms', methods=['POST'])
def ingest_lms():
    """
    Simulate LMS ingestion. Accepts JSON: {"records":[...], "instructor":"instructor1"}
    """
    data = request.get_json() or {}
    records = data.get("records", [])
    instructor = data.get("instructor", "")
    # Reuse add_records logic partially
    db = get_db()
    cur = db.cursor()
    inserted = 0
    for rec in records:
        s = rec.get("student_name")
        if not s or not valid_student(s):
            continue
        marks = rec.get("marks", 0)
        attendance = rec.get("attendance", 0)
        course = rec.get("course", "")
        risk = predict_risk(marks, attendance)
        cur.execute("""
            INSERT INTO records (student_name, marks, attendance, risk_score, course, instructor_name)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (s, marks, attendance, risk, course, instructor))
        lastid = cur.lastrowid
        inserted += 1
        threshold = float(get_setting("risk_threshold", 0.6))
        if risk >= threshold:
            cur2 = db.cursor()
            cur2.execute("INSERT INTO alerts (student_name, risk_score, record_id) VALUES (%s,%s,%s)", (s, risk, lastid))
            cur2.close()
    db.commit()
    cur.close()
    db.close()
    audit(instructor or "system", "ingest_lms", {"processed": inserted})
    return jsonify({"success": True, "processed": inserted})


# ================================
# MODEL RETRAIN / VERSION (SIMULATION)
# ================================
@app.route('/api/retrain_model', methods=['POST'])
def retrain_model():
    """
    Simulated retrain: call rebuild_model() from ml_engine,
    increment model_version setting and record audit.
    """
    # optional: accept 'username' to record who triggered retrain
    data = request.get_json() or {}
    user = data.get("username", "admin")
    # Call ml_engine to rebuild model (in our deterministic engine this may toggle version)
    rebuild_model()
    # bump version in settings
    cur_ver = int(get_setting("model_version", "1"))
    new_ver = cur_ver + 1
    set_setting("model_version", str(new_ver))
    audit(user, "retrain_model", {"new_version": new_ver})
    return jsonify({"success": True, "model_version": str(new_ver)})


# ================================
# USER MANAGEMENT (ADMIN)
# ================================
@app.route('/api/users', methods=['GET'])
def list_users():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT id, username, role FROM users ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    db.close()
    return jsonify(rows)


@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    role = data.get("role", "student")

    if not username or not password or role not in ("student", "instructor", "admin"):
        return jsonify({"success": False, "message": "Invalid data"}), 400

    hashed = generate_password_hash(password)
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                    (username, hashed, role))
        db.commit()
    except Exception as e:
        db.rollback()
        cur.close()
        db.close()
        return jsonify({"success": False, "message": str(e)}), 400

    cur.close()
    db.close()
    audit(username, "create_user", {"role": role})
    return jsonify({"success": True, "username": username, "role": role})


# ================================
# MAIN
# ================================
if __name__ == "__main__":
    app.run(port=5000, debug=True)
