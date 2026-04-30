import unittest

from services.security.auth_exceptions import ForbiddenError
from services.security.authorization_service import AuthorizationService


class FakeOrganizationRepository:
    def __init__(self) -> None:
        self.org = {"org_id": "org-1", "name": "Org One"}
        self.org_members = {
            ("org-1", "owner"): {"user_id": "owner", "org_role": "OWNER", "status": "active"},
            ("org-1", "member"): {"user_id": "member", "org_role": "MEMBER", "status": "active"},
        }
        self.teams = {
            ("org-1", "team-a"): {"team_id": "team-a", "name": "Team A"},
            ("org-1", "team-b"): {"team_id": "team-b", "name": "Team B"},
        }
        self.team_members = {
            ("org-1", "team-a", "member"): {
                "user_id": "member",
                "team_role": "TEAM_ADMIN",
                "status": "active",
            }
        }

    def get_organization(self, *, org_id: str):
        if org_id == "org-1":
            return dict(self.org)
        return None

    def get_org_member(self, *, org_id: str, user_id: str):
        member = self.org_members.get((org_id, user_id))
        return dict(member) if member else None

    def get_team(self, *, org_id: str, team_id: str):
        team = self.teams.get((org_id, team_id))
        return dict(team) if team else None

    def get_team_member(self, *, org_id: str, team_id: str, user_id: str):
        member = self.team_members.get((org_id, team_id, user_id))
        return dict(member) if member else None


class AuthorizationServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = FakeOrganizationRepository()
        self.service = AuthorizationService(organization_repository=self.repo)

    def test_non_member_is_denied_from_org(self):
        with self.assertRaises(ForbiddenError) as raised:
            self.service.require_org_member(user_id="ghost", org_id="org-1")
        self.assertEqual(raised.exception.reason, "not_org_member")

    def test_owner_can_access_any_team(self):
        membership = self.service.require_team_permission(
            user_id="owner",
            org_id="org-1",
            team_id="team-b",
            permission="team.members.read",
        )
        self.assertEqual(membership["team_role"], "ORG_ADMIN_BYPASS")

    def test_team_admin_of_team_a_cannot_access_team_b(self):
        with self.assertRaises(ForbiddenError) as raised:
            self.service.require_team_permission(
                user_id="member",
                org_id="org-1",
                team_id="team-b",
                permission="team.members.read",
            )
        self.assertEqual(raised.exception.reason, "not_team_member")


if __name__ == "__main__":
    unittest.main()
