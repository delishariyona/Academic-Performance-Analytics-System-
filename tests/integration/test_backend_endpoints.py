import json
import random
import string
import pytest

from backend_v2_withEncryption_withRoles import app


def random_user():
    return "tst_" + ''.join(random.choice(string.ascii_lowercase) for _ in range(6))


def test_login_and_settings_flow():
    client = app.test_client()
    # use existing admin credentials (created earlier in setup)
    res = client.post('/api/login', json={'username': 'admin', 'password': 'adminpass'})
    assert res.status_code == 200
    data = res.get_json()
    assert data.get('success') is True

    # now call settings endpoint using same client (session preserved)
    sres = client.get('/api/settings')
    assert sres.status_code == 200
    j = sres.get_json()
    assert 'risk_threshold' in j and 'model_version' in j


def test_create_user_and_list():
    client = app.test_client()
    # login as admin
    res = client.post('/api/login', json={'username': 'admin', 'password': 'adminpass'})
    assert res.status_code == 200
    # create a new user
    name = random_user()
    cres = client.post('/api/users', json={'username': name, 'password': 'pw', 'role': 'student'})
    # admin-only - ensure success
    assert cres.status_code == 200
    jr = cres.get_json()
    assert jr.get('success') is True

    # list users
    l = client.get('/api/users')
    assert l.status_code == 200
    users = l.get_json()
    assert any(u.get('username') == name for u in users)
