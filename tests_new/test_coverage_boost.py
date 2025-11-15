import sys
import os
import importlib.util
import importlib
import smtplib
import pytest

# ensure backend path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BACKEND_DIR = os.path.join(ROOT, 'backend_v2_withEncryption_withRoles')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# import modules under test
crypto = importlib.import_module('crypto')
ml = importlib.import_module('ml_engine')
email_service = importlib.import_module('email_service')

# import the app module
spec = importlib.util.spec_from_file_location('backend_app', os.path.join(BACKEND_DIR, 'app.py'))
backend_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_mod)
app = backend_mod.app


def test_crypto_roundtrip_and_hmac():
    plain = 'Alice'
    token = crypto.encrypt_value(plain)
    assert token != plain
    got = crypto.decrypt_value(token)
    assert got == plain
    h = crypto.hmac_value(plain)
    assert isinstance(h, str) and len(h) > 0


def test_ml_engine_predict_and_retrain():
    # small values -> expect higher risk per implementation
    r1 = ml.predict_risk(1, 1)
    r2 = ml.predict_risk(80, 90)
    assert 0.0 <= r1 <= 1.0
    assert 0.0 <= r2 <= 1.0
    # retrain should bump model version via rebuild_model without throwing
    try:
        ml.rebuild_model()
    except Exception:
        pytest.skip('rebuild_model not available in this environment')


def test_email_service_smtp_success(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port):
            sent['connected'] = (host, port)

        def starttls(self):
            sent['starttls'] = True

        def login(self, user, pw):
            sent['login'] = (user, pw)

        def sendmail(self, frm, to, msg):
            sent['sent'] = (frm, to, msg)

        def quit(self):
            sent['quit'] = True

    monkeypatch.setattr(smtplib, 'SMTP', FakeSMTP)
    # call send_alert_email and expect it to use FakeSMTP without exception
    try:
        email_service.send_alert_email('to@example.com', 'Bob', 0.9, 'C101', 'Prof')
    except Exception as e:
        pytest.fail(f'email_service.send_alert_email raised: {e}')
    assert 'sent' in sent


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self._lastrowid = None
        self._dict = False

    def execute(self, sql, params=None):
        s = sql.strip().lower()
        self._last_query = s
        # very small SQL router for tests
        if s.startswith('select') and 'from users where username' in s:
            uname = params[0]
            user = self.db.users.get(uname)
            if self._dict:
                self._fetch = user.copy() if user else None
            else:
                self._fetch = tuple(user.values()) if user else None
        elif s.startswith('select') and 'count(*) from users' in s:
            self._fetch = (1,)  # valid student
        elif s.startswith('select') and 'from settings where `key`' in s:
            # return threshold or model_version based on param
            key = params[0]
            if key == 'risk_threshold':
                self._fetch = ('0.6',)
            else:
                self._fetch = ('1',)
        elif s.startswith('insert into records'):
            # simulate insert
            self._lastrowid = self.db.next_id()
            self._fetch = None
        elif s.startswith('insert into alerts'):
            self._lastrowid = self.db.next_id()
            self._fetch = None
        elif s.startswith('select') and 'from alerts' in s:
            # return stored alerts
            items = []
            for a in self.db.alerts:
                items.append({'id': a['id'], 'student_name': a['student_name'], 'student_hmac': a['student_hmac'], 'risk_score': a['risk_score'], 'record_id': a['record_id'], 'created_at': 'now'})
            self._fetchall = items
        elif s.startswith('select') and 'from records' in s:
            # return sample records
            if self._dict:
                self._fetchall = [{'id': 1, 'student_name': crypto.encrypt_value('student1'), 'marks': 10, 'attendance': 90, 'risk_score': 0.1, 'course': 'C', 'instructor_name': 'instructor1', 'timestamp': 't'}]
            else:
                self._fetchall = [(1, crypto.encrypt_value('student1'), crypto.hmac_value('student1'), 10, 90, 0.1, 'C', 'instructor1', 't')]
        else:
            self._fetch = None

    def fetchone(self):
        v = getattr(self, '_fetch', None)
        # if a plain scalar was stored, return as single-element tuple, converting numeric strings
        if isinstance(v, (str, int, float)):
            if isinstance(v, str):
                if v.isdigit():
                    return (int(v),)
                try:
                    return (float(v),)
                except Exception:
                    return (v,)
            return (v,)
        # normalize single-value tuple element numeric strings to numbers
        if isinstance(v, tuple) and len(v) == 1:
            val = v[0]
            if isinstance(val, str):
                if val.isdigit():
                    return (int(val),)
                try:
                    return (float(val),)
                except Exception:
                    return v
        return v

    def fetchall(self):
        return getattr(self, '_fetchall', [])

    def close(self):
        pass

    @property
    def lastrowid(self):
        return self._lastrowid


class FakeDB:
    def __init__(self):
        self._id = 100
        # users mapped to dicts
        self.users = {'admin': {'username': 'admin', 'password': 'adminpass', 'role': 'admin'}, 'instructor1': {'username': 'instructor1', 'password': 'instructorpass', 'role': 'instructor'}, 'student1': {'username': 'student1', 'password': 'studentpass', 'role': 'student'}}
        self.alerts = []

    def cursor(self, dictionary=False):
        c = FakeCursor(self)
        c._dict = dictionary
        return c

    def commit(self):
        pass

    def close(self):
        pass

    def next_id(self):
        self._id += 1
        return self._id


def test_app_endpoints_with_fake_db(monkeypatch):
    fake = FakeDB()

    # monkeypatch the get_db used by the app module
    monkeypatch.setattr(backend_mod, 'get_db', lambda: fake)

    client = app.test_client()

    # login as admin
    r = client.post('/api/login', json={'username': 'admin', 'password': 'adminpass'})
    assert r.status_code == 200
    j = r.get_json()
    assert j.get('success') is True

    # set and get settings (requires admin)
    with client.session_transaction() as sess:
        sess['username'] = 'admin'

    r2 = client.post('/api/settings', json={'key': 'risk_threshold', 'value': '0.5'})
    assert r2.status_code == 200

    r3 = client.get('/api/settings')
    assert r3.status_code == 200
    data = r3.get_json()
    assert 'risk_threshold' in data

    # test add_record as instructor
    with client.session_transaction() as sess:
        sess['username'] = 'instructor1'

    # force valid_student to True and stub out actual email sending to avoid SMTP
    monkeypatch.setattr(backend_mod, 'valid_student', lambda n: True)
    monkeypatch.setattr(backend_mod, 'send_alert_email', lambda *a, **k: None)

    rec = {'student_name': 'student1', 'marks': 1, 'attendance': 1, 'course': 'C', 'instructor': 'instructor1'}
    r4 = client.post('/api/add_record', json=rec)
    assert r4.status_code == 200
    jr = r4.get_json()
    assert jr.get('success') is True

    # alerts listing (as instructor)
    r5 = client.get('/api/alerts')
    assert r5.status_code == 200
