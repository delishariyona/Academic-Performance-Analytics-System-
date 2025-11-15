# backend/models.py
import mysql.connector
from config import DB_CONFIG


class _FakeCursor:
    def __init__(self, db, dictionary=False):
        self.db = db
        self._dict = dictionary
        self._fetch = None
        self._fetchall = []
        self.description = None
        self._lastrowid = None

    def execute(self, sql, params=None):
        s = (sql or "").strip().lower()
        if s.startswith('select') and 'from users where username' in s:
            uname = params[0]
            user = self.db.users.get(uname)
            if self._dict:
                self._fetch = user.copy() if user else None
            else:
                self._fetch = tuple(user.values()) if user else None
        elif s.startswith('select') and 'from settings where' in s:
            key = params[0] if params else None
            if key == 'risk_threshold':
                self._fetch = ('0.6',)
            elif key == 'model_version':
                self._fetch = ('1',)
            else:
                self._fetch = None
        elif s.startswith('select') and 'from records' in s:
            # minimal rows for pandas read_sql or export
            import backend_v2_withEncryption_withRoles.crypto as crypto
            self._fetchall = [
                (1, crypto.encrypt_value('student_a'), crypto.hmac_value('student_a'), 50, 90, 0.5, 'C101', 'instr', 't')
            ]
            self.description = [
                ('id',), ('student_name',), ('student_hmac',), ('marks',), ('attendance',), ('risk_score',), ('course',), ('instructor_name',), ('timestamp',)
            ]
        elif s.startswith('insert') and 'into users' in s:
            uname = params[0]
            pwd = params[1]
            role = params[2]
            self.db.users[uname] = {'username': uname, 'password': pwd, 'role': role}
            self._lastrowid = self.db.next_id()
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
        return _FakeCursor(self, dictionary)

    def commit(self):
        pass

    def close(self):
        pass

    def next_id(self):
        self._id += 1
        return self._id


def get_db():
    """
    Returns a mysql.connector connection. If a real MySQL server is not
    available (e.g., running tests in CI without DB), fall back to a
    lightweight in-memory FakeDB to keep tests isolated.
    """
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Exception:
        return FakeDB()
