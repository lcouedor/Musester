import os

def getSecret(key: str) -> str:
    return os.getenv(key)
