import hashlib
import secrets


class InviteTokenService:
    def __init__(self, *, signing_secret: str) -> None:
        self._signing_secret = signing_secret

    def generate_token(self) -> str:
        return secrets.token_urlsafe(32)

    def hash_token(self, *, token: str) -> str:
        raw = f"{self._signing_secret}:{token}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
