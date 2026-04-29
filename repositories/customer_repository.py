import os
import uuid
from datetime import datetime, timezone
from typing import Any


class CustomerRepositoryError(Exception):
    pass


class CustomerRepository:
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
            "FIRESTORE_CUSTOMERS_COLLECTION", "customers"
        )
        self._project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self._database_id = database_id or os.getenv("FIRESTORE_DATABASE_ID", "customer")

    def get_by_google_sub(self, *, google_sub: str) -> dict[str, Any] | None:
        try:
            snapshot = self._collection().document(google_sub).get()
        except Exception as error:
            raise CustomerRepositoryError("Failed to fetch customer by google_sub.") from error

        if not snapshot.exists:
            return None
        return self._validate_customer_document(snapshot.to_dict())

    def get_by_customer_id(self, *, customer_id: str) -> dict[str, Any] | None:
        try:
            query = self._collection().where("customer_id", "==", customer_id).limit(1)
            documents = list(query.stream())
        except Exception as error:
            raise CustomerRepositoryError("Failed to fetch customer by customer_id.") from error

        if not documents:
            return None
        return self._validate_customer_document(documents[0].to_dict())

    def upsert_by_google_sub(
        self,
        *,
        google_sub: str,
        email: str | None,
        refresh_token_enc: str,
    ) -> dict[str, Any]:
        now = _now_iso()
        document_ref = self._collection().document(google_sub)

        try:
            snapshot = document_ref.get()
        except Exception as error:
            raise CustomerRepositoryError("Failed to fetch customer for upsert.") from error

        if not snapshot.exists:
            customer = {
                "customer_id": str(uuid.uuid4()),
                "google_sub": google_sub,
                "email": email,
                "refresh_token_enc": refresh_token_enc,
                "doc_id": None,
                "created_at": now,
                "updated_at": now,
            }
        else:
            existing = self._validate_customer_document(snapshot.to_dict())
            customer = {
                **existing,
                "email": email or existing.get("email"),
                "refresh_token_enc": refresh_token_enc,
                "updated_at": now,
            }

        try:
            document_ref.set(customer)
        except Exception as error:
            raise CustomerRepositoryError("Failed to upsert customer.") from error

        return customer

    def update_doc_id(self, *, customer_id: str, doc_id: str | None) -> dict[str, Any]:
        now = _now_iso()

        try:
            query = self._collection().where("customer_id", "==", customer_id).limit(1)
            documents = list(query.stream())
        except Exception as error:
            raise CustomerRepositoryError("Failed to fetch customer for doc update.") from error

        if not documents:
            raise CustomerRepositoryError("Customer not found.")

        document = documents[0]
        current = self._validate_customer_document(document.to_dict())
        updated = {
            **current,
            "doc_id": doc_id,
            "updated_at": now,
        }

        try:
            document.reference.set(updated)
        except Exception as error:
            raise CustomerRepositoryError("Failed to update customer doc_id.") from error

        return updated

    def _collection(self):
        return self._get_firestore_client().collection(self._collection_name)

    def _get_firestore_client(self):
        if self._firestore_client is not None:
            return self._firestore_client

        try:
            from google.cloud import firestore
        except ModuleNotFoundError as error:
            raise CustomerRepositoryError(
                "google-cloud-firestore is not installed."
            ) from error

        try:
            client_kwargs: dict[str, Any] = {}
            if self._project_id:
                client_kwargs["project"] = self._project_id
            if self._database_id:
                client_kwargs["database"] = self._database_id
            self._firestore_client = firestore.Client(**client_kwargs)
        except Exception as error:
            raise CustomerRepositoryError("Failed to initialize Firestore client.") from error

        return self._firestore_client

    @staticmethod
    def _validate_customer_document(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise CustomerRepositoryError("Customer document has invalid format.")
        return payload


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
