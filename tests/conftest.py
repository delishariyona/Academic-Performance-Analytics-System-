import pytest

class FakeCursor:
    def __init__(self, db, dictionary=False):
        self.db = db
        self._dict = dictionary
        self.description = None
        self._lastrowid = None

    def execute(self, sql, params=None):
        s = (sql or "").strip().lower()
        self._last_query = s
        # simple routing for queries used in tests
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
            # minimal fake row for exports
            import backend_v2_withEncryption_withRoles.crypto as crypto
            self._fetchall = [
                (1, crypto.encrypt_value('student_a'), crypto.hmac_value('student_a'), 50, 90, 0.5, 'C101', 'instr', 't')
            ]
            self.description = [
                ('id',), ('student_name',), ('student_hmac',), ('marks',), ('attendance',), ('risk_score',), ('course',), ('instructor_name',), ('timestamp',)
            ]
        elif s.startswith('insert') and 'into users' in s:
            # simulate insert user
            uname = params[0]
            pwd = params[1]
            role = params[2]
            self.db.users[uname] = {'username': uname, 'password': pwd, 'role': role}
            self._lastrowid = self.db.next_id()
        elif s.startswith('select') and 'from users order by id' in s:
            # return list of users
            self._fetchall = [ {'id': i+1, 'username': u, 'role': d['role']} for i,(u,d) in enumerate(self.db.users.items()) ]
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
        self._id = 100
        self.users = {
            'admin': {'username': 'admin', 'password': 'adminpass', 'role': 'admin'},
            'instructor1': {'username': 'instructor1', 'password': 'instructorpass', 'role': 'instructor'},
            'student1': {'username': 'student1', 'password': 'studentpass', 'role': 'student'},
        }

    def cursor(self, dictionary=False):
        return FakeCursor(self, dictionary)

    def commit(self):
        pass

    def close(self):
        pass

    def next_id(self):
        self._id += 1
        return self._id


@pytest.fixture(autouse=True)
def patch_get_db(monkeypatch):
    """Automatically replace get_db used by the app with a FakeDB for tests."""
    import backend_v2_withEncryption_withRoles.app as backend_app
    import backend_v2_withEncryption_withRoles.models as backend_models

    fake = FakeDB()
    # patch both the app module's get_db binding and the models.get_db
    monkeypatch.setattr(backend_app, 'get_db', lambda: fake)
    monkeypatch.setattr(backend_models, 'get_db', lambda: fake)
    # patch mysql.connector.connect globally so any module calling it gets FakeDB
    try:
        import mysql
        import mysql.connector
        monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: fake)
    except Exception:
        # mysql may not be installed in test environment; ignore if unavailable
        pass
    yield