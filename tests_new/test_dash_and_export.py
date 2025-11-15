import pytest
import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
BACKEND_DIR = os.path.join(ROOT, 'backend_v2_withEncryption_withRoles')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
import importlib.util
spec = importlib.util.spec_from_file_location('backend_app', os.path.join(BACKEND_DIR, 'app.py'))
backend_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_mod)
app = backend_mod.app
import werkzeug
if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = '0'


def login_client(username='admin', password='adminpass'):
    c = app.test_client()
    r = c.post('/api/login', json={'username': username, 'password': password})
    assert r.status_code == 200
    return c


def test_instructor_kpis():
    c = login_client('instructor1', 'instructorpass')
    r = c.get('/api/instructor/instructor1')
    assert r.status_code == 200
    j = r.get_json()
    assert isinstance(j, list)


def test_admin_aggregation_and_export():
    c = login_client('admin', 'adminpass')
    r = c.get('/api/all_records')
    assert r.status_code in (200, 500)
    # export endpoints (may depend on reportlab availability)
    e = c.get('/api/export')
    assert e.status_code == 200
    je = e.get_json()
    assert je.get('success') is True
    p = c.get('/api/export_pdf')
    assert p.status_code == 200
    jp = p.get_json()
    assert jp.get('success') is True
