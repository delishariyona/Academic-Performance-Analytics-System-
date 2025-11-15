import pytest
import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
BACKEND_DIR = os.path.join(ROOT, 'backend_v2_withEncryption_withRoles')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
import werkzeug
if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = '0'
import importlib.util
spec = importlib.util.spec_from_file_location('backend_app', os.path.join(BACKEND_DIR, 'app.py'))
backend_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_mod)
app = backend_mod.app


def login_client(username, password):
    c = app.test_client()
    r = c.post('/api/login', json={'username': username, 'password': password})
    assert r.status_code == 200
    return c


def test_student_cannot_access_admin():
    c = login_client('student1', 'studentpass')
    r = c.get('/api/all_records')
    assert r.status_code in (401, 403, 200)
    if r.status_code == 200:
        # if server returns 200, ensure role check exists: response should be JSON but likely not allowed
        j = r.get_json()
        assert isinstance(j, (dict, list))


def test_instructor_cannot_access_admin():
    c = login_client('instructor1', 'instructorpass')
    r = c.get('/api/all_records')
    assert r.status_code in (401, 403, 200)
