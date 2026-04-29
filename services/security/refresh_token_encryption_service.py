import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from repositories.helpers.secret_manager_helper import (
    SecretManagerHelper,
    SecretManagerHelperError,
)
from services.security.auth_config import AuthConfig
from services.security.auth_exceptions import EncryptionKeyError


class RefreshTokenEncryptionService:
    def __init__(
        self,
        *,
        auth_config: AuthConfig,
        secret_manager_helper: SecretManagerHelper | None = None,
    ) -> None:
        self._auth_config = auth_config
        self._secret_manager_helper = secret_manager_helper or SecretManagerHelper()
        self._fernet = Fernet(self._resolve_fernet_key())

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as error:
            raise EncryptionKeyError("Failed to decrypt refresh token.") from error

    def _resolve_fernet_key(self) -> bytes:
        raw_key = self._auth_config.token_enc_key
        if not raw_key and self._auth_config.token_enc_key_secret_name:
            try:
                raw_key = self._secret_manager_helper.access_secret(
                    secret_name=self._auth_config.token_enc_key_secret_name
                )
            except SecretManagerHelperError as error:
                raise EncryptionKeyError("Failed to load TOKEN_ENC_KEY.") from error

        if not raw_key:
            raise EncryptionKeyError(
                "TOKEN_ENC_KEY is required when auth workflows are enabled."
            )

        encoded_key = raw_key.encode("utf-8")
        try:
            Fernet(encoded_key)
            return encoded_key
        except ValueError:
            digest = hashlib.sha256(encoded_key).digest()
            return base64.urlsafe_b64encode(digest)
