import base64
import hashlib
import hmac
import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from services.security.auth_exceptions import InvalidStateError


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _base64url_decode(raw: str) -> bytes:
    padding = "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode(raw + padding)


class _NonceStore:
    def __init__(self) -> None:
        self._consumed: dict[str, int] = {}
        self._lock = threading.Lock()

    def consume_once(self, *, nonce: str, expires_at: int) -> None:
        now = int(datetime.now(timezone.utc).timestamp())
        with self._lock:
            stale_nonces = [
                key for key, value in self._consumed.items() if value <= now
            ]
            for key in stale_nonces:
                del self._consumed[key]

            if nonce in self._consumed:
                raise InvalidStateError("invalid_state")

            self._consumed[nonce] = expires_at


class StateTokenService:
    def __init__(self, *, secret: str, ttl_seconds: int = 600) -> None:
        self._secret = secret.encode("utf-8")
        self._ttl_seconds = ttl_seconds
        self._nonce_store = _NonceStore()

    def issue_state_token(
        self,
        *,
        callback_mode: str,
        redirect_uri: str | None = None,
        platform: str | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        issued_at = int(now.timestamp())
        expires_at = int((now + timedelta(seconds=self._ttl_seconds)).timestamp())
        payload: dict[str, Any] = {
            "nonce": str(uuid.uuid4()),
            "iat": issued_at,
            "exp": expires_at,
            "callback_mode": callback_mode,
        }
        if redirect_uri:
            payload["redirect_uri"] = redirect_uri
        if platform:
            payload["platform"] = platform

        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        payload_encoded = _base64url_encode(payload_bytes)
        signature = hmac.new(
            self._secret, payload_encoded.encode("utf-8"), hashlib.sha256
        ).digest()
        signature_encoded = _base64url_encode(signature)
        return f"{payload_encoded}.{signature_encoded}"

    def consume_state_token(self, token: str) -> dict[str, Any]:
        try:
            encoded_payload, encoded_signature = token.split(".", maxsplit=1)
        except ValueError as error:
            raise InvalidStateError("invalid_state") from error

        expected_signature = hmac.new(
            self._secret, encoded_payload.encode("utf-8"), hashlib.sha256
        ).digest()
        provided_signature = _base64url_decode(encoded_signature)
        if not hmac.compare_digest(expected_signature, provided_signature):
            raise InvalidStateError("invalid_state")

        try:
            payload = json.loads(_base64url_decode(encoded_payload).decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as error:
            raise InvalidStateError("invalid_state") from error

        now = int(datetime.now(timezone.utc).timestamp())
        required_keys = {"nonce", "iat", "exp", "callback_mode"}
        if not required_keys.issubset(payload.keys()):
            raise InvalidStateError("invalid_state")
        if not isinstance(payload["nonce"], str):
            raise InvalidStateError("invalid_state")
        if not isinstance(payload["iat"], int) or not isinstance(payload["exp"], int):
            raise InvalidStateError("invalid_state")
        if payload["exp"] <= now or payload["iat"] > now:
            raise InvalidStateError("invalid_state")

        self._nonce_store.consume_once(
            nonce=payload["nonce"],
            expires_at=payload["exp"],
        )

        return payload
