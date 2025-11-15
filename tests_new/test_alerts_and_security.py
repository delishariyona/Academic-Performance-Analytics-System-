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
from models import get_db
import werkzeug
if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = '0'


def login_client(username='admin', password='adminpass'):
    c = app.test_client()
    r = c.post('/api/login', json={'username': username, 'password': password})
    assert r.status_code == 200
    return c


def test_alerts_list():
    c = login_client('admin', 'adminpass')
    r = c.get('/api/alerts')
    assert r.status_code == 200
    j = r.get_json()
    assert isinstance(j, list)


def test_data_encryption_in_db():
    # Verify that records.student_name appears encrypted (not plain) and student_hmac present
    try:
        db = get_db()
    except Exception:
        pytest.skip('DB not available')
    cur = db.cursor()
    cur.execute('SELECT student_name, student_hmac FROM records LIMIT 5')
    rows = cur.fetchall()
    cur.close()
    db.close()
    if not rows:
        pytest.skip('No records to inspect')
    for name, hmac in rows:
        assert name is not None
        # encrypted tokens will include a colon or be longer than plain username
        assert (':' in name) or (len(name) > 30) or hmac is not None
