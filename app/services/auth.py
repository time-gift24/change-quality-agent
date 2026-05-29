from app.core.config import Settings
from app.repositories.users import DEV_USERS, UserRepository
from app.schemas.users import UserPublic

DEV_LOGIN_ACCOUNTS = frozenset(user["account"] for user in DEV_USERS)


class AuthRequiredError(PermissionError):
    pass


class DevLoginDisabledError(PermissionError):
    pass


class DevLoginAccountNotFoundError(KeyError):
    pass


class AuthService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: UserRepository | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository

    @property
    def session_cookie_name(self) -> str:
        return self._settings.auth_session_cookie_name

    def current_user_public(self, current_user) -> UserPublic:
        if current_user is None:
            raise AuthRequiredError()
        return user_to_public(current_user)

    async def dev_login(self, account: str) -> UserPublic:
        if not self._settings.auth_dev_mode:
            raise DevLoginDisabledError()
        if account not in DEV_LOGIN_ACCOUNTS:
            raise DevLoginAccountNotFoundError(account)
        if self._repository is None:
            raise DevLoginDisabledError()

        user = await self._repository.get_by_account(account)
        if user is None:
            raise DevLoginAccountNotFoundError(account)

        return user_to_public(user)


def user_to_public(user) -> UserPublic:
    return UserPublic(
        id=user.id,
        account=user.account,
        is_admin=user.is_admin,
        meta=user.meta or {},
    )
