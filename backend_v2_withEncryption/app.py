# backend/app.py
from flask import Flask, request, jsonify, session, abort
from flask_cors import CORS
from models import get_db
import os
from crypto import encrypt_value, decrypt_value, hmac_value
from config import TLS
import ssl
from ml_engine import predict_risk, get_model_version, rebuild_model
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
import json
import traceback

# ------------------- App + CORS / sessions config -------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = '127e4628cb846d2d1473092708ff211f7da769bc37dab3ee945293fea4f0d1c4'
# Set a secret key (in production use an env var)
# app.secret_key = "MY_SUPER_SECRET_KEY_123"
# ---- FIXED COOKIE SETTINGS FOR LOCALHOST ----
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False   # THIS LINE IS CRITICAL ON LOCALHOST
app.config['SESSION_COOKIE_SAMESITE'] = "Lax"
from flask_session import Session

app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# IMPORTANT: when supports_credentials=True you must NOT use origins="*" .
# We're explicitly allowing your Streamlit origin:
CORS(app,
     supports_credentials=True,
     origins=[
         "http://localhost:8501",
         "http://127.0.0.1:8501",
         "http://192.168.1.18:8501"
     ])

# ------------------- Utility functions -------------------
def require_role(allowed_roles):
    username = session.get("username")
    if not username:
        abort(401)  # Not logged in

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT role FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()
    db.close()

    if not user:
        abort(401)

    if user["role"] not in allowed_roles:
        abort(403)  # Forbidden

# optional: email
try:
    from email_service import send_alert_email
    EMAIL_AVAILABLE = True
except Exception:
    EMAIL_AVAILABLE = False

# PDF export libs
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# ------------------- DB helpers & audit -------------------
def ensure_tables():
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
    cur.execute("SELECT value FROM settings WHERE `key`='risk_threshold'")
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO settings (`key`,`value`) VALUES (%s,%s)", ("risk_threshold", "0.6"))
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

ensure_tables()

# ------------------- users helpers -------------------
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
    try:
        if stored_pw.startswith("pbkdf2:") or stored_pw.startswith("argon2:"):
            if check_password_hash(stored_pw, password):
                return user
        elif stored_pw == password:
            return user
    except Exception:
        return None
    return None

# ------------------- routes -------------------
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json() or {}
        username = data.get("username")
        password = data.get("password")

        user = fetch_user_record(username, password)
        if user:
            # set session
            session['username'] = user["username"]

            audit(username, "login", {"success": True})

            # IMPORTANT PART — build response manually
            resp = jsonify({
                "success": True,
                "role": user["role"],
                "username": user["username"]
            })

            # allow cookie to pass
            origin = request.headers.get("Origin")
            if origin:
                resp.headers["Access-Control-Allow-Credentials"] = "true"
                resp.headers["Access-Control-Allow-Origin"] = origin

            return resp

        else:
            audit(username or "unknown", "login", {"success": False})
            resp = jsonify({"success": False, "message": "Invalid credentials"})
            resp.status_code = 401

            origin = request.headers.get("Origin")
            if origin:
                resp.headers["Access-Control-Allow-Credentials"] = "true"
                resp.headers["Access-Control-Allow-Origin"] = origin

            return resp

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on login", "error": str(e)}), 500

@app.route('/api/add_record', methods=['POST'])
def add_record():
    require_role(["instructor"])
    try:
        data = request.get_json() or {}
        student_name = data.get("student_name")
        marks = data.get("marks", 0)
        attendance = data.get("attendance", 0)
        course = data.get("course", "")
        instructor = data.get("instructor", "")

        if not valid_student(student_name):
            audit(instructor or "unknown", "add_record", {"student": student_name, "status": "invalid_student"})
            return jsonify({"success": False, "message": f"'{student_name}' is not a valid student"}), 400

        try:
            marks = float(marks)
        except:
            marks = 0.0
        try:
            attendance = float(attendance)
        except:
            attendance = 0.0

        risk = predict_risk(marks, attendance)

        db = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO records (student_name, marks, attendance, risk_score, course, instructor_name)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (student_name, int(marks), int(attendance), float(risk), course[:200], instructor))
        rec_id = cur.lastrowid
        db.commit()
        cur.close()
        db.close()

        threshold = float(get_setting("risk_threshold", 0.6))
        if risk >= threshold:
            db2 = get_db()
            cur2 = db2.cursor()
            cur2.execute("INSERT INTO alerts (student_name, risk_score, record_id) VALUES (%s,%s,%s)",
                         (student_name, risk, rec_id))
            db2.commit()
            cur2.close()
            db2.close()

            if EMAIL_AVAILABLE:
                try:
                    send_alert_email(
                        to_email="savah19648@gyknife.com",
                        student_name=student_name,
                        risk_score=risk,
                        course=course,
                        instructor=instructor
                    )
                except Exception as e:
                    print("Email send failed:", e)

        audit(instructor or "unknown", "add_record", {"student": student_name, "risk": risk, "record_id": rec_id})
        return jsonify({"success": True, "risk_score": risk})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on add_record", "error": str(e)}), 500

@app.route('/api/add_records', methods=['POST'])
def add_records():
    require_role(["instructor"])
    try:
        data = request.get_json() or {}
        records = data.get("records", [])
        instructor = data.get("instructor", "")
        db = get_db()
        cur = db.cursor()
        processed = 0
        alerts = 0
        for rec in records:
            student_name = rec.get("student_name")
            if not student_name:
                continue
            marks = rec.get("marks", 0) or 0
            attendance = rec.get("attendance", 0) or 0
            course = rec.get("course", "") or ""
            if not valid_student(student_name):
                continue
            try:
                marks = float(marks)
            except:
                marks = 0.0
            try:
                attendance = float(attendance)
            except:
                attendance = 0.0
            risk = predict_risk(marks, attendance)
            cur.execute("""
                INSERT INTO records (student_name, marks, attendance, risk_score, course, instructor_name)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (student_name, int(marks), int(attendance), float(risk), course[:200], instructor))
            lastid = cur.lastrowid
            processed += 1
            if risk >= float(get_setting("risk_threshold", 0.6)):
                c2 = db.cursor()
                c2.execute("INSERT INTO alerts (student_name, risk_score, record_id) VALUES (%s,%s,%s)",
                           (student_name, risk, lastid))
                c2.close()
                alerts += 1
        db.commit()
        cur.close()
        db.close()
        audit(instructor or "unknown", "bulk_add_records", {"processed": processed, "alerts": alerts})
        return jsonify({"success": True, "processed": processed})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on add_records", "error": str(e)}), 500

@app.route('/api/student/<username>', methods=['GET'])
def student_data(username):
    require_role(["student"])
    if session.get("username") != username:
        abort(403)

    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("""
            SELECT course, marks, attendance, risk_score, instructor_name, timestamp, student_name
            FROM records
            WHERE student_name = %s
            ORDER BY timestamp DESC
        """, (username,))
        rows = cur.fetchall()
        cur.close()
        db.close()
        for r in rows:
            r['marks'] = float(r['marks']) if r.get('marks') is not None else None
            r['attendance'] = float(r['attendance']) if r.get('attendance') is not None else None
            r['risk_score'] = float(r['risk_score']) if r.get('risk_score') is not None else None
        return jsonify(rows)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on student_data", "error": str(e)}), 500

@app.route('/api/instructor/<username>', methods=['GET'])
def instructor_data(username):
    require_role(["instructor"])
    try:
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
        for r in rows:
            r['marks'] = float(r['marks']) if r.get('marks') is not None else None
            r['attendance'] = float(r['attendance']) if r.get('attendance') is not None else None
            r['risk_score'] = float(r['risk_score']) if r.get('risk_score') is not None else None
        return jsonify(rows)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on instructor_data", "error": str(e)}), 500

@app.route('/api/all_records', methods=['GET'])
def all_records():
    require_role(["admin"])
    try:
        db = get_db()
        df = pd.read_sql("SELECT * FROM records", db)
        db.close()
        if not df.empty:
            df['marks'] = df['marks'].astype(float)
            df['attendance'] = df['attendance'].astype(float)
            df['risk_score'] = df['risk_score'].astype(float)
        return df.to_json(orient='records')
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on all_records", "error": str(e)}), 500

@app.route('/api/export', methods=['GET'])
def export_csv():
    require_role(["admin"])
    try:
        db = get_db()
        df = pd.read_sql("SELECT * FROM records", db)
        df["student_alias"] = df["student_name"].apply(lambda x: f"sid_{abs(hash(x)) % 10000}")
        df.drop(columns=["student_name"], inplace=True)
        path = "report_anonymized.csv"
        df.to_csv(path, index=False)
        db.close()
        audit("admin", "export_report", {"path": path})
        return jsonify({"success": True, "path": path})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on export", "error": str(e)}), 500

@app.route('/api/export_pdf', methods=['GET'])
def export_pdf():
    require_role(["admin"])
    try:
        db = get_db()
        df = pd.read_sql("SELECT * FROM records", db)
        db.close()
        filename = "dashboard_report.pdf"
        doc = SimpleDocTemplate(filename, pagesize=A4)
        styles = getSampleStyleSheet()
        elems = []
        elems.append(Paragraph("APAS Dashboard Report", styles['Heading1']))
        data = [df.columns.tolist()] + df.astype(str).values.tolist()
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('FONT', (0,0), (-1,-1), 'Helvetica', 8)
        ]))
        elems.append(table)
        doc.build(elems)
        audit("admin", "export_pdf", {"path": filename})
        return jsonify({"success": True, "path": filename})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on export_pdf", "error": str(e)}), 500

@app.route('/api/alerts', methods=['GET'])
def list_alerts():
    # Alerts should be visible to admin and instructor; students will only see alerts filtered on frontend
    try:
        # allow instructors & admin; allow students to fetch (they get filtered client-side)
        username = session.get("username")
        if not username:
            abort(401)
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT id, student_name, risk_score, record_id, created_at FROM alerts ORDER BY created_at DESC")
        rows = cur.fetchall()
        cur.close()
        db.close()
        return jsonify(rows)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on alerts", "error": str(e)}), 500

@app.route('/api/audit_logs', methods=['GET'])
def get_audit_logs():
    require_role(["admin"])
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT id, event_time, username, action, details FROM audit_log ORDER BY event_time DESC LIMIT 500")
        rows = cur.fetchall()
        cur.close()
        db.close()
        return jsonify(rows)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on audit_logs", "error": str(e)}), 500

@app.route('/api/settings', methods=['GET'])
def settings_get():
    # Settings are admin only for reading/updating in UI; but we'll allow authenticated users to read threshold
    username = session.get("username")
    if not username:
        abort(401)
    try:
        # let everyone view threshold so student UI can show it
        threshold = float(get_setting("risk_threshold", 0.6))
        model_version = get_setting("model_version", "1")
        return jsonify({"risk_threshold": threshold, "model_version": model_version})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on settings", "error": str(e)}), 500

@app.route('/api/settings', methods=['POST'])
def settings_post():
    require_role(["admin"])
    try:
        data = request.get_json() or {}
        key = data.get("key")
        value = data.get("value")
        if not key:
            return jsonify({"success": False, "message": "key required"}), 400
        set_setting(key, value)
        audit(data.get("username", "admin"), "update_setting", {"key": key, "value": value})
        return jsonify({"success": True, "key": key, "value": value})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on settings_post", "error": str(e)}), 500

@app.route('/api/retrain_model', methods=['POST'])
def retrain_model():
    require_role(["admin"])
    try:
        data = request.get_json() or {}
        user = data.get("username", "admin")
        rebuild_model()
        cur_ver = int(get_setting("model_version", "1"))
        new_ver = cur_ver + 1
        set_setting("model_version", str(new_ver))
        audit(user, "retrain_model", {"new_version": new_ver})
        return jsonify({"success": True, "model_version": str(new_ver)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on retrain_model", "error": str(e)}), 500

@app.route('/api/users', methods=['GET'])
def list_users():
    require_role(["admin"])
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT id, username, role FROM users ORDER BY id")
        rows = cur.fetchall()
        cur.close()
        db.close()
        return jsonify(rows)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on users", "error": str(e)}), 500

@app.route('/api/users', methods=['POST'])
def create_user():
    require_role(["admin"])
    try:
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
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Server error on create_user", "error": str(e)}), 500

# useful debug endpoint
@app.route("/api/debug", methods=["GET"])
def debug():
    return jsonify({
        "session_username": session.get("username"),
        "cookies_received": {k: v for k, v in request.cookies.items()}
    })

if __name__ == "__main__":
    # run without debug so flask won't return HTML debug pages on exception (that caused JSON decode errors)
    # Enforce TLS 1.2+ by building an SSLContext
    cert = TLS.get('CERT_PATH')
    key = TLS.get('KEY_PATH')
    if cert and key and (os.path.exists(cert) and os.path.exists(key)):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        # require TLS 1.2 or newer
        try:
            context.minimum_version = ssl.TLSVersion.TLSv1_2
        except AttributeError:
            # older Python: disable older protocols
            context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        context.load_cert_chain(certfile=cert, keyfile=key)
        app.run(host='0.0.0.0', port=5000, debug=False, ssl_context=context)
    else:
        # fallback to plain HTTP but print a warning
        print("WARNING: TLS cert/key not found. Running without TLS. Set TLS paths in config or create dev certs in ./secrets/")
        app.run(port=5000, debug=False)
