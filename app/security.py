import hashlib
import hmac
import secrets


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 200_000).hex()
    return f'{salt}${digest}'


def verify_password(password, encoded):
    salt, _ = encoded.split('$', 1)
    return hmac.compare_digest(hash_password(password, salt), encoded)
