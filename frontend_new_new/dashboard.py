# frontend/dashboard.py
import streamlit as st
import requests
import urllib3
import pandas as pd
import plotly.express as px
import time

API_BASE = "https://localhost:5000/api"
# Development: disable insecure warnings for self-signed certs
VERIFY_SSL = False
if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="APAS Dashboard", layout="wide")

# Session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None

# persistent requests.Session so cookies (session) are preserved across requests
def get_requests_session():
    if "requests_session" not in st.session_state:
        s = requests.Session()
        s.verify = VERIFY_SSL
        st.session_state.requests_session = s
    return st.session_state.requests_session

# create session early so it's available to login and subsequent calls
sess = get_requests_session()

def safe_json(res):
    """
    Try to parse JSON, but return fallback dict/text if the backend responded with non-JSON
    """
    try:
        return res.json()
    except Exception:
        # not JSON - return text wrapper
        return {"success": False, "message": res.text or "Non-JSON response", "status_code": res.status_code}

def do_login():
    username = st.session_state.get("login_username")
    password = st.session_state.get("login_password")
    if not username or not password:
        st.error("Enter username and password.")
        return
    try:
        s = get_requests_session()
        res = s.post(f"{API_BASE}/login", json={"username": username, "password": password}, timeout=10)
        data = safe_json(res)
        if res.status_code == 200 and data.get("success"):
            st.session_state.logged_in = True
            st.session_state.role = data["role"]
            st.session_state.username = data["username"]
            st.success(f"Welcome, {st.session_state.username} ({st.session_state.role})")
            st.rerun()
        else:
            st.error(data.get("message", "Invalid credentials."))
    except Exception as e:
        st.error(f"Connection error: {e}")

# Login screen
if not st.session_state.logged_in:
    st.title("🎓 APAS - Academic Performance Analytics System")
    st.subheader("Login")
    st.text_input("Username", key="login_username")
    st.text_input("Password", type="password", key="login_password")
    st.button("Login", on_click=do_login)
    st.markdown("**Demo accounts:** admin/adminpass, instructor1/instructorpass, student1/studentpass")
    st.stop()

# Logout
if st.button("Logout"):
    st.session_state.clear()
    st.rerun()

role = st.session_state.role
username = st.session_state.username
st.sidebar.title("Navigation")
st.sidebar.write(f"👤 {username} ({role})")

import time

SESSION_TIMEOUT = 900   # 15 mins

# TRACK SESSION TIME
if "last_active" not in st.session_state:
    st.session_state.last_active = time.time()
else:
    if time.time() - st.session_state.last_active > SESSION_TIMEOUT:
        st.warning("Session expired. Please login again.")
        st.session_state.clear()
        st.rerun()

# update activity timestamp
st.session_state.last_active = time.time()

# Fetch settings (threshold & model version) once
def fetch_settings():
    try:
        s = get_requests_session()
        r = s.get(f"{API_BASE}/settings", timeout=10)
        data = safe_json(r)
        if r.status_code == 200:
            return data
    except:
        pass
    return {"risk_threshold": 0.6, "model_version": "1"}

settings = fetch_settings()
threshold = float(settings.get("risk_threshold", 0.6))
model_version = settings.get("model_version", "1")

# ----------------- STUDENT DASHBOARD -----------------
if role == "student":
    st.title("📊 Student Dashboard")
    st.info("View your performance, attendance, and predicted risk scores.")

    s = get_requests_session()
    res = s.get(f"{API_BASE}/student/{username}", timeout=10)
    data = safe_json(res)
    if res.status_code == 200:
        df = pd.DataFrame(data)
        if not df.empty:
            st.dataframe(df[['course','marks','attendance','risk_score','instructor_name','timestamp']])
            fig = px.bar(df, x="course", y="risk_score", color="risk_score", title="Risk by Course")
            st.plotly_chart(fig, use_container_width=True)
            avg_risk = round(df['risk_score'].mean(), 2)
            st.markdown(f"**Average risk:** {avg_risk}  (threshold = {threshold})")
            if avg_risk >= threshold:
                st.error(f"⚠️ High risk! Your average risk {avg_risk} ≥ threshold {threshold}")
            elif avg_risk >= 0.4:
                st.warning(f"Moderate risk: {avg_risk}")
            else:
                st.success("Low risk — keep it up!")
        else:
            st.info("No records found for you. Contact your instructor.")
    else:
        st.error(data.get("message", "Failed to fetch student data."))

    # show alerts if any for this student
    a_res = s.get(f"{API_BASE}/alerts", timeout=10)
    a_data = safe_json(a_res)
    if a_res.status_code == 200:
        alerts = pd.DataFrame(a_data)
        if not alerts.empty:
            my_alerts = alerts[alerts['student_name'] == username]
            if not my_alerts.empty:
                st.markdown("### 🔔 Alerts")
                st.dataframe(my_alerts[['student_name','risk_score','created_at']])
    st.stop()

# ----------------- INSTRUCTOR DASHBOARD -----------------
if role == "instructor":
    st.title("🧑‍🏫 Instructor Dashboard")
    st.info("Upload and monitor student performance data for your courses.")
    instructor = username

    st.subheader("➕ Add Single Record")
    with st.form("single"):
        sname = st.text_input("Student Username")
        marks = st.number_input("Marks", 0, 100)
        attendance = st.number_input("Attendance (%)", 0, 100)
        course = st.text_input("Course")
        submitted = st.form_submit_button("Add")
        if submitted:
            s = get_requests_session()
            res = s.post(f"{API_BASE}/add_record", json={
                "student_name": sname, "marks": marks, "attendance": attendance,
                "course": course, "instructor": instructor
            }, timeout=10)
            data = safe_json(res)
            if res.status_code == 200 and data.get("success"):
                st.success(f"Added — risk {data['risk_score']}")
            else:
                st.error(data.get("message", "Error"))

    st.markdown("---")
    st.subheader("📁 Bulk CSV Upload (student_name,marks,attendance,course)")
    csv_file = st.file_uploader("CSV", type=["csv"])
    if csv_file is not None:
        try:
            df = pd.read_csv(csv_file)
            st.dataframe(df.head())
            if st.button("Upload CSV to Backend"):
                records = df.to_dict(orient="records")
                s = get_requests_session()
                res = s.post(f"{API_BASE}/add_records", json={"records": records, "instructor": instructor}, timeout=30)
                data = safe_json(res)
                if res.status_code == 200 and data.get("success"):
                    st.success(f"Uploaded {data.get('processed')} valid records")
                else:
                    st.error(data.get("message", "Upload failed"))
        except Exception as e:
            st.error(f"Failed to read CSV: {e}")

    st.markdown("---")
    st.subheader("📊 My Class Records")
    s = get_requests_session()
    r = s.get(f"{API_BASE}/instructor/{instructor}", timeout=10)
    rdata = safe_json(r)
    if r.status_code == 200:
        df = pd.DataFrame(rdata)
        if not df.empty:
            st.dataframe(df)
            c1, c2 = st.columns(2)
            with c1:
                fig = px.scatter(df, x="marks", y="attendance", color="risk_score", title="Marks vs Attendance")
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                fig2 = px.histogram(df, x="risk_score", nbins=10, title="Risk Distribution")
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No class data yet.")
    else:
        st.error(rdata.get("message", "Failed to load class data."))

    # show alerts for this instructor's students
    a_res = s.get(f"{API_BASE}/alerts", timeout=10)
    a_data = safe_json(a_res)
    if a_res.status_code == 200:
        alerts = pd.DataFrame(a_data)
        if not alerts.empty and 'student_name' in alerts.columns:
            my_alerts = alerts[alerts['student_name'].isin(df['student_name'].tolist() if not df.empty else [])]
            if not my_alerts.empty:
                st.markdown("### 🔔 Class Alerts (risk >= threshold)")
                st.dataframe(my_alerts[['student_name','risk_score','created_at']])

    st.stop()

# ----------------- ADMIN DASHBOARD -----------------
if role == "admin":
    st.title("🧑‍💼 Admin Dashboard")
    st.info("Institution overview, settings, alerts and user management.")
    # settings
    st.subheader("⚙️ System Settings")
    s = get_requests_session()
    s_res = s.get(f"{API_BASE}/settings", timeout=10)
    s_data = safe_json(s_res)
    if s_res.status_code == 200:
        s = s_data
        cur_thresh = float(s.get("risk_threshold", 0.6))
        cur_model = s.get("model_version", "1")
    else:
        cur_thresh = 0.6
        cur_model = "1"

    new_thresh = st.slider("Risk threshold (students with risk >= threshold generate alerts)", 0.0, 1.0, cur_thresh, 0.05)
    if st.button("Save Threshold"):
        s = get_requests_session()
        r = s.post(f"{API_BASE}/settings", json={"key": "risk_threshold", "value": str(new_thresh), "username": username})
        d = safe_json(r)
        if r.status_code == 200 and d.get("success"):
            st.success("Threshold updated")
            time.sleep(0.3)
            st.rerun()
        else:
            st.error(d.get("message", "Failed to update threshold"))

    st.markdown(f"**Current model version:** {cur_model}")
    if st.button("Retrain (simulate) model"):
        s = get_requests_session()
        rr = s.post(f"{API_BASE}/retrain_model", json={"username": username}, timeout=30)
        rd = safe_json(rr)
        if rr.status_code == 200 and rd.get("success"):
            st.success(f"Model retrained to version {rd.get('model_version')}")
            st.rerun()
        else:
            st.error(rd.get("message", "Retrain failed"))

    st.markdown("---")
    # analytics
    st.subheader("📈 Institution Analytics")
    s = get_requests_session()
    res = s.get(f"{API_BASE}/all_records", timeout=30)
    rdata = safe_json(res)
    if res.status_code == 200:
        df = pd.DataFrame(rdata)
        if not df.empty:
            total_students = df['student_name'].nunique()
            avg_marks = df['marks'].mean()
            avg_att = df['attendance'].mean()
            at_risk = len(df[df['risk_score'] >= new_thresh])
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Students", total_students)
            c2.metric("Avg Marks", f"{avg_marks:.2f}")
            c3.metric("Avg Attendance", f"{avg_att:.2f}%")
            c4.metric("At-Risk Records", at_risk)
            fig = px.histogram(df, x="risk_score", nbins=10, title="Risk Distribution")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No records available")
    else:
        st.error(rdata.get("message", "Failed to load analytics"))

    st.markdown("---")
    #export to pdf
    if st.button("Export Dashboard PDF"):
        s = get_requests_session()
        r = s.get(f"{API_BASE}/export_pdf", timeout=30)
        d = safe_json(r)
        if r.status_code == 200 and d.get("success"):
            st.success("PDF generated: " + d.get("path"))
        else:
            st.error(d.get("message", "PDF export failed") + " - " + str(d.get("error", "")))

    if st.button("Export Anonymized CSV"):
        r = s.get(f"{API_BASE}/export", timeout=30)
        d = safe_json(r)
        if r.status_code == 200 and d.get("success"):
            st.success("CSV generated: " + d.get("path"))
        else:
            st.error(d.get("message", "CSV export failed") + " - " + str(d.get("error", "")))

    st.markdown("---")
    # alerts view
    st.subheader("🔔 Alerts (students above threshold)")
    a_res = s.get(f"{API_BASE}/alerts", timeout=10)
    a_data = safe_json(a_res)
    if a_res.status_code == 200:
        alerts_df = pd.DataFrame(a_data)
        if not alerts_df.empty:
            st.dataframe(alerts_df)
        else:
            st.info("No alerts")
    else:
        st.error(a_data.get("message", "Failed to load alerts"))

    st.markdown("---")
    # user management
    st.subheader("👥 User Management")
    users_res = s.get(f"{API_BASE}/users", timeout=10)
    users_data = safe_json(users_res)
    if users_res.status_code == 200:
        users_df = pd.DataFrame(users_data)
        if not users_df.empty:
            st.dataframe(users_df)
    else:
        st.error(users_data.get("message", "Failed loading users"))

    st.markdown("Create user")
    new_u = st.text_input("Username", key="admin_new_user")
    new_p = st.text_input("Password", type="password", key="admin_new_pass")
    new_r = st.selectbox("Role", ["student","instructor","admin"], index=0)
    if st.button("Create User"):
        if not new_u or not new_p:
            st.error("Provide username & password")
        else:
            cr = s.post(f"{API_BASE}/users", json={"username": new_u, "password": new_p, "role": new_r}, timeout=10)
            cdata = safe_json(cr)
            if cr.status_code == 200 and cdata.get("success"):
                st.success("User created")
                st.rerun()
            else:
                st.error(f"Create failed: {cdata.get('message', cr.text)}")

    st.markdown("---")
    # audit logs
    st.subheader("📜 Audit Log (recent)")
    al = s.get(f"{API_BASE}/audit_logs", timeout=10)
    al_data = safe_json(al)
    if al.status_code == 200:
        al_df = pd.DataFrame(al_data)
        if not al_df.empty:
            st.dataframe(al_df.head(200))
        else:
            st.info("No audit events")
    else:
        st.error(al_data.get("message", "Failed to fetch audit logs"))

    st.stop()
