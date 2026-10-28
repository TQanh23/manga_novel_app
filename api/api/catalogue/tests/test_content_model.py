"""Task 1.1: what the content tables default to, accept and refuse."""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from api.auth.models import Role
from api.catalogue.models import Episode, GlossaryEntry, GlossaryKind, Tag, WorkTag
from api.core.ids import uuid7
from api.reader.models import ReadingProgress
from api.testing import MakeUser, MakeWork


async def test_a_work_is_neither_a_sample_nor_opted_in_to_training_unless_someone_says_so(
    db_session: AsyncSession, make_user: MakeUser
) -> None:
    author = await make_user(Role.AUTHOR)

    # Raw SQL: the database's own defaults, not the model's.
    row = (
        await db_session.execute(
            text(
                "INSERT INTO core.works (id, author_id, type, title, language)"
                " VALUES (:id, :author_id, 'novel', 'Untitled', 'vi')"
                " RETURNING is_sample, ai_opt_in_training, status, synopsis"
            ),
            {"id": uuid7(), "author_id": author.id},
        )
    ).one()

    assert row.is_sample is False
    assert row.ai_opt_in_training is False
    assert (row.status, row.synopsis) == ("ongoing", "")


@pytest.mark.parametrize(
    ("field", "value", "constraint"),
    [
        ("type", "comic", "ck_works_type"),
        ("language", "fr", "ck_works_language"),
        ("status", "paused", "ck_works_status"),
    ],
)
async def test_a_work_refuses_values_outside_its_lists(
    make_user: MakeUser, make_work: MakeWork, field: str, value: str, constraint: str
) -> None:
    author = await make_user(Role.AUTHOR)

    with pytest.raises(IntegrityError, match=constraint):
        await make_work(author, **{field: value})


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        ({"status": "hidden"}, "ck_episodes_status"),
        ({"number": 0}, "ck_episodes_number_positive"),
        ({"price_coins": -1}, "ck_episodes_price_coins_not_negative"),
        ({"status": "scheduled"}, "ck_episodes_publish_at_set"),
        ({"status": "published"}, "ck_episodes_publish_at_set"),
    ],
)
async def test_an_episode_refuses_values_that_make_no_sense(
    db_session: AsyncSession,
    make_user: MakeUser,
    make_work: MakeWork,
    fields: dict[str, Any],
    constraint: str,
) -> None:
    author = await make_user(Role.AUTHOR)
    work = await make_work(author)
    episode = {"work_id": work.id, "author_id": author.id, "number": 1, "title": "One", **fields}
    db_session.add(Episode(**episode))

    with pytest.raises(IntegrityError, match=constraint):
        await db_session.flush()


async def test_a_new_episode_is_a_free_draft_and_can_be_scheduled(
    db_session: AsyncSession, make_user: MakeUser, make_work: MakeWork
) -> None:
    author = await make_user(Role.AUTHOR)
    work = await make_work(author)
    episode = Episode(work_id=work.id, author_id=author.id, number=1, title="One")
    db_session.add(episode)
    await db_session.flush()
    await db_session.refresh(episode)

    assert (episode.status, episode.price_coins, episode.wuf_eligible) == ("draft", 0, False)
    assert episode.publish_at is None
    assert episode.published_version_id is None

    episode.status = "scheduled"
    episode.publish_at = datetime(2030, 1, 1, tzinfo=UTC)
    await db_session.flush()


async def test_episode_numbers_are_unique_within_a_work(
    db_session: AsyncSession, make_user: MakeUser, make_work: MakeWork
) -> None:
    author = await make_user(Role.AUTHOR)
    work = await make_work(author)
    other_work = await make_work(author)
    db_session.add_all(
        [
            Episode(work_id=work.id, author_id=author.id, number=1, title="One"),
            Episode(work_id=other_work.id, author_id=author.id, number=1, title="One"),
        ]
    )
    await db_session.flush()

    db_session.add(Episode(work_id=work.id, author_id=author.id, number=1, title="Again"))

    with pytest.raises(IntegrityError, match="uq_episodes_work_id_number"):
        await db_session.flush()


async def test_an_episode_cannot_name_an_author_other_than_its_works(
    db_session: AsyncSession, make_user: MakeUser, make_work: MakeWork
) -> None:
    author = await make_user(Role.AUTHOR)
    someone_else = await make_user(Role.AUTHOR)
    work = await make_work(author)
    db_session.add(Episode(work_id=work.id, author_id=someone_else.id, number=1, title="One"))

    with pytest.raises(IntegrityError, match="fk_episodes_work_id_works"):
        await db_session.flush()


async def test_fr_nv_03_a_glossary_entry_keeps_korean_japanese_and_vietnamese_as_written(
    db_session: AsyncSession, make_user: MakeUser, make_work: MakeWork
) -> None:
    author = await make_user(Role.AUTHOR)
    work = await make_work(author, language="ko")
    aliases = ["하늘", "ハヌル", "Hạ Nựu"]
    attributes = {"눈 색": "갈색", "tuổi": 17, "関係": {"姉": "김바다"}}
    translations = {"ja": "キム・ハヌル", "vi": "Kim Hạ Nựu", "en": "Kim Ha-neul"}
    entry = GlossaryEntry(
        work_id=work.id,
        kind=GlossaryKind.CHARACTER,
        name="김하늘",
        aliases=aliases,
        attributes=attributes,
        translations=translations,
    )
    db_session.add(entry)
    await db_session.flush()
    entry_id = entry.id
    db_session.expire(entry)

    stored = (
        await db_session.execute(select(GlossaryEntry).where(GlossaryEntry.id == entry_id))
    ).scalar_one()

    assert stored.name == "김하늘"
    assert stored.aliases == aliases
    assert stored.attributes == attributes
    assert stored.translations == translations


async def test_fr_nv_03_a_glossary_entry_starts_with_no_aliases_or_attributes(
    db_session: AsyncSession, make_user: MakeUser, make_work: MakeWork
) -> None:
    work = await make_work(await make_user(Role.AUTHOR))

    row = (
        await db_session.execute(
            text(
                "INSERT INTO core.glossary_entries (id, work_id, kind, name)"
                " VALUES (:id, :work_id, 'place', '서울')"
                " RETURNING aliases, attributes, translations"
            ),
            {"id": uuid7(), "work_id": work.id},
        )
    ).one()

    assert (row.aliases, row.attributes, row.translations) == ([], {}, {})


async def test_fr_nv_03_a_work_lists_a_name_once_per_kind(
    db_session: AsyncSession, make_user: MakeUser, make_work: MakeWork
) -> None:
    work = await make_work(await make_user(Role.AUTHOR))
    db_session.add_all(
        [
            GlossaryEntry(work_id=work.id, kind="character", name="Hà Nội"),
            GlossaryEntry(work_id=work.id, kind="place", name="Hà Nội"),
        ]
    )
    await db_session.flush()

    db_session.add(GlossaryEntry(work_id=work.id, kind="place", name="Hà Nội"))

    with pytest.raises(IntegrityError, match="uq_glossary_entries_work_id_kind_name"):
        await db_session.flush()


async def test_a_glossary_entry_refuses_an_unknown_kind(
    db_session: AsyncSession, make_user: MakeUser, make_work: MakeWork
) -> None:
    work = await make_work(await make_user(Role.AUTHOR))
    db_session.add(GlossaryEntry(work_id=work.id, kind="item", name="Sword"))

    with pytest.raises(IntegrityError, match="ck_glossary_entries_kind"):
        await db_session.flush()


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        ({"slug": "isekai", "kind": "category"}, "ck_tags_kind"),
        ({"slug": "Isekai"}, "ck_tags_slug_lowercase"),
    ],
)
async def test_a_tag_refuses_an_unknown_kind_and_a_slug_that_is_not_lowercase(
    db_session: AsyncSession, fields: dict[str, str], constraint: str
) -> None:
    db_session.add(Tag(name="Isekai", **fields))

    with pytest.raises(IntegrityError, match=constraint):
        await db_session.flush()


async def test_a_work_carries_a_genre_and_a_free_tag_once_each(
    db_session: AsyncSession, make_user: MakeUser, make_work: MakeWork
) -> None:
    work = await make_work(await make_user(Role.AUTHOR))
    genre = Tag(slug="isekai", name="Isekai", kind="genre")
    free = Tag(slug="회귀", name="회귀")
    db_session.add_all([genre, free])
    await db_session.flush()
    db_session.add_all(
        [WorkTag(work_id=work.id, tag_id=genre.id), WorkTag(work_id=work.id, tag_id=free.id)]
    )
    await db_session.flush()
    await db_session.refresh(free)

    assert free.kind == "tag"

    db_session.add(WorkTag(work_id=work.id, tag_id=genre.id, source="ai_suggested_approved"))

    with pytest.raises(IntegrityError, match="uq_work_tags_work_id_tag_id"):
        await db_session.flush()


async def test_a_work_tag_refuses_an_unknown_source(
    db_session: AsyncSession, make_user: MakeUser, make_work: MakeWork
) -> None:
    work = await make_work(await make_user(Role.AUTHOR))
    tag = Tag(slug="western", name="Western", kind="genre")
    db_session.add(tag)
    await db_session.flush()
    db_session.add(WorkTag(work_id=work.id, tag_id=tag.id, source="ai"))

    with pytest.raises(IntegrityError, match="ck_work_tags_source"):
        await db_session.flush()


async def test_fr_rd_05_a_reader_has_one_position_per_episode(
    db_session: AsyncSession, make_user: MakeUser, make_work: MakeWork
) -> None:
    author = await make_user(Role.AUTHOR)
    reader = await make_user()
    work = await make_work(author)
    episode = Episode(work_id=work.id, author_id=author.id, number=1, title="One")
    db_session.add(episode)
    await db_session.flush()
    db_session.add(ReadingProgress(user_id=reader.id, episode_id=episode.id, position=12))
    await db_session.flush()

    db_session.add(ReadingProgress(user_id=reader.id, episode_id=episode.id, position=40))

    with pytest.raises(IntegrityError, match="uq_reading_progress_user_id_episode_id"):
        await db_session.flush()


async def test_fr_rd_05_a_position_is_never_negative(
    db_session: AsyncSession, make_user: MakeUser, make_work: MakeWork
) -> None:
    author = await make_user(Role.AUTHOR)
    work = await make_work(author)
    episode = Episode(work_id=work.id, author_id=author.id, number=1, title="One")
    db_session.add(episode)
    await db_session.flush()
    db_session.add(ReadingProgress(user_id=author.id, episode_id=episode.id, position=-1))

    with pytest.raises(IntegrityError, match="ck_reading_progress_position_not_negative"):
        await db_session.flush()


async def test_fr_ad_04_the_wuf_periods_and_revenue_splits_come_with_the_schema(
    db_session: AsyncSession,
) -> None:
    rows = await db_session.execute(
        text("SELECT kind, value FROM core.config_presets WHERE active ORDER BY kind, value")
    )

    assert [tuple(row) for row in rows] == [
        ("revenue_share", 50),
        ("revenue_share", 60),
        ("revenue_share", 70),
        ("wuf_period", 3 * 3600),
        ("wuf_period", 12 * 3600),
        ("wuf_period", 24 * 3600),
        ("wuf_period", 72 * 3600),
    ]


@pytest.mark.parametrize(
    ("kind", "value", "constraint"),
    [
        ("coin_price", 100, "ck_config_presets_kind"),
        ("wuf_period", 0, "ck_config_presets_value_positive"),
        ("revenue_share", 101, "ck_config_presets_revenue_share_percent"),
        ("revenue_share", 50, "uq_config_presets_kind_value"),
    ],
)
async def test_fr_ad_04_a_preset_refuses_values_that_make_no_sense(
    owner_connection: AsyncConnection, kind: str, value: int, constraint: str
) -> None:
    with pytest.raises(IntegrityError, match=constraint):
        await owner_connection.execute(
            text("INSERT INTO core.config_presets (id, kind, value) VALUES (:id, :kind, :value)"),
            {"id": uuid7(), "kind": kind, "value": value},
        )


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO core.config_presets (id, kind, value)"
        " VALUES (gen_random_uuid(), 'wuf_period', 60)",
        "UPDATE core.config_presets SET active = false",
        "DELETE FROM core.config_presets",
        "DELETE FROM core.works",
        "DELETE FROM core.episodes",
        "DELETE FROM core.episode_versions",
        "UPDATE core.episode_versions SET body_html = ''",
    ],
)
async def test_the_api_role_cannot_change_presets_delete_works_or_rewrite_a_saved_version(
    db_session: AsyncSession, statement: str
) -> None:
    with pytest.raises(ProgrammingError, match="permission denied"):
        await db_session.execute(text(statement))
