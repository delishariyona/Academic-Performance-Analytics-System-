"""Pytest-style tests for encryption and TLS helpers in backend_v2_withEncryption_withRoles.

These tests exercise `crypto.py` helpers and TLS loading. They replace the
legacy script-style tests so pytest collects and reports coverage for this
module's lines.
"""
import os
import pytest

from crypto import encrypt_value, decrypt_value, hmac_value, get_fernet, get_hmac_key


def test_encryption_roundtrip():
    test_cases = ["student1", "John Doe", "alice@example.com", "123"]
    for plaintext in test_cases:
        token = encrypt_value(plaintext)
        assert token != plaintext
        got = decrypt_value(token)
        assert got == plaintext


def test_hmac_deterministic_and_uniqueness():
    vals = ["student1", "instructor42", "admin_user"]
    for v in vals:
        h1 = hmac_value(v)
        h2 = hmac_value(v)
        assert isinstance(h1, str) and len(h1) > 0
        assert h1 == h2

    # different values -> different HMACs (very likely)
    assert hmac_value("student1") != hmac_value("student2")


def test_none_handling():
    assert encrypt_value(None) is None
    assert decrypt_value(None) is None
    assert hmac_value(None) is None


def test_invalid_token_returns_none():
    assert decrypt_value("not_a_token") is None
    assert decrypt_value("") is None
    assert decrypt_value("gAAAAABxyz123") is None


def test_key_loading_and_roundtrip():
    # get_fernet/get_hmac_key will create keys if missing
    f = get_fernet()
    assert f is not None
    key = get_hmac_key()
    assert isinstance(key, (bytes, bytearray)) and len(key) > 0

    # ensure Fernet object works
    msg = "ping-123"
    tok = f.encrypt(msg.encode())
    assert f.decrypt(tok).decode() == msg


def test_tls_cert_load_or_skip():
    cert = "secrets/server.crt"
    key = "secrets/server.key"
    if not (os.path.exists(cert) and os.path.exists(key)):
        pytest.skip("TLS cert/key not present in dev secrets/ -> skipping")

    import ssl

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert, keyfile=key)
    # setting minimum version is optional
    try:
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    except Exception:
        pass
    assert True
"""Pytest-style tests for encryption and TLS helpers in backend_v2_withEncryption_withRoles.

These tests exercise `crypto.py` helpers and TLS loading. They replace the
legacy script-style tests so pytest collects and reports coverage for this
module's lines.
"""
import os
import pytest

from crypto import encrypt_value, decrypt_value, hmac_value, get_fernet, get_hmac_key


def test_encryption_roundtrip():
    test_cases = ["student1", "John Doe", "alice@example.com", "123"]
    for plaintext in test_cases:
        token = encrypt_value(plaintext)
        assert token != plaintext
        got = decrypt_value(token)
        assert got == plaintext


def test_hmac_deterministic_and_uniqueness():
    vals = ["student1", "instructor42", "admin_user"]
    for v in vals:
        h1 = hmac_value(v)
        h2 = hmac_value(v)
        assert isinstance(h1, str) and len(h1) > 0
        assert h1 == h2

    # different values -> different HMACs (very likely)
    assert hmac_value("student1") != hmac_value("student2")


def test_none_handling():
    assert encrypt_value(None) is None
    assert decrypt_value(None) is None
    assert hmac_value(None) is None


def test_invalid_token_returns_none():
    assert decrypt_value("not_a_token") is None
    assert decrypt_value("") is None
    assert decrypt_value("gAAAAABxyz123") is None


def test_key_loading_and_roundtrip():
    # get_fernet/get_hmac_key will create keys if missing
    f = get_fernet()
    assert f is not None
    key = get_hmac_key()
    assert isinstance(key, (bytes, bytearray)) and len(key) > 0

    # ensure Fernet object works
    msg = "ping-123"
    tok = f.encrypt(msg.encode())
    assert f.decrypt(tok).decode() == msg


def test_tls_cert_load_or_skip():
    cert = "secrets/server.crt"
    key = "secrets/server.key"
    if not (os.path.exists(cert) and os.path.exists(key)):
        pytest.skip("TLS cert/key not present in dev secrets/ -> skipping")

    import ssl

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert, keyfile=key)
    # setting minimum version is optional
    try:
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    except Exception:
        pass
    assert True
