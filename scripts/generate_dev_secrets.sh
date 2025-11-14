#!/usr/bin/env bash
set -eu

# Generates development Fernet/HMAC keys and a self-signed TLS cert in ./secrets/
SECRETS_DIR="./backend_v2/secrets"
mkdir -p "$SECRETS_DIR"

echo "Generating Fernet key..."
python - <<'PY'
from cryptography.fernet import Fernet
open('$SECRETS_DIR/fernet.key','wb').write(Fernet.generate_key())
open('$SECRETS_DIR/hmac.key','wb').write(__import__('os').urandom(32))
print('Fernet and HMAC keys written to $SECRETS_DIR')
PY

echo "Generating self-signed TLS certificate (valid 365 days)..."
openssl req -x509 -newkey rsa:2048 -nodes -keyout "$SECRETS_DIR/server.key" -out "$SECRETS_DIR/server.crt" -days 365 -subj "/C=US/ST=None/L=None/O=APAS/OU=Dev/CN=localhost"

echo "Done. Secrets and certs created in $SECRETS_DIR"
