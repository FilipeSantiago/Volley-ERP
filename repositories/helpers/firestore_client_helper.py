import os
from typing import Any


class FirestoreClientHelperError(Exception):
    pass


def resolve_firestore_client(
    *,
    firestore_client: Any | None,
    project_id: str | None = None,
    database_id: str | None = None,
) -> Any:
    if firestore_client is not None:
        return firestore_client

    resolved_project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
    resolved_database_id = database_id or os.getenv("FIRESTORE_DATABASE_ID", "customer")

    try:
        from google.cloud import firestore
    except ModuleNotFoundError as error:
        raise FirestoreClientHelperError(
            "google-cloud-firestore is not installed."
        ) from error

    try:
        client_kwargs: dict[str, Any] = {}
        if resolved_project_id:
            client_kwargs["project"] = resolved_project_id
        if resolved_database_id:
            client_kwargs["database"] = resolved_database_id
        return firestore.Client(**client_kwargs)
    except Exception as error:
        raise FirestoreClientHelperError(
            f"Failed to initialize Firestore client: {error}"
        ) from error
