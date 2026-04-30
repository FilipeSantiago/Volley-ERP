import os
from datetime import datetime, timezone
from typing import Any

from repositories.helpers.firestore_client_helper import (
    FirestoreClientHelperError,
    resolve_firestore_client,
)


class GoogleConnectionRepositoryError(Exception):
    pass


class GoogleConnectionRepository:
    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        collection_name: str | None = None,
        project_id: str | None = None,
        database_id: str | None = None,
    ) -> None:
        self._firestore_client = firestore_client
        self._collection_name = collection_name or os.getenv(
            "FIRESTORE_GOOGLE_CONNECTIONS_COLLECTION", "google_connections"
        )
        self._project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self._database_id = database_id or os.getenv("FIRESTORE_DATABASE_ID", "customer")

    def get_by_user_id(self, *, user_id: str) -> dict[str, Any] | None:
        try:
            snapshot = self._collection().document(user_id).get()
        except Exception as error:
            raise GoogleConnectionRepositoryError(
                "Failed to fetch Google connection."
            ) from error

        if not snapshot.exists:
            return None
        return self._validate_document(snapshot.to_dict())

    def upsert_google_connection(
        self,
        *,
        user_id: str,
        encrypted_refresh_token: str | None,
        scopes: list[str],
    ) -> dict[str, Any]:
        existing = self.get_by_user_id(user_id=user_id)
        now = _now_iso()

        if existing is None:
            if not encrypted_refresh_token:
                raise GoogleConnectionRepositoryError(
                    "Google refresh token is required for first-time connection."
                )
            payload = {
                "user_id": user_id,
                "provider": "google",
                "encrypted_refresh_token": encrypted_refresh_token,
                "scopes": scopes,
                "created_at": now,
                "updated_at": now,
            }
        else:
            payload = {
                **existing,
                "encrypted_refresh_token": encrypted_refresh_token
                or existing.get("encrypted_refresh_token"),
                "scopes": scopes or existing.get("scopes", []),
                "updated_at": now,
            }

        try:
            self._collection().document(user_id).set(payload)
        except Exception as error:
            raise GoogleConnectionRepositoryError(
                "Failed to upsert Google connection."
            ) from error

        return payload

    def _collection(self):
        return self._get_firestore_client().collection(self._collection_name)

    def _get_firestore_client(self):
        if self._firestore_client is None:
            try:
                self._firestore_client = resolve_firestore_client(
                    firestore_client=None,
                    project_id=self._project_id,
                    database_id=self._database_id,
                )
            except FirestoreClientHelperError as error:
                raise GoogleConnectionRepositoryError(str(error)) from error
        return self._firestore_client

    @staticmethod
    def _validate_document(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise GoogleConnectionRepositoryError(
                "Google connection document has invalid format."
            )
        if payload.get("provider") != "google":
            raise GoogleConnectionRepositoryError("Invalid Google connection provider.")
        return payload


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
