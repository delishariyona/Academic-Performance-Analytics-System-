import os
import time
import requests
import smtplib
import importlib
import subprocess
import pytest

# Load backend app module
import sys, os as _os
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), '..'))
BACKEND_DIR = _os.path.join(ROOT, 'backend_v2_withEncryption_withRoles')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
import importlib.util
spec = importlib.util.spec_from_file_location('backend_app', os.path.join(BACKEND_DIR, 'app.py'))
backend_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_mod)
app = backend_mod.app


def ensure_mailhog_running():
    # Start MailHog if not running
    try:
        r = requests.get('http://127.0.0.1:8025/health')
        if r.status_code == 200:
            return True
    except Exception:
        pass
    # try to start docker container
    try:
        subprocess.run(['docker', 'run', '--rm', '-d', '--name', 'mailhog-test', '-p', '1025:1025', '-p', '8025:8025', 'mailhog/mailhog'], check=True)
        # wait
        for _ in range(10):
            try:
                r = requests.get('http://127.0.0.1:8025/health', timeout=1)
                if r.status_code == 200:
                    return True
            except Exception:
                time.sleep(0.5)
    except Exception:
        return False
    return False


@pytest.mark.integration
def test_email_alert_sent_and_received():
    if not ensure_mailhog_running():
        pytest.skip('MailHog not available; skipping email alert test')

    # monkeypatch app's send_alert_email to use MailHog SMTP (127.0.0.1:1025)
    def send_via_mailhog(to_email, student_name, risk_score, course, instructor):
        from email.mime.text import MIMEText
        msg = MIMEText(f"Alert for {student_name} risk={risk_score} course={course}")
        msg['Subject'] = f"[ALERT] {student_name}"
        msg['From'] = 'noreply@example.com'
        msg['To'] = to_email
        s = smtplib.SMTP('127.0.0.1', 1025)
        s.sendmail('noreply@example.com', [to_email], msg.as_string())
        s.quit()

    # replace function in backend module
    backend_mod.send_alert_email = send_via_mailhog

    client = app.test_client()
    # login as instructor
    r = client.post('/api/login', json={'username': 'instructor1', 'password': 'instructorpass'})
    assert r.status_code == 200

    # add a record that triggers an alert (low marks -> high risk)
    rec = {
        'student_name': 'student1',
        'marks': 1,
        'attendance': 1,
        'course': 'TestCourse',
        'instructor': 'instructor1'
    }
    ar = client.post('/api/add_record', json=rec)
    assert ar.status_code == 200

    # query MailHog API for messages
    msgs = None
    for _ in range(10):
        try:
            r = requests.get('http://127.0.0.1:8025/api/v2/messages')
            j = r.json()
            if j.get('total', 0) > 0:
                msgs = j
                break
        except Exception:
            pass
        time.sleep(0.5)

    assert msgs is not None, 'No email captured by MailHog'
    # check for our alert subject
    subjects = [m['Content']['Headers'].get('Subject', [''])[0] for m in msgs.get('items', [])]
    assert any('[ALERT' in s or 'High Risk' in s or 'ALERT' in s for s in subjects)
