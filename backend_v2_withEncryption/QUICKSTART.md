# Quick Start - backend_v2_withEncryption

## 30-Second Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate keys and TLS cert (one-time)
python3 << 'EOF'
from cryptography.fernet import Fernet
import os

os.makedirs('secrets', exist_ok=True)
with open('secrets/fernet.key', 'wb') as f:
    f.write(Fernet.generate_key())
with open('secrets/hmac.key', 'wb') as f:
    f.write(os.urandom(32))
EOF

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout secrets/server.key -out secrets/server.crt -days 365 \
  -subj "/C=US/ST=None/L=None/O=APAS/OU=Dev/CN=localhost"

# 3. Configure MySQL (edit config.py with your DB credentials)

# 4. Run the app
python3 app.py
```

## Verify Encryption Works

```bash
python3 test_encryption.py
```

Expected: `Total: 9/9 tests passed ✓`

## What's Different from backend_v2?

| Feature | backend_v2 | backend_v2_withEncryption |
|---------|-----------|---------------------------|
| Student Names | Plain text in DB | **Encrypted with Fernet** |
| Lookups | Direct DB query | **Deterministic HMAC** |
| Data in Transit | HTTP | **HTTPS/TLS 1.2+** |
| Keys | N/A | **Auto-generated in secrets/** |

## API Usage (Same as Before)

```bash
# Add record - encryption transparent
curl -X POST https://localhost:5000/api/add_record \
  -d '{"student_name":"alice","marks":85,"attendance":95}' \
  -H "Content-Type: application/json"

# Get student data - automatic decryption
curl https://localhost:5000/api/student/alice

# Both work exactly the same, but data is encrypted!
```

## Files Created/Modified

- `crypto.py` - Encryption utilities
- `config.py` - Added TLS paths
- `app.py` - Integrated encryption, TLS enforcement
- `requirements.txt` - Added cryptography, reportlab
- `secrets/` - Auto-generated (fernet.key, hmac.key, server.crt, server.key)
- `test_encryption.py` - Test suite
- `ENCRYPTION_TLS_SETUP.md` - Full documentation

## Key Features

✅ Fernet encryption (symmetric, secure)
✅ HMAC for deterministic lookups (no plaintext leaks)
✅ TLS 1.2+ enforcement (in-transit encryption)
✅ Graceful DB error handling (app runs even if DB down)
✅ Comprehensive test suite (9/9 tests pass)
✅ Production-ready with env vars + CA certs

## Production Checklist

- [ ] Generate real CA-signed TLS certs
- [ ] Store keys in secrets manager (AWS/Vault)
- [ ] Set env vars: `APAS_FERNET_KEY`, `APAS_HMAC_KEY`
- [ ] Enable MySQL SSL
- [ ] Rotate keys quarterly
- [ ] Monitor audit_log for access patterns
- [ ] Test key rotation procedure

## Next Steps

1. ✅ **Verify** - Run `python3 test_encryption.py`
2. ✅ **Read** - Check `ENCRYPTION_TLS_SETUP.md` for details
3. ✅ **Deploy** - Move to production with CA certs + secrets manager

---

**Questions?** See `ENCRYPTION_TLS_SETUP.md` for full documentation & troubleshooting.
