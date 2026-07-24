import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.exception_handlers import register_exception_handlers
from controllers.monthly_fees_controller import create_monthly_fees_router
from services.security.auth_exceptions import InvalidTokenError
from services.security.auth_guard import AuthGuard


class FakeAuthServiceForGuard:
    def validate_access_token(self, *, access_token: str):
        if access_token == "valid-token":
            return {"sub": "user-1", "email": "user@example.com", "google_sub": "g-1"}
        raise InvalidTokenError("invalid_token")


class FakeMonthlyFeesService:
    def list_monthly_fees(
        self,
        *,
        user_id: str,
        team_id: str,
        tag: str | None,
        athlete_id: str | None,
        include_inactive: bool,
    ):
        return {"items": [], "count": 0}

    def create_monthly_fee(
        self,
        *,
        user_id: str,
        team_id: str,
        tag: str,
        amount: float,
        currency: str | None,
        athlete_id: str | None,
        person_name: str | None,
        description: str | None,
    ):
        return {
            "fee_id": "fee-1",
            "org_id": "org-1",
            "team_id": team_id,
            "tag": tag,
            "direction": "CREDIT" if tag == "MONTHLY_CONTRIBUTION" else "DEBIT",
            "amount": amount,
            "currency": currency or "BRL",
            "athlete_id": athlete_id,
            "person_name": person_name,
            "description": description,
            "source": "RECURRING_RULE",
            "is_active": True,
            "created_at": "2026-04-01T00:00:00Z",
            "updated_at": "2026-04-01T00:00:00Z",
        }

    def update_monthly_fee(
        self,
        *,
        user_id: str,
        team_id: str,
        fee_id: str,
        amount: float | None,
        currency: str | None,
        description: str | None,
    ):
        if fee_id == "missing":
            return None
        return {
            "fee_id": fee_id,
            "org_id": "org-1",
            "team_id": team_id,
            "tag": "COURT",
            "direction": "DEBIT",
            "amount": amount if amount is not None else 500.0,
            "currency": currency or "BRL",
            "athlete_id": None,
            "person_name": None,
            "description": description or "Court recurring fee",
            "source": "RECURRING_RULE",
            "is_active": True,
            "created_at": "2026-04-01T00:00:00Z",
            "updated_at": "2026-04-01T00:00:00Z",
        }

    def soft_delete_monthly_fee(self, *, user_id: str, team_id: str, fee_id: str):
        if fee_id == "missing":
            return None
        return {
            "fee_id": fee_id,
            "org_id": "org-1",
            "team_id": team_id,
            "tag": "COURT",
            "direction": "DEBIT",
            "amount": 500.0,
            "currency": "BRL",
            "athlete_id": None,
            "person_name": None,
            "description": "Court recurring fee",
            "source": "RECURRING_RULE",
            "is_active": False,
            "created_at": "2026-04-01T00:00:00Z",
            "updated_at": "2026-04-02T00:00:00Z",
        }


class MonthlyFeesControllerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)
        auth_guard = AuthGuard(auth_service=FakeAuthServiceForGuard())
        app.include_router(create_monthly_fees_router(FakeMonthlyFeesService(), auth_guard))
        self.client = TestClient(app)

    def test_monthly_fees_endpoint_is_protected(self):
        response = self.client.get("/monthly_fees", params={"team_id": "team-1"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")

    def test_list_monthly_fees_success(self):
        response = self.client.get(
            "/monthly_fees",
            params={"team_id": "team-1"},
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_create_monthly_fee_accepts_team_id_from_body(self):
        response = self.client.post(
            "/monthly_fees",
            json={
                "team_id": "team-1",
                "tag": "MONTHLY_CONTRIBUTION",
                "amount": 100.0,
                "athlete_id": "ath-1",
            },
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["team_id"], "team-1")

    def test_create_monthly_fee_rejects_team_id_mismatch(self):
        response = self.client.post(
            "/monthly_fees?team_id=team-query",
            json={
                "team_id": "team-body",
                "tag": "MONTHLY_CONTRIBUTION",
                "amount": 100.0,
                "athlete_id": "ath-1",
            },
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_request")

    def test_update_monthly_fee_not_found(self):
        response = self.client.put(
            "/monthly_fees/missing",
            json={"team_id": "team-1", "amount": 100.0, "currency": "USD"},
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "monthly_fee_not_found")

    def test_soft_delete_monthly_fee_success(self):
        response = self.client.delete(
            "/monthly_fees/fee-1",
            params={"team_id": "team-1"},
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_active"])


if __name__ == "__main__":
    unittest.main()
