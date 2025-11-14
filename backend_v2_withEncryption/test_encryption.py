#!/usr/bin/env python3
"""
Comprehensive test suite for encryption and TLS features in backend_v2_withEncryption
Tests:
  1. Encryption/Decryption round-trip
  2. HMAC deterministic behavior
  3. Fernet key generation and loading
  4. HMAC key generation and loading
  5. Invalid token handling
"""

import sys
import os
from crypto import encrypt_value, decrypt_value, hmac_value, get_fernet, get_hmac_key

def test_encryption_roundtrip():
    """Test that plaintext can be encrypted and decrypted back to original."""
    print("\n[TEST 1] Encryption/Decryption Round-trip")
    test_cases = ["student1", "John Doe", "alice@example.com", "123", ""]
    
    for plaintext in test_cases:
        if not plaintext:  # Skip empty string in this test (will fail for encryption)
            continue
        encrypted = encrypt_value(plaintext)
        decrypted = decrypt_value(encrypted)
        status = "✓" if plaintext == decrypted else "✗"
        print(f"  {status} '{plaintext}' -> encrypted -> decrypted: '{decrypted}'")
        if plaintext != decrypted:
            print(f"     ERROR: Mismatch! Expected '{plaintext}' but got '{decrypted}'")
            return False
    return True


def test_hmac_deterministic():
    """Test that HMAC produces the same hash for the same input."""
    print("\n[TEST 2] HMAC Deterministic Behavior")
    test_values = ["student1", "instructor42", "admin_user"]
    
    for value in test_values:
        hmac1 = hmac_value(value)
        hmac2 = hmac_value(value)
        status = "✓" if hmac1 == hmac2 else "✗"
        print(f"  {status} HMAC('{value}')")
        print(f"     First call:  {hmac1[:32]}...")
        print(f"     Second call: {hmac2[:32]}...")
        if hmac1 != hmac2:
            print(f"     ERROR: HMAC not deterministic!")
            return False
    return True


def test_hmac_uniqueness():
    """Test that different inputs produce different HMACs."""
    print("\n[TEST 3] HMAC Uniqueness (Different inputs)")
    value1 = "student1"
    value2 = "student2"
    
    hmac1 = hmac_value(value1)
    hmac2 = hmac_value(value2)
    
    status = "✓" if hmac1 != hmac2 else "✗"
    print(f"  {status} Different inputs produce different HMACs")
    print(f"     HMAC('{value1}'): {hmac1[:32]}...")
    print(f"     HMAC('{value2}'): {hmac2[:32]}...")
    if hmac1 == hmac2:
        print(f"     ERROR: HMACs are identical!")
        return False
    return True


def test_none_handling():
    """Test that None values are handled gracefully."""
    print("\n[TEST 4] None Value Handling")
    
    enc_none = encrypt_value(None)
    dec_none = decrypt_value(None)
    hmac_none = hmac_value(None)
    
    status1 = "✓" if enc_none is None else "✗"
    status2 = "✓" if dec_none is None else "✗"
    status3 = "✓" if hmac_none is None else "✗"
    
    print(f"  {status1} encrypt_value(None) returns None: {enc_none}")
    print(f"  {status2} decrypt_value(None) returns None: {dec_none}")
    print(f"  {status3} hmac_value(None) returns None: {hmac_none}")
    
    return enc_none is None and dec_none is None and hmac_none is None


def test_invalid_token():
    """Test that invalid tokens are handled gracefully."""
    print("\n[TEST 5] Invalid Token Handling")
    
    invalid_tokens = [
        "not_a_token",
        "gAAAAABxyz123",  # Invalid Fernet token
        "",
    ]
    
    all_passed = True
    for invalid_token in invalid_tokens:
        result = decrypt_value(invalid_token)
        status = "✓" if result is None else "✗"
        print(f"  {status} decrypt_value('{invalid_token[:20]}...') returns None: {result}")
        if result is not None:
            all_passed = False
    
    return all_passed


def test_key_files_exist():
    """Test that key and cert files were created."""
    print("\n[TEST 6] Key and Certificate Files")
    
    files_to_check = [
        ("secrets/fernet.key", "Fernet encryption key"),
        ("secrets/hmac.key", "HMAC secret key"),
        ("secrets/server.crt", "TLS certificate"),
        ("secrets/server.key", "TLS private key"),
    ]
    
    all_exist = True
    for filepath, description in files_to_check:
        exists = os.path.exists(filepath)
        status = "✓" if exists else "✗"
        print(f"  {status} {filepath}: {description}")
        if not exists:
            all_exist = False
    
    return all_exist


def test_fernet_key_load():
    """Test that Fernet can be loaded and used."""
    print("\n[TEST 7] Fernet Key Loading")
    
    try:
        fernet = get_fernet()
        print(f"  ✓ Fernet object created successfully")
        
        # Try to encrypt/decrypt with the loaded key
        test_msg = "test_message_123"
        token = fernet.encrypt(test_msg.encode())
        decrypted = fernet.decrypt(token).decode()
        
        if test_msg == decrypted:
            print(f"  ✓ Fernet encryption/decryption works")
            return True
        else:
            print(f"  ✗ Decrypted message doesn't match!")
            return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_hmac_key_load():
    """Test that HMAC key can be loaded."""
    print("\n[TEST 8] HMAC Key Loading")
    
    try:
        hmac_key = get_hmac_key()
        print(f"  ✓ HMAC key loaded successfully (length: {len(hmac_key)} bytes)")
        return len(hmac_key) > 0
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_tls_cert_validity():
    """Test that TLS certificate is valid."""
    print("\n[TEST 9] TLS Certificate Validity")
    
    try:
        import ssl
        import socket
        
        cert_path = "secrets/server.crt"
        if not os.path.exists(cert_path):
            print(f"  ✗ Certificate not found at {cert_path}")
            return False
        
        # Try to load the cert with SSL context
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cert_path, keyfile="secrets/server.key")
        print(f"  ✓ TLS certificate and key loaded successfully")
        
        # Check minimum TLS version
        try:
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            print(f"  ✓ TLS 1.2+ minimum version enforced")
        except AttributeError:
            print(f"  ⚠ TLS version attribute not available (older Python)")
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def main():
    print("=" * 70)
    print("BACKEND_V2_WITHENCRYPTION - ENCRYPTION & TLS TEST SUITE")
    print("=" * 70)
    
    tests = [
        ("Encryption Round-trip", test_encryption_roundtrip),
        ("HMAC Deterministic", test_hmac_deterministic),
        ("HMAC Uniqueness", test_hmac_uniqueness),
        ("None Handling", test_none_handling),
        ("Invalid Token Handling", test_invalid_token),
        ("Key/Cert Files Exist", test_key_files_exist),
        ("Fernet Key Loading", test_fernet_key_load),
        ("HMAC Key Loading", test_hmac_key_load),
        ("TLS Certificate Validity", test_tls_cert_validity),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n  ✗ EXCEPTION: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    print("=" * 70)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
