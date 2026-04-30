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


class EncryptionKeyError(AuthError):
    pass


class OAuthConfigurationError(AuthError):
    pass


class ForbiddenError(AuthError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class OrganizationNotFoundError(AuthError):
    pass


class TeamNotFoundError(AuthError):
    pass


class InviteNotFoundError(AuthError):
    pass


class InviteExpiredError(AuthError):
    pass


class InviteAlreadyAcceptedError(AuthError):
    pass


class InviteEmailMismatchError(AuthError):
    pass


class StorageOwnerConnectionMissingError(AuthError):
    pass


class WorkspaceProvisioningFailedError(AuthError):
    pass
