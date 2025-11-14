from cryptography.fernet import Fernet, InvalidToken
import os
import base64
import hashlib
import hmac
from config import ENCRYPTION


def _load_or_create_key(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        with open(path, 'rb') as f:
            return f.read().strip()
    # create a new key
    key = Fernet.generate_key()
    with open(path, 'wb') as f:
        f.write(key)
    return key


def get_fernet():
    # Prefer env var
    env_key = os.environ.get('APAS_FERNET_KEY')
    if env_key:
        # allow either raw key or base64
        return Fernet(env_key.encode() if isinstance(env_key, str) else env_key)
    key_path = ENCRYPTION.get('FERNET_KEY_PATH')
    key = _load_or_create_key(key_path)
    return Fernet(key)


def get_hmac_key():
    env = os.environ.get('APAS_HMAC_KEY')
    if env:
        return env.encode()
    path = ENCRYPTION.get('HMAC_KEY_PATH')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        return open(path, 'rb').read().strip()
    # create random key
    k = os.urandom(32)
    with open(path, 'wb') as f:
        f.write(k)
    return k


def encrypt_value(plaintext: str) -> str:
    f = get_fernet()
    if plaintext is None:
        return None
    token = f.encrypt(plaintext.encode())
    return token.decode()


def decrypt_value(token: str) -> str:
    if token is None:
        return None
    f = get_fernet()
    try:
        return f.decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def hmac_value(value: str) -> str:
    # deterministic HMAC for lookups
    if value is None:
        return None
    key = get_hmac_key()
    hm = hmac.new(key, value.encode(), hashlib.sha256).hexdigest()
    return hm
