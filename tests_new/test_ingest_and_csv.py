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


def login_client(username='instructor1', password='instructorpass'):
    c = app.test_client()
    r = c.post('/api/login', json={'username': username, 'password': password})
    assert r.status_code == 200
    return c


def test_csv_bulk_upload():
    c = login_client()
    records = [
        {"student_name": "student1", "marks": 80, "attendance": 90, "course": "Math"},
        {"student_name": "student2", "marks": 60, "attendance": 70, "course": "Bio"}
    ]
    r = c.post('/api/add_records', json={'records': records, 'instructor': 'instructor1'})
    assert r.status_code == 200
    j = r.get_json()
    assert j.get('success') is True
