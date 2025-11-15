import pytest
import sys, os
# ensure repo root in sys.path so tests can import the backend package
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
BACKEND_DIR = os.path.join(ROOT, 'backend_v2_withEncryption_withRoles')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# import the backend app module by file so local imports resolve correctly
import werkzeug
if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = '0'
import importlib.util
spec = importlib.util.spec_from_file_location('backend_app', os.path.join(BACKEND_DIR, 'app.py'))
backend_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_mod)
app = backend_mod.app


def test_successful_login():
    client = app.test_client()
    res = client.post('/api/login', json={'username': 'admin', 'password': 'adminpass'})
    assert res.status_code == 200
    j = res.get_json()
    assert j.get('success') is True


def test_invalid_login():
    client = app.test_client()
    res = client.post('/api/login', json={'username': 'noone', 'password': 'bad'})
    assert res.status_code in (401, 200)
    j = res.get_json()
    # either explicit failure or 401 with message
    assert j.get('success') is False or res.status_code == 401
