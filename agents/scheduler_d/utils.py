# scheduler_d/utils.py
import hashlib

def hash_binary(binary_bytes: bytes) -> str:
    return hashlib.sha256(binary_bytes).hexdigest()
