import os
import pytest

from backend_v2_withEncryption_withRoles import crypto


def test_encrypt_decrypt_roundtrip():
    plain = "student1"
    token = crypto.encrypt_value(plain)
    assert token != plain
    out = crypto.decrypt_value(token)
    assert out == plain


def test_hmac_deterministic():
    a = crypto.hmac_value("student1")
    b = crypto.hmac_value("student1")
    assert a == b
    assert isinstance(a, str) and len(a) == 64


def test_encrypt_none_returns_none():
    assert crypto.encrypt_value(None) is None
    assert crypto.decrypt_value(None) is None
    assert crypto.hmac_value(None) is None
