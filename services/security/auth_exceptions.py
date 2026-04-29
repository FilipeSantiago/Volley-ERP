class AuthError(Exception):
    pass


class InvalidRedirectURIError(AuthError):
    pass


class InvalidStateError(AuthError):
    pass


class InvalidCodeVerifierError(AuthError):
    pass


class InvalidCodeError(AuthError):
    pass


class DisallowedPlatformClientMismatchError(AuthError):
    pass


class OAuthProviderError(AuthError):
    def __init__(self, error: str, error_description: str | None = None) -> None:
        self.error = error
        self.error_description = error_description or ""
        super().__init__(self.error_description or self.error)


class InvalidTokenError(AuthError):
    pass


class TokenExpiredError(AuthError):
    pass


class UnauthorizedError(AuthError):
    pass


class CustomerNotFoundError(AuthError):
    pass


class WorkspaceCreationError(AuthError):
    pass


class EncryptionKeyError(AuthError):
    pass


class OAuthConfigurationError(AuthError):
    pass
