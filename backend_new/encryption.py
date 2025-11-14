from cryptography.fernet import Fernet

KEY = b'FMhlwrJoB9YGxco3qQqM-GsgRfZzJjux7gN8gJmxWCo='
f = Fernet(KEY)

def encrypt(text):
    text = str(text)  # <<--- FIX: ensures int/float become string
    return f.encrypt(text.encode()).decode()

def decrypt(token):
    return f.decrypt(token.encode()).decode()
