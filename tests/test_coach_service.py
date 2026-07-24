import unittest

from repositories.coach_repository import CoachRepositoryError
from services.coach_service import CoachService
from services.security.auth_config import AuthConfig
from services.security.auth_exceptions import ForbiddenError


class FakeAuthorizationService:
    def __init__(self, *, org_role: str = "ADMIN") -> None:
        self._org_role = org_role

    def require_org_role(
        self,
        *,
        user_id: str,
        org_id: str,
        allowed_roles: set[str],
    ):
        if self._org_role not in allowed_roles:
            raise ForbiddenError("insufficient_org_role")
        return {"user_id": user_id, "org_role": self._org_role, "status": "active"}

    def require_team_permission(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
        permission: str,
    ):
        return {"team_role": "TEAM_ADMIN", "status": "active"}


class FakeOrganizationRepository:
    def __init__(self) -> None:
        self.organization = {
            "org_id": "org-1",
            "name": "Org One",
            "storage_owner_user_id": "storage-owner-1",
        }
        self.teams = {
            ("org-1", "team-1"): {
                "team_id": "team-1",
                "name": "Team One",
                "team_spreadsheet_id": "sheet-1",
                "team_spreadsheet_url": "https://sheet",
            }
        }

    def get_organization(self, *, org_id: str):
        if org_id != "org-1":
            return None
        return dict(self.organization)

    def get_team(self, *, org_id: str, team_id: str):
        team = self.teams.get((org_id, team_id))
        return dict(team) if team else None


class FakeGoogleConnectionRepository:
    def get_by_user_id(self, *, user_id: str):
        if user_id != "storage-owner-1":
            return None
        return {"encrypted_refresh_token": "enc-token"}


class FakeRefreshTokenEncryptionService:
    def decrypt(self, encrypted_refresh_token: str) -> str:
        if encrypted_refresh_token != "enc-token":
            raise ValueError("unexpected token")
        return "refresh-token"


class FakeWorkspaceService:
    def ensure_workspace_for_organization(self, *, org_id: str):
        return {"workspace_images_folder_id": "images-1"}


class InMemoryCoachRepository:
    def __init__(self) -> None:
        self.by_spreadsheet: dict[str, dict] = {}

    def get_team_coach(
        self,
        *,
        spreadsheet_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ):
        coach = self.by_spreadsheet.get(spreadsheet_id)
        return dict(coach) if coach else None

    def upsert_team_coach(
        self,
        *,
        spreadsheet_id: str,
        team_id: str,
        images_folder_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        coach: dict,
    ):
        existing = self.by_spreadsheet.get(spreadsheet_id)
        created_at = existing.get("created_at") if existing else "2026-01-01T00:00:00Z"
        updated = {
            "full_name": coach["full_name"],
            "birthday": coach["birthday"],
            "cpf": coach["cpf"],
            "cellphone": coach["cellphone"],
            "tshirt_size": coach.get("tshirt_size"),
            "shorts_size": coach.get("shorts_size"),
            "position": coach["position"],
            "rg": coach.get("rg"),
            "email": coach.get("email"),
            "pix_key": coach["pix_key"],
            "photo_link": "https://drive.google.com/file/d/coach-photo/view",
            "created_at": created_at,
            "updated_at": "2026-01-02T00:00:00Z",
        }
        self.by_spreadsheet[spreadsheet_id] = updated
        return dict(updated)

    def get_team_coach_photo(
        self,
        *,
        spreadsheet_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ):
        coach = self.by_spreadsheet.get(spreadsheet_id)
        if coach is None:
            return None
        return {
            "content": b"fake-image",
            "mime_type": "image/jpeg",
            "file_name": "coach.jpg",
            "photo_link": coach.get("photo_link"),
            "full_name": coach.get("full_name"),
        }


def _build_auth_config() -> AuthConfig:
    return AuthConfig(
        google_oauth_client_id="test-client-id",
        google_oauth_client_secret="test-client-secret",
        google_oauth_redirect_uri="https://api.example.com/auth/google/callback",
        google_oauth_android_client_id=None,
        google_oauth_android_client_secret=None,
        google_oauth_ios_client_id=None,
        google_oauth_ios_client_secret=None,
        auth_state_secret="state-secret",
        jwt_access_secret="jwt-access-secret-jwt-access-secret-123",
        jwt_refresh_secret="jwt-refresh-secret-jwt-refresh-secret-123",
        jwt_issuer="volley-erp",
        jwt_audience="volley-erp-client",
        jwt_access_ttl_seconds=600,
        jwt_refresh_ttl_seconds=604800,
        auth_redirect_allowed_origins=["https://app.example.com"],
        auth_redirect_allowed_schemes=["myapp"],
        auth_mobile_allowed_platforms=["android", "ios"],
        auth_mobile_redirect_allowed_android=[],
        auth_mobile_redirect_allowed_ios=[],
        token_enc_key="enc-key",
        token_enc_key_secret_name=None,
        invite_token_ttl_seconds=604800,
        app_public_base_url="https://app.example.com",
    )


class CoachServiceTestCase(unittest.TestCase):
    def _build_service(
        self,
        *,
        org_role: str = "ADMIN",
        repository: InMemoryCoachRepository | None = None,
    ) -> CoachService:
        return CoachService(
            auth_config=_build_auth_config(),
            organization_repository=FakeOrganizationRepository(),
            google_connection_repository=FakeGoogleConnectionRepository(),
            coach_repository=repository or InMemoryCoachRepository(),
            refresh_token_encryption_service=FakeRefreshTokenEncryptionService(),
            authorization_service=FakeAuthorizationService(org_role=org_role),
            workspace_service=FakeWorkspaceService(),
        )

    def setUp(self) -> None:
        self.repository = InMemoryCoachRepository()
        self.service = self._build_service(
            org_role="ADMIN",
            repository=self.repository,
        )

    def test_create_and_get_coach(self):
        created = self.service.create_coach(
            user_id="user-1",
            org_id="org-1",
            team_id="team-1",
            payload={
                "full_name": "Coach One",
                "birthday": "1980-01-01",
                "cpf": "123",
                "cellphone": "555-0101",
                "position": "Central",
                "pix_key": "coach@pix",
                "photo_filename": "coach.jpg",
                "photo_mime_type": "image/jpeg",
                "photo_content": b"fake-image",
            },
        )
        loaded = self.service.get_coach(
            user_id="user-1",
            org_id="org-1",
            team_id="team-1",
        )
        self.assertEqual(created["team_id"], "team-1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["pix_key"], "coach@pix")

    def test_update_coach_returns_none_when_missing(self):
        result = self.service.update_coach(
            user_id="user-1",
            org_id="org-1",
            team_id="team-1",
            payload={
                "full_name": "Coach One",
                "birthday": "1980-01-01",
                "cpf": "123",
                "cellphone": "555-0101",
                "position": "Central",
                "pix_key": "coach@pix",
            },
        )
        self.assertIsNone(result)

    def test_create_coach_requires_org_admin_role(self):
        non_admin_service = self._build_service(
            org_role="MEMBER",
            repository=self.repository,
        )
        with self.assertRaises(ForbiddenError) as raised:
            non_admin_service.create_coach(
                user_id="user-1",
                org_id="org-1",
                team_id="team-1",
                payload={
                    "full_name": "Coach One",
                    "birthday": "1980-01-01",
                    "cpf": "123",
                    "cellphone": "555-0101",
                    "position": "Central",
                    "pix_key": "coach@pix",
                    "photo_filename": "coach.jpg",
                    "photo_mime_type": "image/jpeg",
                    "photo_content": b"fake-image",
                },
            )
        self.assertEqual(raised.exception.reason, "insufficient_org_role")

    def test_update_coach_requires_org_admin_role(self):
        non_admin_service = self._build_service(
            org_role="MEMBER",
            repository=self.repository,
        )
        with self.assertRaises(ForbiddenError) as raised:
            non_admin_service.update_coach(
                user_id="user-1",
                org_id="org-1",
                team_id="team-1",
                payload={
                    "full_name": "Coach One",
                    "birthday": "1980-01-01",
                    "cpf": "123",
                    "cellphone": "555-0101",
                    "position": "Central",
                    "pix_key": "coach@pix",
                },
            )
        self.assertEqual(raised.exception.reason, "insufficient_org_role")

    def test_get_coach_allows_non_org_admin_read(self):
        self.service.create_coach(
            user_id="user-1",
            org_id="org-1",
            team_id="team-1",
            payload={
                "full_name": "Coach One",
                "birthday": "1980-01-01",
                "cpf": "123",
                "cellphone": "555-0101",
                "position": "Central",
                "pix_key": "coach@pix",
                "photo_filename": "coach.jpg",
                "photo_mime_type": "image/jpeg",
                "photo_content": b"fake-image",
            },
        )
        non_admin_service = self._build_service(
            org_role="MEMBER",
            repository=self.repository,
        )
        loaded = non_admin_service.get_coach(
            user_id="user-1",
            org_id="org-1",
            team_id="team-1",
        )
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["full_name"], "Coach One")

    def test_update_coach_replaces_existing_record(self):
        self.service.create_coach(
            user_id="user-1",
            org_id="org-1",
            team_id="team-1",
            payload={
                "full_name": "Coach One",
                "birthday": "1980-01-01",
                "cpf": "123",
                "cellphone": "555-0101",
                "position": "Central",
                "pix_key": "coach@pix",
                "photo_filename": "coach.jpg",
                "photo_mime_type": "image/jpeg",
                "photo_content": b"fake-image",
            },
        )
        updated = self.service.update_coach(
            user_id="user-1",
            org_id="org-1",
            team_id="team-1",
            payload={
                "full_name": "Coach Two",
                "birthday": "1981-01-01",
                "cpf": "999",
                "cellphone": "555-9999",
                "position": "Ponteiro",
                "pix_key": "coach-two@pix",
            },
        )
        loaded = self.service.get_coach(
            user_id="user-1",
            org_id="org-1",
            team_id="team-1",
        )
        self.assertIsNotNone(updated)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["full_name"], "Coach Two")
        self.assertEqual(loaded["pix_key"], "coach-two@pix")

    def test_get_coach_photo(self):
        self.service.create_coach(
            user_id="user-1",
            org_id="org-1",
            team_id="team-1",
            payload={
                "full_name": "Coach One",
                "birthday": "1980-01-01",
                "cpf": "123",
                "cellphone": "555-0101",
                "position": "Central",
                "pix_key": "coach@pix",
                "photo_filename": "coach.jpg",
                "photo_mime_type": "image/jpeg",
                "photo_content": b"fake-image",
            },
        )
        photo = self.service.get_coach_photo(
            user_id="user-1",
            org_id="org-1",
            team_id="team-1",
        )
        self.assertIsNotNone(photo)
        self.assertEqual(photo["mime_type"], "image/jpeg")
        self.assertEqual(photo["content"], b"fake-image")


if __name__ == "__main__":
    unittest.main()
