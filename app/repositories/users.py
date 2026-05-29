from copy import deepcopy

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.users import User
from app.core.json_types import JsonObject

DEV_USERS: tuple[JsonObject, ...] = (
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
        meta: JsonObject,
    ) -> User:
        statement = insert(User).values(
            account=account,
            refresh_token=refresh_token,
            is_admin=is_admin,
            meta=deepcopy(meta),
        )
        upsert_statement = (
            statement.on_conflict_do_update(
                index_elements=[User.account],
                set_={
                    "refresh_token": statement.excluded.refresh_token,
                    "is_admin": statement.excluded.is_admin,
                    "meta": statement.excluded.meta,
                    "updated_at": func.now(),
                },
            )
            .returning(User)
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(upsert_statement)
        await self._session.flush()
        return result.scalar_one()


async def seed_dev_users(repository: UserRepository) -> None:
    for user in DEV_USERS:
        await repository.upsert_user(**user)
