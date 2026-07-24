import unittest

from services.monthly_fees_service import MonthlyFeesService
from services.security.auth_config import AuthConfig


class FakeOrganizationRepository:
    def __init__(self) -> None:
        self.user_orgs = {
            "user-1": [
                {
                    "org_id": "org-1",
                    "org_role": "ADMIN",
                    "status": "active",
                }
            ]
        }
        self.orgs = {
            "org-1": {
                "org_id": "org-1",
                "name": "Org One",
                "storage_owner_user_id": "storage-owner-1",
            }
        }
        self.teams = {
            ("org-1", "team-1"): {
                "team_id": "team-1",
                "status": "active",
                "team_spreadsheet_id": "sheet-1",
            }
        }

    def list_user_organizations(self, *, user_id: str):
        return list(self.user_orgs.get(user_id, []))

    def get_team(self, *, org_id: str, team_id: str):
        team = self.teams.get((org_id, team_id))
        return dict(team) if team else None

    def get_organization(self, *, org_id: str):
        org = self.orgs.get(org_id)
        return dict(org) if org else None


class FakeGoogleConnectionRepository:
    def get_by_user_id(self, *, user_id: str):
        if user_id != "storage-owner-1":
            return None
        return {"encrypted_refresh_token": "enc-token"}


class FakeRefreshTokenEncryptionService:
    def decrypt(self, encrypted_refresh_token: str) -> str:
        if encrypted_refresh_token != "enc-token":
            raise ValueError("Unexpected token")
        return "refresh-token"


class FakeAuthorizationService:
    def require_team_permission(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
        permission: str,
    ):
        return {"team_role": "TEAM_ADMIN", "status": "active"}


class InMemoryMonthlyFeesRepository:
    def __init__(self) -> None:
        self.entries: list[dict] = [
            {
                "entry_id": "legacy-generated-1",
                "org_id": "org-1",
                "team_id": "team-1",
                "year": 2026,
                "month": 4,
                "entry_date": "2026-04-01",
                "tag": "COURT",
                "direction": "DEBIT",
                "amount": 500.0,
                "currency": "BRL",
                "athlete_id": None,
                "person_id": None,
                "person_name": None,
                "description": "Generated legacy monthly fee",
                "source": "GENERATED",
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-01T00:00:00Z",
            }
        ]

    def list_monthly_fee_entries(
        self,
        *,
        spreadsheet_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ):
        return [dict(item) for item in self.entries]

    def append_monthly_fee_entries(
        self,
        *,
        spreadsheet_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        entries: list[dict],
    ):
        self.entries.extend(dict(item) for item in entries)
        return entries

    def update_monthly_fee_entry(
        self,
        *,
        spreadsheet_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        entry_id: str,
        expected_team_id: str | None,
        expected_source: str | None,
        amount: float | None,
        currency: str | None,
        description: str | None,
        is_active: bool | None,
        updated_at: str,
    ):
        for item in self.entries:
            if item.get("entry_id") != entry_id:
                continue
            if expected_team_id is not None and item.get("team_id") != expected_team_id:
                continue
            if expected_source is not None and str(item.get("source") or "").upper() != expected_source:
                continue
            if amount is not None:
                item["amount"] = amount
            if currency is not None:
                item["currency"] = currency
            if description is not None:
                item["description"] = description
            if is_active is not None:
                item["is_active"] = is_active
            item["updated_at"] = updated_at
            return dict(item)
        return None


def _build_auth_config() -> AuthConfig:
    return AuthConfig(
        google_oauth_client_id="client-id",
        google_oauth_client_secret="client-secret",
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


class MonthlyFeesServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryMonthlyFeesRepository()
        self.service = MonthlyFeesService(
            auth_config=_build_auth_config(),
            organization_repository=FakeOrganizationRepository(),
            google_connection_repository=FakeGoogleConnectionRepository(),
            refresh_token_encryption_service=FakeRefreshTokenEncryptionService(),
            authorization_service=FakeAuthorizationService(),
            monthly_fees_repository=self.repository,
        )

    def test_create_monthly_fee_is_idempotent_for_active_rule(self):
        created = self.service.create_monthly_fee(
            user_id="user-1",
            team_id="team-1",
            tag="MONTHLY_CONTRIBUTION",
            amount=80.0,
            currency="BRL",
            athlete_id="athlete-1",
            person_name=None,
            description="Recurring contribution",
        )
        self.assertIsNotNone(created["fee_id"])
        with self.assertRaises(ValueError):
            self.service.create_monthly_fee(
                user_id="user-1",
                team_id="team-1",
                tag="MONTHLY_CONTRIBUTION",
                amount=80.0,
                currency="BRL",
                athlete_id="athlete-1",
                person_name=None,
                description="Recurring contribution duplicate",
            )

    def test_soft_deleted_rule_can_be_created_again(self):
        created = self.service.create_monthly_fee(
            user_id="user-1",
            team_id="team-1",
            tag="COURT",
            amount=500.0,
            currency="BRL",
            athlete_id=None,
            person_name=None,
            description="Court recurring fee",
        )
        deleted = self.service.soft_delete_monthly_fee(
            user_id="user-1",
            team_id="team-1",
            fee_id=created["fee_id"],
        )
        self.assertIsNotNone(deleted)
        self.assertFalse(deleted["is_active"])
        recreated = self.service.create_monthly_fee(
            user_id="user-1",
            team_id="team-1",
            tag="COURT",
            amount=500.0,
            currency="BRL",
            athlete_id=None,
            person_name=None,
            description="Court recurring fee",
        )
        self.assertTrue(recreated["is_active"])

    def test_list_monthly_fees_excludes_inactive_by_default(self):
        created = self.service.create_monthly_fee(
            user_id="user-1",
            team_id="team-1",
            tag="COURT",
            amount=500.0,
            currency="BRL",
            athlete_id=None,
            person_name=None,
            description="Court recurring fee",
        )
        self.service.soft_delete_monthly_fee(
            user_id="user-1",
            team_id="team-1",
            fee_id=created["fee_id"],
        )

        active_only = self.service.list_monthly_fees(
            user_id="user-1",
            team_id="team-1",
            tag=None,
            athlete_id=None,
            include_inactive=False,
        )
        self.assertEqual(active_only["count"], 0)

        with_inactive = self.service.list_monthly_fees(
            user_id="user-1",
            team_id="team-1",
            tag=None,
            athlete_id=None,
            include_inactive=True,
        )
        self.assertEqual(with_inactive["count"], 1)
        self.assertFalse(with_inactive["items"][0]["is_active"])

    def test_update_monthly_fee_entry(self):
        created = self.service.create_monthly_fee(
            user_id="user-1",
            team_id="team-1",
            tag="COACH",
            amount=200.0,
            currency="BRL",
            athlete_id=None,
            person_name="Coach One",
            description="Coach recurring fee",
        )
        updated = self.service.update_monthly_fee(
            user_id="user-1",
            team_id="team-1",
            fee_id=created["fee_id"],
            amount=220.0,
            currency="USD",
            description="Adjusted",
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["amount"], 220.0)
        self.assertEqual(updated["currency"], "USD")
        self.assertEqual(updated["description"], "Adjusted")

    def test_create_monthly_fee_requires_target_for_contribution(self):
        with self.assertRaises(ValueError):
            self.service.create_monthly_fee(
                user_id="user-1",
                team_id="team-1",
                tag="MONTHLY_CONTRIBUTION",
                amount=80.0,
                currency="BRL",
                athlete_id=None,
                person_name=None,
                description=None,
            )

    def test_create_monthly_fee_allows_person_name_for_contribution(self):
        created = self.service.create_monthly_fee(
            user_id="user-1",
            team_id="team-1",
            tag="MONTHLY_CONTRIBUTION",
            amount=80.0,
            currency="BRL",
            athlete_id="athlete-1",
            person_name="Athlete One",
            description=None,
        )
        self.assertEqual(created["person_name"], "Athlete One")

    def test_create_monthly_fee_allows_coach_without_person_name(self):
        created = self.service.create_monthly_fee(
            user_id="user-1",
            team_id="team-1",
            tag="COACH",
            amount=120.0,
            currency="BRL",
            athlete_id=None,
            person_name=None,
            description=None,
        )
        self.assertEqual(created["tag"], "COACH")

    def test_create_monthly_fee_requires_person_name_for_commission(self):
        with self.assertRaises(ValueError):
            self.service.create_monthly_fee(
                user_id="user-1",
                team_id="team-1",
                tag="COMMISSION",
                amount=120.0,
                currency="BRL",
                athlete_id=None,
                person_name=None,
                description=None,
            )


if __name__ == "__main__":
    unittest.main()
