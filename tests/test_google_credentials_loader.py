import os
import unittest
from unittest.mock import patch

from repositories.helpers.google_drive_folders_helper import (
    GoogleDriveHelperError,
    _load_google_credentials,
)


class GoogleCredentialsLoaderTestCase(unittest.TestCase):
    @patch("repositories.helpers.google_drive_folders_helper._load_adc_credentials")
    def test_adc_mode_prefers_adc_credentials(self, mock_load_adc_credentials):
        adc_credentials = object()
        mock_load_adc_credentials.return_value = adc_credentials

        with patch.dict(
            os.environ,
            {
                "GOOGLE_AUTH_MODE": "adc",
                "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/service-account.json",
            },
            clear=True,
        ):
            credentials = _load_google_credentials(scopes=["scope://drive"])

        self.assertIs(credentials, adc_credentials)
        mock_load_adc_credentials.assert_called_once_with(scopes=["scope://drive"])

    @patch("repositories.helpers.google_drive_folders_helper._load_adc_credentials")
    def test_adc_mode_requires_adc_credentials(self, mock_load_adc_credentials):
        mock_load_adc_credentials.return_value = None

        with patch.dict(os.environ, {"GOOGLE_AUTH_MODE": "adc"}, clear=True):
            with self.assertRaisesRegex(
                GoogleDriveHelperError,
                "Google ADC credentials are not configured",
            ):
                _load_google_credentials(scopes=["scope://drive"])

    @patch("google.oauth2.service_account.Credentials.from_service_account_file")
    @patch("repositories.helpers.google_drive_folders_helper._load_adc_credentials")
    def test_service_account_mode_uses_credentials_file(
        self,
        mock_load_adc_credentials,
        mock_from_service_account_file,
    ):
        service_account_credentials = object()
        mock_from_service_account_file.return_value = service_account_credentials

        with patch.dict(
            os.environ,
            {
                "GOOGLE_AUTH_MODE": "service_account",
                "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/service-account.json",
            },
            clear=True,
        ):
            credentials = _load_google_credentials(scopes=["scope://drive"])

        self.assertIs(credentials, service_account_credentials)
        mock_load_adc_credentials.assert_not_called()
        mock_from_service_account_file.assert_called_once_with(
            "/tmp/service-account.json",
            scopes=["scope://drive"],
        )

    @patch("google.oauth2.service_account.Credentials.from_service_account_info")
    @patch("repositories.helpers.google_drive_folders_helper._load_adc_credentials")
    def test_auto_mode_falls_back_to_service_account_json(
        self,
        mock_load_adc_credentials,
        mock_from_service_account_info,
    ):
        mock_load_adc_credentials.return_value = None
        service_account_credentials = object()
        mock_from_service_account_info.return_value = service_account_credentials

        with patch.dict(
            os.environ,
            {
                "GOOGLE_AUTH_MODE": "auto",
                "GOOGLE_SERVICE_ACCOUNT_JSON": '{"type":"service_account"}',
            },
            clear=True,
        ):
            credentials = _load_google_credentials(scopes=["scope://drive"])

        self.assertIs(credentials, service_account_credentials)
        mock_load_adc_credentials.assert_called_once_with(scopes=["scope://drive"])
        mock_from_service_account_info.assert_called_once_with(
            {"type": "service_account"},
            scopes=["scope://drive"],
        )

    def test_invalid_auth_mode_raises_error(self):
        with patch.dict(os.environ, {"GOOGLE_AUTH_MODE": "invalid"}, clear=True):
            with self.assertRaisesRegex(
                GoogleDriveHelperError,
                "Invalid GOOGLE_AUTH_MODE",
            ):
                _load_google_credentials(scopes=["scope://drive"])


if __name__ == "__main__":
    unittest.main()
