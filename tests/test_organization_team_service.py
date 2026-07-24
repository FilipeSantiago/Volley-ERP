import unittest

from services.organization_team_service import OrganizationTeamService
from services.security.auth_config import AuthConfig
from services.security.auth_exceptions import ForbiddenError


class FakeAuthorizationService:
    def __init__(self, *, can_access_all_teams: bool) -> None:
        self._can_access_all_teams = can_access_all_teams
        self.team_permission_calls: list[tuple[str, str, str, str]] = []
        self.can_access_all_calls: list[tuple[str, str]] = []

    def require_team_permission(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
        permission: str,
    ) -> dict[str, str]:
        self.team_permission_calls.append((user_id, org_id, team_id, permission))
        return {"team_role": "TEAM_ADMIN", "status": "active"}

    def can_access_all_teams(self, *, user_id: str, org_id: str) -> bool:
        self.can_access_all_calls.append((user_id, org_id))
        return self._can_access_all_teams

    def require_org_member(self, *, user_id: str, org_id: str) -> dict[str, str]:
        return {"org_role": "ADMIN", "status": "active"}


class FakeOrganizationRepository:
    def __init__(self) -> None:
        self.organization = {
            "org_id": "org-1",
            "name": "Org One",
            "storage_owner_user_id": "storage-owner-1",
        }
        self.teams = {
            ("org-1", "team-a"): {
                "team_id": "team-a",
                "name": "Team A",
                "status": "active",
                "team_spreadsheet_id": "sheet-a",
                "team_spreadsheet_url": "https://sheet-a",
            },
            ("org-1", "team-b"): {
                "team_id": "team-b",
                "name": "Team B",
                "status": "active",
                "team_spreadsheet_id": "sheet-b",
                "team_spreadsheet_url": "https://sheet-b",
            },
            ("org-1", "team-c"): {
                "team_id": "team-c",
                "name": "Team C",
                "status": "inactive",
                "team_spreadsheet_id": "sheet-c",
                "team_spreadsheet_url": "https://sheet-c",
            },
        }
        self.user_team_pointers: dict[tuple[str, str], list[dict]] = {}

    def get_organization(self, *, org_id: str):
        if org_id != "org-1":
            return None
        return dict(self.organization)

    def get_team(self, *, org_id: str, team_id: str):
        team = self.teams.get((org_id, team_id))
        return dict(team) if team else None

    def list_teams_for_org(self, *, org_id: str):
        return [
            dict(team)
            for (stored_org_id, _), team in self.teams.items()
            if stored_org_id == org_id
        ]

    def list_user_team_pointers(self, *, user_id: str, org_id: str):
        return list(self.user_team_pointers.get((user_id, org_id), []))


class FakeGoogleConnectionRepository:
    def get_by_user_id(self, *, user_id: str):
        if user_id != "storage-owner-1":
            return None
        return {"encrypted_refresh_token": "enc-token"}


class FakeRefreshTokenEncryptionService:
    def decrypt(self, encrypted_refresh_token: str) -> str:
        if encrypted_refresh_token != "enc-token":
            raise ValueError("Unexpected refresh token payload.")
        return "refresh-token"


class FakeTeamWorkspaceRepository:
    def __init__(self) -> None:
        self.requests: list[str] = []
        self.rows_by_sheet = {
            "sheet-a": [
                {
                    "athlete_id": "athlete-a-1",
                    "full_name": "Athlete A1",
                    "birthday": "2000-01-01",
                    "cpf": "111",
                    "cellphone": "555-1111",
                    "position": "Central",
                }
            ],
            "sheet-b": [
                {
                    "athlete_id": "athlete-b-1",
                    "full_name": "Athlete B1",
                    "birthday": "2001-01-01",
                    "cpf": "222",
                    "cellphone": "555-2222",
                    "position": "Ponteiro",
                }
            ],
        }

    def list_team_athletes(
        self,
        *,
        spreadsheet_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ):
        self.requests.append(spreadsheet_id)
        return {"items": list(self.rows_by_sheet.get(spreadsheet_id, []))}


class FakeUserRepository:
    pass


class FakeWorkspaceService:
    pass


class FakeInviteService:
    pass


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


class OrganizationTeamServiceTestCase(unittest.TestCase):
    def _build_service(
        self,
        *,
        can_access_all_teams: bool,
    ) -> tuple[OrganizationTeamService, FakeAuthorizationService]:
        authorization_service = FakeAuthorizationService(
            can_access_all_teams=can_access_all_teams
        )
        service = OrganizationTeamService(
            auth_config=_build_auth_config(),
            organization_repository=FakeOrganizationRepository(),
            user_repository=FakeUserRepository(),
            google_connection_repository=FakeGoogleConnectionRepository(),
            team_workspace_repository=FakeTeamWorkspaceRepository(),
            refresh_token_encryption_service=FakeRefreshTokenEncryptionService(),
            workspace_service=FakeWorkspaceService(),
            authorization_service=authorization_service,
            invite_service=FakeInviteService(),
        )
        return service, authorization_service

    def test_list_athletes_team_scope_still_requires_team_permission(self):
        service, authorization_service = self._build_service(can_access_all_teams=False)

        result = service.list_athletes(user_id="user-1", org_id="org-1", team_id="team-a")

        self.assertEqual(len(authorization_service.team_permission_calls), 1)
        self.assertEqual(result["team_id"], "team-a")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["team_id"], "team-a")
        self.assertEqual(result["items"][0]["org_id"], "org-1")

    def test_list_athletes_org_scope_aggregates_all_accessible_teams_for_admin(self):
        service, authorization_service = self._build_service(can_access_all_teams=True)

        result = service.list_athletes(user_id="user-1", org_id="org-1", team_id=None)

        self.assertEqual(len(authorization_service.team_permission_calls), 0)
        self.assertEqual(result["team_id"], None)
        self.assertEqual(result["athletes_sheet_id"], None)
        self.assertEqual(result["count"], 2)
        self.assertEqual({item["team_id"] for item in result["items"]}, {"team-a", "team-b"})

    def test_list_athletes_org_scope_forbidden_for_non_admin(self):
        service, _ = self._build_service(can_access_all_teams=False)

        with self.assertRaises(ForbiddenError) as raised:
            service.list_athletes(user_id="user-1", org_id="org-1", team_id=None)

        self.assertEqual(raised.exception.reason, "team_scope_required")

    def test_list_teams_for_org_admin_returns_all_active_teams(self):
        service, _ = self._build_service(can_access_all_teams=True)

        result = service.list_teams(user_id="user-1", org_id="org-1")

        self.assertEqual(result["count"], 2)
        self.assertEqual(
            {team["team_id"] for team in result["items"]},
            {"team-a", "team-b"},
        )
        self.assertEqual(
            {team["team_role"] for team in result["items"]},
            {"ORG_ADMIN"},
        )


if __name__ == "__main__":
    unittest.main()
