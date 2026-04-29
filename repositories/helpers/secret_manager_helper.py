from typing import Any


class SecretManagerHelperError(Exception):
    pass


class SecretManagerHelper:
    def __init__(self, *, client: Any | None = None) -> None:
        self._client = client

    def access_secret(self, *, secret_name: str) -> str:
        client = self._get_client()
        try:
            response = client.access_secret_version(name=secret_name)
        except Exception as error:  # pragma: no cover - provider specific failures
            raise SecretManagerHelperError("Failed to access secret manager value.") from error
        payload = response.payload.data.decode("utf-8")
        if not payload:
            raise SecretManagerHelperError("Secret manager value is empty.")
        return payload

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from google.cloud import secretmanager
        except ModuleNotFoundError as error:
            raise SecretManagerHelperError(
                "google-cloud-secret-manager is not installed."
            ) from error

        self._client = secretmanager.SecretManagerServiceClient()
        return self._client
