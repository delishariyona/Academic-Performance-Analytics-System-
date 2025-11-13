# frontend/dashboard.py
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import time

API_BASE = "http://localhost:5000/api"
st.set_page_config(page_title="APAS Dashboard", layout="wide")

# Session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None

def do_login():
    username = st.session_state.get("login_username")
    password = st.session_state.get("login_password")
    if not username or not password:
        st.error("Enter username and password.")
        return
    try:
        res = requests.post(f"{API_BASE}/login", json={"username": username, "password": password})
        if res.status_code == 200 and res.json().get("success"):
            st.session_state.logged_in = True
            st.session_state.role = res.json()["role"]
            st.session_state.username = res.json()["username"]
            st.success(f"Welcome, {st.session_state.username} ({st.session_state.role})")
            st.rerun()
        else:
            st.error("Invalid credentials.")
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

# Fetch settings (threshold & model version) once
def fetch_settings():
    try:
        r = requests.get(f"{API_BASE}/settings")
        if r.status_code == 200:
            return r.json()
    except:
        return {"risk_threshold": 0.6, "model_version": "1"}
settings = fetch_settings()
threshold = float(settings.get("risk_threshold", 0.6))
model_version = settings.get("model_version", "1")

# ----------------- STUDENT DASHBOARD -----------------
if role == "student":
    st.title("📊 Student Dashboard")
    st.info("View your performance, attendance, and predicted risk scores.")

    res = requests.get(f"{API_BASE}/student/{username}")
    if res.status_code == 200:
        df = pd.DataFrame(res.json())
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
        st.error("Failed to fetch student data.")

    # show alerts if any for this student
    a_res = requests.get(f"{API_BASE}/alerts")
    if a_res.status_code == 200:
        alerts = pd.DataFrame(a_res.json())
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
            res = requests.post(f"{API_BASE}/add_record", json={
                "student_name": sname, "marks": marks, "attendance": attendance,
                "course": course, "instructor": instructor
            })
            if res.status_code == 200 and res.json().get("success"):
                st.success(f"Added — risk {res.json()['risk_score']}")
            else:
                st.error(res.json().get("message", "Error"))

    st.markdown("---")
    st.subheader("📁 Bulk CSV Upload (student_name,marks,attendance,course)")
    csv_file = st.file_uploader("CSV", type=["csv"])
    if csv_file is not None:
        try:
            df = pd.read_csv(csv_file)
            st.dataframe(df.head())
            if st.button("Upload CSV to Backend"):
                records = df.to_dict(orient="records")
                res = requests.post(f"{API_BASE}/add_records", json={"records": records, "instructor": instructor})
                if res.status_code == 200 and res.json().get("success"):
                    st.success(f"Uploaded {res.json().get('processed')} valid records")
                else:
                    st.error("Upload failed")
        except Exception as e:
            st.error(f"Failed to read CSV: {e}")

    st.markdown("---")
    st.subheader("📊 My Class Records")
    r = requests.get(f"{API_BASE}/instructor/{instructor}")
    if r.status_code == 200:
        df = pd.DataFrame(r.json())
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

    # show alerts for this instructor's students
    a_res = requests.get(f"{API_BASE}/alerts")
    if a_res.status_code == 200:
        alerts = pd.DataFrame(a_res.json())
        if not alerts.empty:
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
    s_res = requests.get(f"{API_BASE}/settings")
    if s_res.status_code == 200:
        s = s_res.json()
        cur_thresh = float(s.get("risk_threshold", 0.6))
        cur_model = s.get("model_version", "1")
    else:
        cur_thresh = 0.6
        cur_model = "1"

    new_thresh = st.slider("Risk threshold (students with risk >= threshold generate alerts)", 0.0, 1.0, cur_thresh, 0.05)
    if st.button("Save Threshold"):
        r = requests.post(f"{API_BASE}/settings", json={"key": "risk_threshold", "value": str(new_thresh), "username": username})
        if r.status_code == 200 and r.json().get("success"):
            st.success("Threshold updated")
            time.sleep(0.3)
            st.rerun()
        else:
            st.error("Failed to update threshold")

    st.markdown(f"**Current model version:** {cur_model}")
    if st.button("Retrain (simulate) model"):
        rr = requests.post(f"{API_BASE}/retrain_model", json={"username": username})
        if rr.status_code == 200 and rr.json().get("success"):
            st.success(f"Model retrained to version {rr.json().get('model_version')}")
            st.rerun()
        else:
            st.error("Retrain failed")

    st.markdown("---")
    # analytics
    st.subheader("📈 Institution Analytics")
    res = requests.get(f"{API_BASE}/all_records")
    if res.status_code == 200:
        df = pd.DataFrame(res.json())
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
        st.error("Failed to load analytics")

    st.markdown("---")
    # alerts view
    st.subheader("🔔 Alerts (students above threshold)")
    a_res = requests.get(f"{API_BASE}/alerts")
    if a_res.status_code == 200:
        alerts_df = pd.DataFrame(a_res.json())
        if not alerts_df.empty:
            st.dataframe(alerts_df)
        else:
            st.info("No alerts")
    else:
        st.error("Failed to load alerts")

    st.markdown("---")
    # user management
    st.subheader("👥 User Management")
    users_res = requests.get(f"{API_BASE}/users")
    if users_res.status_code == 200:
        users_df = pd.DataFrame(users_res.json())
        if not users_df.empty:
            st.dataframe(users_df)
    else:
        st.error("Failed loading users")

    st.markdown("Create user")
    new_u = st.text_input("Username", key="admin_new_user")
    new_p = st.text_input("Password", type="password", key="admin_new_pass")
    new_r = st.selectbox("Role", ["student","instructor","admin"], index=0)
    if st.button("Create User"):
        if not new_u or not new_p:
            st.error("Provide username & password")
        else:
            cr = requests.post(f"{API_BASE}/users", json={"username": new_u, "password": new_p, "role": new_r})
            if cr.status_code == 200 and cr.json().get("success"):
                st.success("User created")
                st.rerun()
            else:
                st.error(f"Create failed: {cr.text}")

    st.markdown("---")
    # audit logs
    st.subheader("📜 Audit Log (recent)")
    al = requests.get(f"{API_BASE}/audit_logs")
    if al.status_code == 200:
        al_df = pd.DataFrame(al.json())
        if not al_df.empty:
            st.dataframe(al_df.head(200))
        else:
            st.info("No audit events")
    else:
        st.error("Failed to fetch audit logs")

    st.stop()
