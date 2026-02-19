import base64
import hashlib
import secrets

from frigate.const import PASSWORD_HASH_ALGORITHM


def hash_password(password: str, salt: str | None = None, iterations: int = 600000) -> str:
    if salt is None:
        salt = secrets.token_hex(16)

    assert salt and isinstance(salt, str) and "$" not in salt
    assert isinstance(password, str)

    pw_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    b64_hash = base64.b64encode(pw_hash).decode("ascii").strip()
    return f"{PASSWORD_HASH_ALGORITHM}${iterations}${salt}${b64_hash}"
