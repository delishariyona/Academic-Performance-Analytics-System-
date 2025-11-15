import pytest
import requests


BASE = "http://127.0.0.1:5000"


def is_backend_up():
    try:
        r = requests.get(BASE + "/api/settings", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def test_system_login_flow_or_skip():
    if not is_backend_up():
        pytest.skip("Backend HTTP server not reachable on 127.0.0.1:5000 — skipping system tests")
    sess = requests.Session()
    r = sess.post(BASE + "/api/login", json={"username": "admin", "password": "adminpass"}, timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert data.get('success') is True
    # call settings
    s = sess.get(BASE + "/api/settings", timeout=5)
    assert s.status_code == 200
