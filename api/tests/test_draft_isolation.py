"""NFR-06: an author's drafts are invisible to every other author.

The guarantee is in the database, not in the queries: these tests run raw SQL
as app_rw, the role the API connects as, and never go through a service.
"""

from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.auth import service as auth_service
from api.auth.models import Role, User
from api.catalogue.models import Episode, EpisodeVersion, Work
from api.core.db import set_author_context
from api.core.ids import uuid7
from api.testing import TEST_PASSWORD, MakeUser, MakeWork

ALL_VERSIONS = "SELECT id FROM core.episode_versions"
INSERT_VERSION = (
    "INSERT INTO core.episode_versions (id, episode_id, author_id, body_html)"
    " VALUES (:id, :episode_id, :author_id, 'x')"
)


@dataclass
class Drafts:
    author: User
    other_author: User
    episode: Episode
    versions: list[UUID]


async def visible_versions(session: AsyncSession) -> set[UUID]:
    return set((await session.execute(text(ALL_VERSIONS))).scalars())


async def clear_author_context(session: AsyncSession) -> None:
    # What the setting reads as once the transaction that set it has ended.
    await session.execute(text("SELECT set_config('app.author_id', '', true)"))


@pytest.fixture
async def drafts(db_session: AsyncSession, make_user: MakeUser, make_work: MakeWork) -> Drafts:
    """An episode with three saved versions, none published."""
    author = await make_user(Role.AUTHOR)
    other_author = await make_user(Role.AUTHOR)
    work = await make_work(author)
    episode = Episode(work_id=work.id, author_id=author.id, number=1, title="One")
    db_session.add(episode)
    await db_session.flush()

    await set_author_context(db_session, author.id)
    versions = [
        EpisodeVersion(
            episode_id=episode.id, author_id=author.id, body_html=body, created_by=author.id
        )
        for body in ("첫 번째 초안", "第二稿", "Bản nháp thứ ba")
    ]
    db_session.add_all(versions)
    await db_session.flush()
    return Drafts(author, other_author, episode, [version.id for version in versions])


async def test_nfr_06_an_author_sees_their_own_drafts(
    db_session: AsyncSession, drafts: Drafts
) -> None:
    assert await visible_versions(db_session) == set(drafts.versions)


async def test_nfr_06_another_author_sees_none_of_them_even_with_raw_sql(
    db_session: AsyncSession, drafts: Drafts
) -> None:
    await set_author_context(db_session, drafts.other_author.id)

    assert await visible_versions(db_session) == set()


async def test_nfr_06_a_transaction_that_names_no_author_sees_no_drafts(
    db_session: AsyncSession, drafts: Drafts
) -> None:
    await clear_author_context(db_session)

    assert await visible_versions(db_session) == set()


async def test_nfr_06_an_author_cannot_save_a_version_in_another_authors_name(
    db_session: AsyncSession, drafts: Drafts
) -> None:
    await set_author_context(db_session, drafts.other_author.id)

    with pytest.raises(ProgrammingError, match="row-level security"):
        await db_session.execute(
            text(INSERT_VERSION),
            {"id": uuid7(), "episode_id": drafts.episode.id, "author_id": drafts.author.id},
        )


async def test_nfr_06_an_author_cannot_save_a_version_into_another_authors_episode(
    db_session: AsyncSession, drafts: Drafts
) -> None:
    await set_author_context(db_session, drafts.other_author.id)

    with pytest.raises(IntegrityError, match="fk_episode_versions_episode_id_episodes"):
        await db_session.execute(
            text(INSERT_VERSION),
            {"id": uuid7(), "episode_id": drafts.episode.id, "author_id": drafts.other_author.id},
        )


async def test_nfr_06_no_version_can_be_saved_without_naming_an_author(
    db_session: AsyncSession, drafts: Drafts
) -> None:
    await clear_author_context(db_session)

    with pytest.raises(ProgrammingError, match="row-level security"):
        await db_session.execute(
            text(INSERT_VERSION),
            {"id": uuid7(), "episode_id": drafts.episode.id, "author_id": drafts.author.id},
        )


async def test_nfr_06_publishing_shows_everyone_that_version_and_no_other(
    db_session: AsyncSession, drafts: Drafts
) -> None:
    older, published, newer = drafts.versions
    await db_session.execute(
        text(
            "UPDATE core.episodes SET status = 'published', publish_at = now(),"
            " published_version_id = :version_id WHERE id = :id"
        ),
        {"version_id": published, "id": drafts.episode.id},
    )

    await set_author_context(db_session, drafts.other_author.id)
    assert await visible_versions(db_session) == {published}

    await clear_author_context(db_session)
    assert await visible_versions(db_session) == {published}

    await set_author_context(db_session, drafts.author.id)
    assert await visible_versions(db_session) == {older, published, newer}


async def test_nfr_06_a_removed_episode_stops_showing_its_published_version(
    db_session: AsyncSession, drafts: Drafts
) -> None:
    await db_session.execute(
        text(
            "UPDATE core.episodes SET status = 'published', publish_at = now(),"
            " published_version_id = :version_id WHERE id = :id"
        ),
        {"version_id": drafts.versions[0], "id": drafts.episode.id},
    )
    await db_session.execute(
        text("UPDATE core.episodes SET status = 'removed' WHERE id = :id"),
        {"id": drafts.episode.id},
    )
    await clear_author_context(db_session)

    assert await visible_versions(db_session) == set()


async def test_nfr_06_row_level_security_is_forced_on_episode_versions(
    db_session: AsyncSession,
) -> None:
    # Without FORCE the policies would not bind the table's owner.
    row = (
        await db_session.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class"
                " WHERE oid = 'core.episode_versions'::regclass"
            )
        )
    ).one()

    assert row.relrowsecurity
    assert row.relforcerowsecurity


async def test_nfr_06_the_author_context_ends_with_its_transaction(
    committed_sessions: async_sessionmaker[AsyncSession],
) -> None:
    # Real commits on pooled connections: the next transaction, on whichever
    # connection it gets, must not inherit the previous one's author.
    async with committed_sessions() as session:
        author = await auth_service.register(
            session,
            email="author@example.com",
            password=TEST_PASSWORD,
            display_name="Author",
            roles=(Role.AUTHOR,),
        )
        work = Work(author_id=author.id, type="novel", title="Private", language="vi")
        session.add(work)
        await session.flush()
        episode = Episode(work_id=work.id, author_id=author.id, number=1, title="One")
        session.add(episode)
        await session.flush()
        await set_author_context(session, author.id)
        session.add(
            EpisodeVersion(episode_id=episode.id, author_id=author.id, body_html="Bản nháp")
        )
        await session.commit()

    for _ in range(3):
        async with committed_sessions() as session:
            assert await visible_versions(session) == set()

    async with committed_sessions() as session:
        await set_author_context(session, author.id)
        assert len(await visible_versions(session)) == 1
