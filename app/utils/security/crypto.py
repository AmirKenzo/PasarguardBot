from __future__ import annotations

import base64
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.decrepit.ciphers.modes import CFB
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.utils.security.secrets_cache import get_crypto_key


def generate_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000, backend=default_backend())
    return kdf.derive(password.encode())


def encrypt_data(data: str) -> str:
    salt = os.urandom(16)
    key = generate_key(get_crypto_key(), salt)
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), CFB(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(data.encode()) + encryptor.finalize()
    return base64.b64encode(salt + iv + ciphertext).decode()


def decrypt_data(encrypted_data: str) -> str:
    encrypted_bytes = base64.b64decode(encrypted_data)
    salt = encrypted_bytes[:16]
    iv = encrypted_bytes[16:32]
    ciphertext = encrypted_bytes[32:]
    key = generate_key(get_crypto_key(), salt)
    cipher = Cipher(algorithms.AES(key), CFB(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    return plaintext.decode()
