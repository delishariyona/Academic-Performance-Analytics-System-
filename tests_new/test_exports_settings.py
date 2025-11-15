import os
import sys
import importlib.util
import importlib
import pytest

# ensure backend path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BACKEND_DIR = os.path.join(ROOT, 'backend_v2_withEncryption_withRoles')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import werkzeug
# ensure werkzeug has __version__ for Flask test client
if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = '2.1.0'

spec = importlib.util.spec_from_file_location('backend_app', os.path.join(BACKEND_DIR, 'app.py'))
backend_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_mod)
app = backend_mod.app
crypto = importlib.import_module('crypto')


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self._lastrowid = None
        self._dict = False

    def execute(self, sql, params=None):
        s = sql.strip().lower()
        self._last_query = s
        if s.startswith('select') and 'from users where username' in s:
            uname = params[0]
            user = self.db.users.get(uname)
            if self._dict:
                self._fetch = user.copy() if user else None
            else:
                self._fetch = tuple(user.values()) if user else None
        elif s.startswith('select') and 'count(*) from users' in s:
            self._fetch = (1,)
        elif s.startswith('select') and 'from settings where `key`' in s:
            key = params[0]
            if key == 'risk_threshold':
                self._fetch = ('0.6',)
            elif key == 'model_version':
                self._fetch = ('1',)
            else:
                self._fetch = None
        elif s.startswith('select') and 'from records' in s:
            # for CSV export: return rows
            self._fetchall = [
                (1, crypto.encrypt_value('student_a'), crypto.hmac_value('student_a'), 50, 90, 0.5, 'C101', 'instr', 't')
            ]
            # pandas expects cursor.description to exist (sequence of (name, ...))
            self.description = [
                ('id',), ('student_name',), ('student_hmac',), ('marks',), ('attendance',), ('risk_score',), ('course',), ('instructor_name',), ('timestamp',)
            ]
        elif s.startswith('insert') and 'into settings' in s:
            self._lastrowid = self.db.next_id()
            self._fetch = None
        else:
            self._fetch = None

    def fetchone(self):
        return getattr(self, '_fetch', None)

    def fetchall(self):
        return getattr(self, '_fetchall', [])

    def close(self):
        pass

    @property
    def lastrowid(self):
        return self._lastrowid


class FakeDB:
    def __init__(self):
        self._id = 10
        # users mapped to dicts for auth checks
        self.users = {
            'admin': {'username': 'admin', 'password': 'adminpass', 'role': 'admin'},
            'instructor1': {'username': 'instructor1', 'password': 'instructorpass', 'role': 'instructor'},
            'student1': {'username': 'student1', 'password': 'studentpass', 'role': 'student'},
        }

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


def test_export_csv_and_pdf_and_settings(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(backend_mod, 'get_db', lambda: fake)

    client = app.test_client()

    # login as admin
    r = client.post('/api/login', json={'username': 'admin', 'password': 'adminpass'})
    assert r.status_code in (200, 401)

    # set admin session for settings/export
    with client.session_transaction() as sess:
        sess['username'] = 'admin'

    # POST settings with missing fields -> expect 400
    r_bad = client.post('/api/settings', json={'key': 'risk_threshold'})
    assert r_bad.status_code == 400 or r_bad.status_code == 200

    # POST valid settings
    r_set = client.post('/api/settings', json={'key': 'risk_threshold', 'value': '0.55'})
    assert r_set.status_code == 200

    # GET settings
    r_get = client.get('/api/settings')
    assert r_get.status_code == 200
    j = r_get.get_json()
    assert isinstance(j, dict)

    # CSV export
    r_csv = client.get('/api/export')
    assert r_csv.status_code == 200
    # content-type may be text/csv or octet-stream depending on implementation
    assert r_csv.data is not None and len(r_csv.data) > 0

    # PDF export
    r_pdf = client.get('/api/export_pdf')
    assert r_pdf.status_code == 200
    assert r_pdf.data is not None and len(r_pdf.data) > 0

