"""Create the development data: four accounts and a sample novel.

    uv run python -m api.scripts.seed

Runs on `docker compose up`. Safe to run again: an account or a sample novel
that already exists is left exactly as it is. The accounts share a password
that is in the repository, so this refuses to run anywhere but a local
environment.

The novel's text and glossary live in infra/seed/sample_novel. It is published
through the same services an author's requests go through, so its versions,
its published pointers and its glossary are what the API would have produced.
"""

import asyncio
import tomllib
from dataclasses import dataclass
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import repository, service
from api.auth.models import Locale, Role
from api.author import repository as author_repository
from api.author import service as author_service
from api.author.schemas import GlossaryEntryCreate, WorkCreate
from api.catalogue.models import WorkType
from api.core.config import get_settings
from api.core.db import get_engine, get_sessionmaker
from api.core.logging import configure_logging

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SeedAccount:
    email: str
    display_name: str
    roles: tuple[Role, ...]
    locale: Locale = Locale.EN


SEED_ACCOUNTS = (
    SeedAccount("admin@example.com", "Admin", (Role.ADMIN,)),
    SeedAccount("author@example.com", "Nguyễn Tác Giả", (Role.READER, Role.AUTHOR), Locale.VI),
    SeedAccount("reader1@example.com", "Reader One", (Role.READER,)),
    SeedAccount("reader2@example.com", "Độc Giả Hai", (Role.READER,), Locale.VI),
)

SAMPLE_NOVEL_AUTHOR = "author@example.com"
SAMPLE_NOVEL_DIRECTORY = "sample_novel"


@dataclass(frozen=True)
class SampleEpisode:
    title: str
    body_html: str


@dataclass(frozen=True)
class SampleNovel:
    work: WorkCreate
    episodes: tuple[SampleEpisode, ...]
    glossary: tuple[GlossaryEntryCreate, ...]


def _require_local() -> None:
    if get_settings().environment != "local":
        raise RuntimeError("Seed data has a public password; refusing to create it here.")


def load_sample_novel(directory: Path) -> SampleNovel:
    """Read the sample novel from disk, holding it to the limits the API enforces."""
    with (directory / "novel.toml").open("rb") as file:
        data = tomllib.load(file)
    return SampleNovel(
        work=WorkCreate(
            type=WorkType.NOVEL,
            title=data["title"],
            synopsis=data["synopsis"],
            language=data["language"],
            genres=data["genres"],
            tags=data["tags"],
        ),
        episodes=tuple(
            SampleEpisode(title, (directory / f"{number:02d}.html").read_text(encoding="utf-8"))
            for number, title in enumerate(data["episodes"], start=1)
        ),
        glossary=tuple(GlossaryEntryCreate.model_validate(entry) for entry in data["glossary"]),
    )


async def seed(session: AsyncSession) -> list[str]:
    """Create the accounts that are missing. Returns the emails it created."""
    _require_local()
    settings = get_settings()

    created = []
    for account in SEED_ACCOUNTS:
        if await repository.get_user_by_email(session, account.email) is not None:
            continue
        await service.register(
            session,
            email=account.email,
            password=settings.seed_password.get_secret_value(),
            display_name=account.display_name,
            locale=account.locale,
            roles=account.roles,
        )
        created.append(account.email)
    return created


async def seed_sample_novel(session: AsyncSession) -> bool:
    """Publish the sample novel for the seeded author. Returns whether it was created.

    The work is marked is_sample: it was written for this project, so it may
    go to AI providers that a real author's manuscript never reaches. Nothing
    but this script sets that flag.
    """
    _require_local()
    author = await repository.get_user_by_email(session, SAMPLE_NOVEL_AUTHOR)
    if author is None:
        raise RuntimeError("Seed the accounts before the sample novel.")

    novel = load_sample_novel(get_settings().seed_dir / SAMPLE_NOVEL_DIRECTORY)
    if await author_repository.find_sample_work(session, author.id, novel.work.title) is not None:
        return False

    state = await author_service.create_work(
        session,
        author=author,
        type=novel.work.type,
        title=novel.work.title,
        synopsis=novel.work.synopsis,
        language=novel.work.language,
        wuf_preset_id=None,
        genres=novel.work.genres,
        tags=novel.work.tags,
        is_sample=True,
    )
    for entry in novel.glossary:
        await author_service.create_glossary_entry(
            session,
            author=author,
            work_id=state.work.id,
            kind=entry.kind,
            name=entry.name,
            aliases=entry.aliases,
            attributes=entry.attributes,
            translations={str(code): text for code, text in entry.translations.items()},
        )
    for episode in novel.episodes:
        created = await author_service.create_episode(
            session, author=author, work_id=state.work.id, title=episode.title
        )
        await author_service.save_draft(
            session, author=author, episode_id=created.episode.id, body_html=episode.body_html
        )
        await author_service.publish_episode(session, author=author, episode_id=created.episode.id)
    return True


async def _main() -> None:
    configure_logging(get_settings().log_level)
    try:
        async with get_sessionmaker()() as session:
            created = await seed(session)
            novel_created = await seed_sample_novel(session)
    finally:
        await get_engine().dispose()
    logger.info(
        "seed_finished",
        created=len(created),
        existing=len(SEED_ACCOUNTS) - len(created),
        sample_novel_created=novel_created,
    )


if __name__ == "__main__":
    asyncio.run(_main())
