import os
import uuid
from datetime import datetime, timezone
from typing import Any

from repositories.helpers.firestore_client_helper import (
    FirestoreClientHelperError,
    resolve_firestore_client,
)


class InviteRepositoryError(Exception):
    pass


class InviteRepository:
    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        organizations_collection_name: str | None = None,
        project_id: str | None = None,
        database_id: str | None = None,
    ) -> None:
        self._firestore_client = firestore_client
        self._organizations_collection_name = organizations_collection_name or os.getenv(
            "FIRESTORE_ORGANIZATIONS_COLLECTION", "organizations"
        )
        self._project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self._database_id = database_id or os.getenv("FIRESTORE_DATABASE_ID", "customer")

    def create_invite(
        self,
        *,
        org_id: str,
        invited_email: str,
        scope: str,
        token_hash: str,
        expires_at: str,
        invited_by_user_id: str,
        org_role: str | None = None,
        team_id: str | None = None,
        team_role: str | None = None,
    ) -> dict[str, Any]:
        invite_id = str(uuid.uuid4())
        now = _now_iso()
        payload = {
            "invite_id": invite_id,
            "org_id": org_id,
            "invited_email": invited_email,
            "scope": scope,
            "org_role": org_role,
            "team_id": team_id,
            "team_role": team_role,
            "token_hash": token_hash,
            "status": "pending",
            "expires_at": expires_at,
            "invited_by_user_id": invited_by_user_id,
            "created_at": now,
            "accepted_at": None,
        }

        try:
            self._org_invites_collection(org_id=org_id).document(invite_id).set(payload)
        except Exception as error:
            raise InviteRepositoryError("Failed to create invite.") from error

        return payload

    def get_invite(self, *, org_id: str, invite_id: str) -> dict[str, Any] | None:
        try:
            snapshot = self._org_invites_collection(org_id=org_id).document(invite_id).get()
        except Exception as error:
            raise InviteRepositoryError("Failed to fetch invite.") from error

        if not snapshot.exists:
            return None
        return self._validate_document(snapshot.to_dict())

    def find_pending_invite_by_token_hash(self, *, token_hash: str) -> dict[str, Any] | None:
        return self.find_invite_by_token_hash(token_hash=token_hash, only_pending=True)

    def find_invite_by_token_hash(
        self, *, token_hash: str, only_pending: bool = False
    ) -> dict[str, Any] | None:
        try:
            query = self._get_firestore_client().collection_group("invites").where(
                "token_hash", "==", token_hash
            )
            if only_pending:
                query = query.where("status", "==", "pending")
            query = query.limit(1)
            documents = list(query.stream())
        except Exception as error:
            raise InviteRepositoryError("Failed to locate invite token.") from error

        if not documents:
            return None
        invite = self._validate_document(documents[0].to_dict())
        # Keep reference path for updates in transaction-aware flows.
        invite["_path"] = documents[0].reference.path
        return invite

    def revoke_pending_invites_for_scope(
        self,
        *,
        org_id: str,
        invited_email: str,
        scope: str,
        team_id: str | None = None,
    ) -> None:
        try:
            query = (
                self._org_invites_collection(org_id=org_id)
                .where("invited_email", "==", invited_email)
                .where("scope", "==", scope)
                .where("status", "==", "pending")
            )
            if team_id is not None:
                query = query.where("team_id", "==", team_id)
            documents = list(query.stream())
            if not documents:
                return

            batch = self._get_firestore_client().batch()
            for document in documents:
                payload = self._validate_document(document.to_dict())
                batch.set(
                    document.reference,
                    {**payload, "status": "revoked"},
                )
            batch.commit()
        except Exception as error:
            raise InviteRepositoryError("Failed to revoke pending invites.") from error

    def mark_invite_accepted(self, *, org_id: str, invite_id: str) -> dict[str, Any]:
        invite = self.get_invite(org_id=org_id, invite_id=invite_id)
        if invite is None:
            raise InviteRepositoryError("Invite not found.")

        updated = {
            **invite,
            "status": "accepted",
            "accepted_at": _now_iso(),
        }
        try:
            self._org_invites_collection(org_id=org_id).document(invite_id).set(updated)
        except Exception as error:
            raise InviteRepositoryError("Failed to accept invite.") from error
        return updated

    def _organizations_collection(self):
        return self._get_firestore_client().collection(self._organizations_collection_name)

    def _org_invites_collection(self, *, org_id: str):
        return self._organizations_collection().document(org_id).collection("invites")

    def _get_firestore_client(self):
        if self._firestore_client is None:
            try:
                self._firestore_client = resolve_firestore_client(
                    firestore_client=None,
                    project_id=self._project_id,
                    database_id=self._database_id,
                )
            except FirestoreClientHelperError as error:
                raise InviteRepositoryError(str(error)) from error
        return self._firestore_client

    @staticmethod
    def _validate_document(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise InviteRepositoryError("Invite document has invalid format.")
        return payload


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
