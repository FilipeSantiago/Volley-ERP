import os
import uuid
from datetime import datetime, timezone
from typing import Any

from repositories.helpers.firestore_client_helper import (
    FirestoreClientHelperError,
    resolve_firestore_client,
)


class UserRepositoryError(Exception):
    pass


class UserRepository:
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
            "FIRESTORE_USERS_COLLECTION", "users"
        )
        self._project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self._database_id = database_id or os.getenv("FIRESTORE_DATABASE_ID", "customer")

    def get_by_user_id(self, *, user_id: str) -> dict[str, Any] | None:
        try:
            snapshot = self._collection().document(user_id).get()
        except Exception as error:
            raise UserRepositoryError("Failed to fetch user by user_id.") from error

        if not snapshot.exists:
            return None
        return self._validate_document(snapshot.to_dict())

    def get_by_google_sub(self, *, google_sub: str) -> dict[str, Any] | None:
        try:
            query = self._collection().where("google_sub", "==", google_sub).limit(1)
            documents = list(query.stream())
        except Exception as error:
            raise UserRepositoryError("Failed to fetch user by google_sub.") from error

        if not documents:
            return None
        return self._validate_document(documents[0].to_dict())

    def get_by_email(self, *, email: str) -> dict[str, Any] | None:
        try:
            query = self._collection().where("email", "==", email).limit(1)
            documents = list(query.stream())
        except Exception as error:
            raise UserRepositoryError("Failed to fetch user by email.") from error

        if not documents:
            return None
        return self._validate_document(documents[0].to_dict())

    def upsert_from_google_identity(
        self,
        *,
        google_sub: str,
        email: str | None,
        name: str | None,
    ) -> dict[str, Any]:
        existing = self.get_by_google_sub(google_sub=google_sub)
        now = _now_iso()

        if existing is None:
            user_id = str(uuid.uuid4())
            payload = {
                "user_id": user_id,
                "google_sub": google_sub,
                "email": email,
                "name": name,
                "created_at": now,
                "updated_at": now,
                "last_login_at": now,
            }
        else:
            user_id = existing["user_id"]
            payload = {
                **existing,
                "email": email or existing.get("email"),
                "name": name or existing.get("name"),
                "updated_at": now,
                "last_login_at": now,
            }

        try:
            self._collection().document(user_id).set(payload)
        except Exception as error:
            raise UserRepositoryError("Failed to upsert user.") from error

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
                raise UserRepositoryError(str(error)) from error
        return self._firestore_client

    @staticmethod
    def _validate_document(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise UserRepositoryError("User document has invalid format.")
        if not isinstance(payload.get("user_id"), str):
            raise UserRepositoryError("User document does not include user_id.")
        return payload


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
