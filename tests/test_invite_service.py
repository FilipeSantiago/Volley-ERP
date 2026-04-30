import unittest
from datetime import datetime, timedelta, timezone

from services.security.auth_config import AuthConfig
from services.security.auth_exceptions import InviteEmailMismatchError
from services.security.invite_service import InviteService
from services.security.invite_token_service import InviteTokenService


def _build_auth_config() -> AuthConfig:
    return AuthConfig(
        google_oauth_client_id="web-client-id",
        google_oauth_client_secret="web-client-secret",
        google_oauth_redirect_uri="https://api.example.com/auth/google/callback",
        google_oauth_android_client_id="android-client-id",
        google_oauth_android_client_secret="android-client-secret",
        google_oauth_ios_client_id="ios-client-id",
        google_oauth_ios_client_secret="ios-client-secret",
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
        auth_mobile_redirect_allowed_android=["com.example.android:/oauth2redirect"],
        auth_mobile_redirect_allowed_ios=["com.example.ios:/oauth2redirect"],
        token_enc_key="test-token-encryption-key",
        token_enc_key_secret_name=None,
        invite_token_ttl_seconds=604800,
        app_public_base_url="https://app.example.com",
    )


class FakeInviteRepository:
    def __init__(self) -> None:
        self.invites = {}
        self.last_payload = None

    def revoke_pending_invites_for_scope(self, *, org_id: str, invited_email: str, scope: str, team_id: str | None = None):
        return None

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
    ):
        payload = {
            "invite_id": "invite-1",
            "org_id": org_id,
            "invited_email": invited_email,
            "scope": scope,
            "org_role": org_role,
            "team_id": team_id,
            "team_role": team_role,
            "token_hash": token_hash,
            "status": "pending",
            "expires_at": expires_at,
        }
        self.last_payload = dict(payload)
        self.invites[token_hash] = dict(payload)
        return dict(payload)

    def find_invite_by_token_hash(self, *, token_hash: str, only_pending: bool = False):
        invite = self.invites.get(token_hash)
        if invite is None:
            return None
        if only_pending and invite.get("status") != "pending":
            return None
        return dict(invite)

    def mark_invite_accepted(self, *, org_id: str, invite_id: str):
        for key, invite in self.invites.items():
            if invite["invite_id"] == invite_id and invite["org_id"] == org_id:
                invite["status"] = "accepted"
                return dict(invite)
        raise ValueError("invite not found")


class FakeOrganizationRepository:
    def __init__(self) -> None:
        self.org_members = {}
        self.team_members = {}

    def upsert_org_member_and_pointer(
        self,
        *,
        org_id: str,
        user_id: str,
        email: str | None,
        org_role: str,
        status: str = "active",
    ):
        self.org_members[(org_id, user_id)] = {
            "user_id": user_id,
            "org_role": org_role,
            "status": status,
        }
        return dict(self.org_members[(org_id, user_id)])

    def get_org_member(self, *, org_id: str, user_id: str):
        member = self.org_members.get((org_id, user_id))
        return dict(member) if member else None

    def upsert_team_member_and_pointer(
        self,
        *,
        org_id: str,
        team_id: str,
        user_id: str,
        email: str | None,
        team_role: str,
        status: str = "active",
    ):
        self.team_members[(org_id, team_id, user_id)] = {
            "user_id": user_id,
            "team_role": team_role,
            "status": status,
        }
        return dict(self.team_members[(org_id, team_id, user_id)])


class FakeUserRepository:
    def __init__(self) -> None:
        self.users = {
            "owner": {"user_id": "owner", "email": "owner@example.com"},
            "guest": {"user_id": "guest", "email": "guest@example.com"},
        }

    def get_by_user_id(self, *, user_id: str):
        user = self.users.get(user_id)
        return dict(user) if user else None

    def get_by_email(self, *, email: str):
        for user in self.users.values():
            if user.get("email") == email:
                return dict(user)
        return None


class FakeAuthorizationService:
    def require_org_member(self, *, user_id: str, org_id: str):
        return {"org_role": "OWNER", "status": "active"}

    def require_team_role(self, *, user_id: str, org_id: str, team_id: str, allowed_roles: set[str]):
        return {"team_role": "TEAM_ADMIN", "status": "active"}


class InviteServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.invite_repo = FakeInviteRepository()
        self.org_repo = FakeOrganizationRepository()
        self.user_repo = FakeUserRepository()
        self.token_service = InviteTokenService(signing_secret="state-secret")
        self.service = InviteService(
            auth_config=_build_auth_config(),
            invite_repository=self.invite_repo,
            organization_repository=self.org_repo,
            user_repository=self.user_repo,
            authorization_service=FakeAuthorizationService(),
            invite_token_service=self.token_service,
        )

    def test_create_team_invite_stores_hash_only(self):
        result = self.service.create_invite(
            user_id="owner",
            org_id="org-1",
            payload={"email": "guest@example.com", "team_id": "team-a", "team_role": "PLAYER"},
        )
        self.assertEqual(result["invite_id"], "invite-1")
        self.assertNotIn("token=", self.invite_repo.last_payload["token_hash"])
        self.assertNotEqual(self.invite_repo.last_payload["token_hash"], result["invite_url"])

    def test_accept_team_invite_creates_memberships(self):
        token = "test-token"
        token_hash = self.token_service.hash_token(token=token)
        expires = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
        self.invite_repo.invites[token_hash] = {
            "invite_id": "invite-1",
            "org_id": "org-1",
            "invited_email": "guest@example.com",
            "scope": "team",
            "team_id": "team-a",
            "team_role": "PLAYER",
            "token_hash": token_hash,
            "status": "pending",
            "expires_at": expires.isoformat().replace("+00:00", "Z"),
        }
        result = self.service.accept_invite(user_id="guest", token=token)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["team_id"], "team-a")
        self.assertIn(("org-1", "guest"), self.org_repo.org_members)

    def test_accept_invite_requires_matching_email(self):
        token = "test-token-2"
        token_hash = self.token_service.hash_token(token=token)
        expires = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
        self.invite_repo.invites[token_hash] = {
            "invite_id": "invite-2",
            "org_id": "org-1",
            "invited_email": "different@example.com",
            "scope": "org",
            "org_role": "MEMBER",
            "token_hash": token_hash,
            "status": "pending",
            "expires_at": expires.isoformat().replace("+00:00", "Z"),
        }
        with self.assertRaises(InviteEmailMismatchError):
            self.service.accept_invite(user_id="guest", token=token)


if __name__ == "__main__":
    unittest.main()
