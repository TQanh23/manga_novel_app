"""Architecture rule 1: slow work is queued and the endpoint answers 202 with a job id."""

from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import Role
from api.core.jobs import Job, JobStatus
from api.core.request_id import REQUEST_ID_HEADER
from api.testing import AuthHeaders, MakeUser


async def test_admin_ping_returns_202_with_a_queued_job(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    admin = await make_user(Role.ADMIN)

    response = await client.post(
        "/v1/admin/jobs/ping", headers={**auth_headers(admin), REQUEST_ID_HEADER: "req-ping"}
    )

    assert response.status_code == 202
    job = await db_session.get(Job, UUID(response.json()["job_id"]), populate_existing=True)
    assert job is not None
    assert (job.kind, job.target_id, job.status) == ("ping", admin.id, JobStatus.QUEUED)
    assert job.request_id == "req-ping"


async def test_each_ping_is_its_own_job(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    admin = await make_user(Role.ADMIN)

    first = await client.post("/v1/admin/jobs/ping", headers=auth_headers(admin))
    second = await client.post("/v1/admin/jobs/ping", headers=auth_headers(admin))

    assert first.json()["job_id"] != second.json()["job_id"]


async def test_fr_auth_03_only_admins_can_ping(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    author = await make_user(Role.READER, Role.AUTHOR)

    as_author = await client.post("/v1/admin/jobs/ping", headers=auth_headers(author))
    anonymous = await client.post("/v1/admin/jobs/ping")

    assert as_author.status_code == 403
    assert anonymous.status_code == 401
