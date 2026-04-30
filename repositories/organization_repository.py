import os
import uuid
from datetime import datetime, timezone
from typing import Any

from repositories.helpers.firestore_client_helper import (
    FirestoreClientHelperError,
    resolve_firestore_client,
)


class OrganizationRepositoryError(Exception):
    pass


class OrganizationRepository:
    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        organizations_collection_name: str | None = None,
        user_organizations_collection_name: str | None = None,
        project_id: str | None = None,
        database_id: str | None = None,
    ) -> None:
        self._firestore_client = firestore_client
        self._organizations_collection_name = organizations_collection_name or os.getenv(
            "FIRESTORE_ORGANIZATIONS_COLLECTION", "organizations"
        )
        self._user_organizations_collection_name = (
            user_organizations_collection_name
            or os.getenv("FIRESTORE_USER_ORGANIZATIONS_COLLECTION", "user_organizations")
        )
        self._project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self._database_id = database_id or os.getenv("FIRESTORE_DATABASE_ID", "customer")

    def create_organization_with_owner(
        self,
        *,
        name: str,
        owner_user_id: str,
        owner_email: str | None,
    ) -> dict[str, Any]:
        org_id = str(uuid.uuid4())
        now = _now_iso()
        organization = {
            "org_id": org_id,
            "name": name,
            "owner_user_id": owner_user_id,
            "storage_owner_user_id": owner_user_id,
            "workspace_root_folder_id": None,
            "workspace_sheets_folder_id": None,
            "workspace_images_folder_id": None,
            "workspace_exports_folder_id": None,
            "created_at": now,
            "updated_at": now,
        }
        member = {
            "user_id": owner_user_id,
            "email": owner_email,
            "org_role": "OWNER",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        pointer = {
            "org_id": org_id,
            "org_name": name,
            "org_role": "OWNER",
            "status": "active",
            "joined_at": now,
            "updated_at": now,
        }

        try:
            batch = self._get_firestore_client().batch()
            org_ref = self._organizations_collection().document(org_id)
            member_ref = self._org_members_collection(org_id=org_id).document(owner_user_id)
            pointer_ref = self._user_orgs_collection(user_id=owner_user_id).document(org_id)
            batch.set(org_ref, organization)
            batch.set(member_ref, member)
            batch.set(pointer_ref, pointer)
            batch.commit()
        except Exception as error:
            raise OrganizationRepositoryError("Failed to create organization.") from error

        return organization

    def get_organization(self, *, org_id: str) -> dict[str, Any] | None:
        try:
            snapshot = self._organizations_collection().document(org_id).get()
        except Exception as error:
            raise OrganizationRepositoryError("Failed to fetch organization.") from error

        if not snapshot.exists:
            return None
        return self._validate_document(snapshot.to_dict(), "organization")

    def update_organization_workspace_ids(
        self,
        *,
        org_id: str,
        workspace_root_folder_id: str,
        workspace_sheets_folder_id: str,
        workspace_images_folder_id: str,
        workspace_exports_folder_id: str,
    ) -> dict[str, Any]:
        organization = self.get_organization(org_id=org_id)
        if organization is None:
            raise OrganizationRepositoryError("Organization not found.")

        updated = {
            **organization,
            "workspace_root_folder_id": workspace_root_folder_id,
            "workspace_sheets_folder_id": workspace_sheets_folder_id,
            "workspace_images_folder_id": workspace_images_folder_id,
            "workspace_exports_folder_id": workspace_exports_folder_id,
            "updated_at": _now_iso(),
        }

        try:
            self._organizations_collection().document(org_id).set(updated)
        except Exception as error:
            raise OrganizationRepositoryError(
                "Failed to update organization workspace IDs."
            ) from error

        return updated

    def get_org_member(self, *, org_id: str, user_id: str) -> dict[str, Any] | None:
        try:
            snapshot = self._org_members_collection(org_id=org_id).document(user_id).get()
        except Exception as error:
            raise OrganizationRepositoryError("Failed to fetch organization member.") from error

        if not snapshot.exists:
            return None
        return self._validate_document(snapshot.to_dict(), "organization_member")

    def upsert_org_member_and_pointer(
        self,
        *,
        org_id: str,
        user_id: str,
        email: str | None,
        org_role: str,
        status: str = "active",
    ) -> dict[str, Any]:
        organization = self.get_organization(org_id=org_id)
        if organization is None:
            raise OrganizationRepositoryError("Organization not found.")

        existing_member = self.get_org_member(org_id=org_id, user_id=user_id)
        now = _now_iso()
        member = {
            "user_id": user_id,
            "email": email,
            "org_role": org_role,
            "status": status,
            "created_at": existing_member.get("created_at") if existing_member else now,
            "updated_at": now,
        }
        pointer = {
            "org_id": org_id,
            "org_name": organization.get("name"),
            "org_role": org_role,
            "status": status,
            "joined_at": existing_member.get("created_at") if existing_member else now,
            "updated_at": now,
        }

        try:
            batch = self._get_firestore_client().batch()
            member_ref = self._org_members_collection(org_id=org_id).document(user_id)
            pointer_ref = self._user_orgs_collection(user_id=user_id).document(org_id)
            batch.set(member_ref, member)
            batch.set(pointer_ref, pointer)
            batch.commit()
        except Exception as error:
            raise OrganizationRepositoryError(
                "Failed to upsert organization membership."
            ) from error

        return member

    def list_user_organizations(self, *, user_id: str) -> list[dict[str, Any]]:
        try:
            documents = list(self._user_orgs_collection(user_id=user_id).stream())
        except Exception as error:
            raise OrganizationRepositoryError("Failed to list user organizations.") from error

        return [self._validate_document(item.to_dict(), "user_org_pointer") for item in documents]

    def list_org_members(self, *, org_id: str) -> list[dict[str, Any]]:
        try:
            documents = list(self._org_members_collection(org_id=org_id).stream())
        except Exception as error:
            raise OrganizationRepositoryError(
                "Failed to list organization members."
            ) from error

        return [self._validate_document(item.to_dict(), "organization_member") for item in documents]

    def create_team(
        self,
        *,
        org_id: str,
        name: str,
        category: str | None = None,
        gender: str | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        if self.get_organization(org_id=org_id) is None:
            raise OrganizationRepositoryError("Organization not found.")

        team_id = str(uuid.uuid4())
        now = _now_iso()
        payload = {
            "team_id": team_id,
            "name": name,
            "category": category,
            "gender": gender,
            "status": status,
            "team_spreadsheet_id": None,
            "team_spreadsheet_url": None,
            "created_at": now,
            "updated_at": now,
        }

        try:
            self._org_teams_collection(org_id=org_id).document(team_id).set(payload)
        except Exception as error:
            raise OrganizationRepositoryError("Failed to create team.") from error

        return payload

    def update_team_spreadsheet(
        self,
        *,
        org_id: str,
        team_id: str,
        spreadsheet_id: str,
        spreadsheet_url: str | None,
    ) -> dict[str, Any]:
        team = self.get_team(org_id=org_id, team_id=team_id)
        if team is None:
            raise OrganizationRepositoryError("Team not found.")

        updated = {
            **team,
            "team_spreadsheet_id": spreadsheet_id,
            "team_spreadsheet_url": spreadsheet_url,
            "updated_at": _now_iso(),
        }
        try:
            self._org_teams_collection(org_id=org_id).document(team_id).set(updated)
        except Exception as error:
            raise OrganizationRepositoryError(
                "Failed to update team spreadsheet metadata."
            ) from error
        return updated

    def get_team(self, *, org_id: str, team_id: str) -> dict[str, Any] | None:
        try:
            snapshot = self._org_teams_collection(org_id=org_id).document(team_id).get()
        except Exception as error:
            raise OrganizationRepositoryError("Failed to fetch team.") from error

        if not snapshot.exists:
            return None
        return self._validate_document(snapshot.to_dict(), "team")

    def list_teams_for_org(self, *, org_id: str) -> list[dict[str, Any]]:
        try:
            documents = list(self._org_teams_collection(org_id=org_id).stream())
        except Exception as error:
            raise OrganizationRepositoryError("Failed to list teams.") from error

        return [self._validate_document(item.to_dict(), "team") for item in documents]

    def list_user_team_pointers(
        self, *, user_id: str, org_id: str
    ) -> list[dict[str, Any]]:
        try:
            documents = list(self._user_org_teams_collection(user_id=user_id, org_id=org_id).stream())
        except Exception as error:
            raise OrganizationRepositoryError(
                "Failed to list user team memberships."
            ) from error
        return [self._validate_document(item.to_dict(), "user_team_pointer") for item in documents]

    def get_team_member(
        self, *, org_id: str, team_id: str, user_id: str
    ) -> dict[str, Any] | None:
        try:
            snapshot = (
                self._team_members_collection(org_id=org_id, team_id=team_id)
                .document(user_id)
                .get()
            )
        except Exception as error:
            raise OrganizationRepositoryError("Failed to fetch team member.") from error

        if not snapshot.exists:
            return None
        return self._validate_document(snapshot.to_dict(), "team_member")

    def list_team_members(self, *, org_id: str, team_id: str) -> list[dict[str, Any]]:
        try:
            documents = list(
                self._team_members_collection(org_id=org_id, team_id=team_id).stream()
            )
        except Exception as error:
            raise OrganizationRepositoryError("Failed to list team members.") from error

        return [self._validate_document(item.to_dict(), "team_member") for item in documents]

    def upsert_team_member_and_pointer(
        self,
        *,
        org_id: str,
        team_id: str,
        user_id: str,
        email: str | None,
        team_role: str,
        status: str = "active",
    ) -> dict[str, Any]:
        team = self.get_team(org_id=org_id, team_id=team_id)
        if team is None:
            raise OrganizationRepositoryError("Team not found.")

        existing_member = self.get_team_member(org_id=org_id, team_id=team_id, user_id=user_id)
        now = _now_iso()
        member = {
            "user_id": user_id,
            "email": email,
            "team_role": team_role,
            "status": status,
            "created_at": existing_member.get("created_at") if existing_member else now,
            "updated_at": now,
        }
        pointer = {
            "team_id": team_id,
            "team_name": team.get("name"),
            "team_role": team_role,
            "status": status,
            "joined_at": existing_member.get("created_at") if existing_member else now,
            "updated_at": now,
        }

        try:
            batch = self._get_firestore_client().batch()
            member_ref = self._team_members_collection(org_id=org_id, team_id=team_id).document(
                user_id
            )
            pointer_ref = self._user_org_teams_collection(user_id=user_id, org_id=org_id).document(
                team_id
            )
            batch.set(member_ref, member)
            batch.set(pointer_ref, pointer)
            batch.commit()
        except Exception as error:
            raise OrganizationRepositoryError("Failed to upsert team membership.") from error

        return member

    def set_org_member_status(
        self, *, org_id: str, user_id: str, status: str
    ) -> dict[str, Any]:
        member = self.get_org_member(org_id=org_id, user_id=user_id)
        if member is None:
            raise OrganizationRepositoryError("Organization member not found.")

        updated_member = {
            **member,
            "status": status,
            "updated_at": _now_iso(),
        }
        pointer_ref = self._user_orgs_collection(user_id=user_id).document(org_id)

        try:
            batch = self._get_firestore_client().batch()
            batch.set(
                self._org_members_collection(org_id=org_id).document(user_id),
                updated_member,
            )
            pointer_snapshot = pointer_ref.get()
            if pointer_snapshot.exists:
                pointer = self._validate_document(pointer_snapshot.to_dict(), "user_org_pointer")
                batch.set(
                    pointer_ref,
                    {**pointer, "status": status, "updated_at": updated_member["updated_at"]},
                )
            batch.commit()
        except Exception as error:
            raise OrganizationRepositoryError("Failed to update member status.") from error

        return updated_member

    def remove_user_team_pointer(self, *, user_id: str, org_id: str, team_id: str) -> None:
        try:
            self._user_org_teams_collection(user_id=user_id, org_id=org_id).document(team_id).delete()
        except Exception as error:
            raise OrganizationRepositoryError("Failed to remove user team pointer.") from error

    def set_team_member_status(
        self,
        *,
        org_id: str,
        team_id: str,
        user_id: str,
        status: str,
    ) -> dict[str, Any]:
        member = self.get_team_member(org_id=org_id, team_id=team_id, user_id=user_id)
        if member is None:
            raise OrganizationRepositoryError("Team member not found.")

        updated_member = {
            **member,
            "status": status,
            "updated_at": _now_iso(),
        }
        try:
            self._team_members_collection(org_id=org_id, team_id=team_id).document(user_id).set(
                updated_member
            )
        except Exception as error:
            raise OrganizationRepositoryError("Failed to update team member status.") from error
        return updated_member

    def _organizations_collection(self):
        return self._get_firestore_client().collection(self._organizations_collection_name)

    def _org_members_collection(self, *, org_id: str):
        return self._organizations_collection().document(org_id).collection("members")

    def _org_invites_collection(self, *, org_id: str):
        return self._organizations_collection().document(org_id).collection("invites")

    def _org_teams_collection(self, *, org_id: str):
        return self._organizations_collection().document(org_id).collection("teams")

    def _team_members_collection(self, *, org_id: str, team_id: str):
        return self._org_teams_collection(org_id=org_id).document(team_id).collection("members")

    def _user_orgs_root_collection(self):
        return self._get_firestore_client().collection(self._user_organizations_collection_name)

    def _user_orgs_collection(self, *, user_id: str):
        return self._user_orgs_root_collection().document(user_id).collection("orgs")

    def _user_org_teams_collection(self, *, user_id: str, org_id: str):
        return self._user_orgs_collection(user_id=user_id).document(org_id).collection("teams")

    def _get_firestore_client(self):
        if self._firestore_client is None:
            try:
                self._firestore_client = resolve_firestore_client(
                    firestore_client=None,
                    project_id=self._project_id,
                    database_id=self._database_id,
                )
            except FirestoreClientHelperError as error:
                raise OrganizationRepositoryError(str(error)) from error
        return self._firestore_client

    @staticmethod
    def _validate_document(payload: Any, kind: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise OrganizationRepositoryError(f"{kind} document has invalid format.")
        return payload


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
