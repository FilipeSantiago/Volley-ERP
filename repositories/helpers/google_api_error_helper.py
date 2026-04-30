import json
from typing import Any


class GoogleAPIErrorHelper:
    @staticmethod
    def http_status(error: Exception) -> int | None:
        resp = getattr(error, "resp", None)
        if resp is None:
            return None
        return getattr(resp, "status", None)

    @staticmethod
    def map_drive_error(*, error: Exception, fallback_message: str) -> str:
        status = GoogleAPIErrorHelper.http_status(error)
        provider_message = GoogleAPIErrorHelper._extract_provider_message(error)

        if status == 401:
            return "Google credentials are invalid or expired. Reconnect your Google account."
        if status == 403:
            lower_message = provider_message.lower()
            if "api has not been used" in lower_message or "api is disabled" in lower_message:
                return "Google Drive API is not enabled for this project."
            return "Google Drive permission denied for this account or OAuth scope."

        if provider_message:
            return provider_message
        return fallback_message

    @staticmethod
    def _extract_provider_message(error: Exception) -> str:
        raw_content = getattr(error, "content", b"")
        content: dict[str, Any] = {}
        if isinstance(raw_content, bytes):
            try:
                content = json.loads(raw_content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                content = {}

        nested_error = content.get("error")
        if isinstance(nested_error, dict):
            raw_message = nested_error.get("message")
            if isinstance(raw_message, str):
                return raw_message
        return ""
