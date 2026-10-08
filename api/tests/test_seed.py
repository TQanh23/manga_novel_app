"""Task 0.10: the development accounts, created through the same service as real sign-ups."""

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import repository
from api.auth.models import User
from api.core.config import Settings
from api.scripts.seed import SEED_ACCOUNTS, seed


async def test_seed_creates_one_admin_one_author_and_two_readers(
    db_session: AsyncSession,
) -> None:
    created = await seed(db_session)

    assert created == [account.email for account in SEED_ACCOUNTS]
    roles = {
        user.email: user.role_names for user in (await db_session.execute(select(User))).scalars()
    }
    assert roles == {
        "admin@example.com": ["admin"],
        "author@example.com": ["author", "reader"],
        "reader1@example.com": ["reader"],
        "reader2@example.com": ["reader"],
    }


async def test_seeded_accounts_can_sign_in(
    client: AsyncClient, db_session: AsyncSession, settings: Settings
) -> None:
    await seed(db_session)

    response = await client.post(
        "/v1/auth/login",
        json={
            "email": "author@example.com",
            "password": settings.seed_password.get_secret_value(),
        },
    )

    assert response.status_code == 200
    assert response.json()["user"]["roles"] == ["author", "reader"]


async def test_seed_is_idempotent_and_leaves_existing_accounts_alone(
    db_session: AsyncSession,
) -> None:
    await seed(db_session)
    admin = await repository.get_user_by_email(db_session, "admin@example.com")
    assert admin is not None
    admin.display_name = "Renamed by hand"
    password_hash = admin.password_hash
    await db_session.commit()

    created_again = await seed(db_session)

    assert created_again == []
    assert (await db_session.execute(select(func.count()).select_from(User))).scalar_one() == 4
    admin = await repository.get_user_by_email(db_session, "admin@example.com")
    assert admin is not None
    assert (admin.display_name, admin.password_hash) == ("Renamed by hand", password_hash)


async def test_seed_only_fills_in_what_is_missing(db_session: AsyncSession) -> None:
    await seed(db_session)

    assert await seed(db_session) == []


async def test_seed_refuses_to_run_outside_local(
    db_session: AsyncSession, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "environment", "production")

    with pytest.raises(RuntimeError, match="refusing"):
        await seed(db_session)

    assert (await db_session.execute(select(func.count()).select_from(User))).scalar_one() == 0
