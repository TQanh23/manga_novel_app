"""Deleting a work leaves nothing of it in Postgres.

The start of the hard-delete test: the delete endpoint arrives with the AI
core, and adds object storage and the AI tables to this. A table that
references a work or an episode belongs in WORK_OWNED_TABLES and in the work
built below.
"""

from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from api.auth.models import User
from api.catalogue.models import Episode, EpisodeVersion, GlossaryEntry, Tag, Work, WorkTag
from api.reader.models import Favourite, ReadingProgress

WORK_OWNED_TABLES = [
    "core.episode_versions",
    "core.episodes",
    "core.favourites",
    "core.glossary_entries",
    "core.reading_progress",
    "core.work_tags",
]


async def count(connection: AsyncConnection, table: str) -> int:
    rows = await connection.execute(text(f"SELECT count(*) FROM {table}"))  # noqa: S608
    return int(rows.scalar_one())


async def test_every_table_that_references_a_work_or_an_episode_cascades_on_delete(
    db_session: AsyncSession,
) -> None:
    rows = (
        await db_session.execute(
            text(
                "SELECT conrelid::regclass::text AS referencing, conname, confdeltype::text"
                " FROM pg_constraint WHERE contype = 'f'"
                " AND confrelid IN ('core.works'::regclass, 'core.episodes'::regclass)"
            )
        )
    ).all()

    assert [row.conname for row in rows if row.confdeltype != "c"] == []
    assert sorted({row.referencing for row in rows}) == WORK_OWNED_TABLES


async def test_deleting_a_work_removes_everything_that_belonged_to_it(
    owner_connection: AsyncConnection,
) -> None:
    async with AsyncSession(bind=owner_connection, expire_on_commit=False) as session:
        author = User(email="author@example.com", password_hash="x", display_name="Author")
        reader = User(email="reader@example.com", password_hash="x", display_name="Reader")
        tag = Tag(slug="noir", name="Noir", kind="genre")
        session.add_all([author, reader, tag])
        await session.flush()
        work = Work(author_id=author.id, type="novel", title="Doomed", language="en")
        session.add(work)
        await session.flush()
        episodes = [
            Episode(work_id=work.id, author_id=author.id, number=number, title=f"Episode {number}")
            for number in (1, 2)
        ]
        session.add_all(episodes)
        await session.flush()
        versions = [
            EpisodeVersion(episode_id=episode.id, author_id=author.id, body_md="Text")
            for episode in episodes
            for _ in range(2)
        ]
        session.add_all(versions)
        session.add_all(
            [
                GlossaryEntry(work_id=work.id, kind="character", name="Mira"),
                WorkTag(work_id=work.id, tag_id=tag.id),
                ReadingProgress(user_id=reader.id, episode_id=episodes[0].id, position=3),
                Favourite(user_id=reader.id, work_id=work.id),
            ]
        )
        await session.flush()
        # A published version is the one row that points back at its episode.
        episodes[0].status = "published"
        episodes[0].publish_at = datetime.now(UTC)
        episodes[0].published_version_id = versions[0].id
        await session.flush()

        for table in WORK_OWNED_TABLES:
            assert await count(owner_connection, table) > 0, table

        await owner_connection.execute(
            text("DELETE FROM core.works WHERE id = :id"), {"id": work.id}
        )

        for table in WORK_OWNED_TABLES:
            assert await count(owner_connection, table) == 0, table
        # What was never the work's stays: its tag, next to the fixed genres.
        tags_left = await owner_connection.execute(
            text("SELECT count(*) FROM core.tags WHERE slug = 'noir'")
        )
        assert tags_left.scalar_one() == 1
        remaining = (await owner_connection.execute(select(User.email))).scalars()
        assert sorted(remaining) == ["author@example.com", "reader@example.com"]
