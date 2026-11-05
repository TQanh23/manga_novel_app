"""Create the development data: four accounts, a sample novel and a shelf of sample works.

    uv run python -m api.scripts.seed

Runs on `docker compose up`. Safe to run again: an account or a sample novel
that already exists is left exactly as it is. The accounts share a password
that is in the repository, so this refuses to run anywhere but a local
environment.

The novel's text and glossary live in infra/seed/sample_novel; it is the base
of the AI eval set. Shorter works in infra/seed/catalogue give the reader's
homepage and the browse filters something to show. All of them are published
through the same services an author's requests go through, so their versions,
published pointers and glossaries are what the API would have produced.
"""

import asyncio
import tomllib
from dataclasses import dataclass
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import repository, service
from api.auth.models import Locale, Role, User
from api.author import repository as author_repository
from api.author import service as author_service
from api.author.schemas import GlossaryEntryCreate, WorkCreate
from api.catalogue.models import WorkStatus, WorkType
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
CATALOGUE_DIRECTORY = "catalogue"


@dataclass(frozen=True)
class SampleEpisode:
    title: str
    body_html: str


@dataclass(frozen=True)
class SampleNovel:
    work: WorkCreate
    episodes: tuple[SampleEpisode, ...]
    glossary: tuple[GlossaryEntryCreate, ...]
    status: WorkStatus = WorkStatus.ONGOING


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
        glossary=tuple(
            GlossaryEntryCreate.model_validate(entry) for entry in data.get("glossary", [])
        ),
        status=WorkStatus(data.get("status", WorkStatus.ONGOING)),
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
    return await _publish_sample(session, author, novel)


def catalogue_directories() -> list[Path]:
    """The sample works for the catalogue, one directory each, in a stable order."""
    root = get_settings().seed_dir / CATALOGUE_DIRECTORY
    return sorted(path for path in root.iterdir() if (path / "novel.toml").is_file())


async def seed_catalogue_samples(session: AsyncSession) -> int:
    """Publish the catalogue's sample works for the seeded author. Returns how many were new.

    Like the sample novel, each is marked is_sample and left alone once it exists.
    """
    _require_local()
    author = await repository.get_user_by_email(session, SAMPLE_NOVEL_AUTHOR)
    if author is None:
        raise RuntimeError("Seed the accounts before the sample works.")
    created = 0
    for directory in catalogue_directories():
        if await _publish_sample(session, author, load_sample_novel(directory)):
            created += 1
    return created


async def _publish_sample(session: AsyncSession, author: User, novel: SampleNovel) -> bool:
    """Create and publish one sample work. False if the author already has it."""
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
    if novel.status != WorkStatus.ONGOING:
        await author_service.update_work(
            session, author=author, work_id=state.work.id, changes={"status": novel.status}
        )
    return True


async def _main() -> None:
    configure_logging(get_settings().log_level)
    try:
        async with get_sessionmaker()() as session:
            created = await seed(session)
            novel_created = await seed_sample_novel(session)
            samples_created = await seed_catalogue_samples(session)
    finally:
        await get_engine().dispose()
    logger.info(
        "seed_finished",
        created=len(created),
        existing=len(SEED_ACCOUNTS) - len(created),
        sample_novel_created=novel_created,
        catalogue_samples_created=samples_created,
    )


if __name__ == "__main__":
    asyncio.run(_main())
