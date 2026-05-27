from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.users import User

DEV_USERS: tuple[dict[str, Any], ...] = (
    {
        "account": "common",
        "refresh_token": "dev-common-refresh-token",
        "is_admin": False,
        "meta": {"source": "dev"},
    },
    {
        "account": "admin",
        "refresh_token": "dev-admin-refresh-token",
        "is_admin": True,
        "meta": {"source": "dev"},
    },
)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_account(self, account: str) -> User | None:
        statement = select(User).where(User.account == account).limit(1)
        return await self._session.scalar(statement)

    async def upsert_user(
        self,
        *,
        account: str,
        refresh_token: str,
        is_admin: bool,
        meta: dict[str, Any],
    ) -> User:
        user = await self.get_by_account(account)
        if user is None:
            user = User(
                account=account,
                refresh_token=refresh_token,
                is_admin=is_admin,
                meta=meta,
            )
            self._session.add(user)
        else:
            user.refresh_token = refresh_token
            user.is_admin = is_admin
            user.meta = meta
        await self._session.flush()
        return user


async def seed_dev_users(repository: UserRepository) -> None:
    for user in DEV_USERS:
        await repository.upsert_user(**user)
