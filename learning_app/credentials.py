"""Authenticated encryption for provider credentials at rest."""
import json
import os

from cryptography.fernet import Fernet, InvalidToken


class CredentialEncryptionUnavailable(RuntimeError):
    pass


def cipher():
    key = os.environ.get("LEARNING_CREDENTIAL_KEY", "").strip()
    if not key:
        raise CredentialEncryptionUnavailable("Set LEARNING_CREDENTIAL_KEY to enable provider connections.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as error:
        raise CredentialEncryptionUnavailable("LEARNING_CREDENTIAL_KEY must be a valid Fernet key.") from error


def encrypt(value):
    return cipher().encrypt(json.dumps(value, separators=(",", ":")).encode("utf-8")).decode("ascii")


def decrypt(value):
    try:
        return json.loads(cipher().decrypt(value.encode("ascii")).decode("utf-8"))
    except InvalidToken as error:
        raise CredentialEncryptionUnavailable("Stored provider credentials could not be decrypted.") from error
