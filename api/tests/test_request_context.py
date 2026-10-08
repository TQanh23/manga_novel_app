"""NFR-10: every request has an id that is echoed back and present in its log lines."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from api.core.request_id import REQUEST_ID_HEADER, get_request_id

LogLines = Callable[[], list[dict[str, Any]]]


@pytest.fixture
def things_route(app: FastAPI) -> None:
    async def read_thing(thing_id: str) -> dict[str, str | None]:
        return {"thing_id": thing_id, "request_id": get_request_id()}

    app.add_api_route("/v1/things/{thing_id}", read_thing)


async def test_a_request_without_an_id_gets_a_uuid7(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert UUID(response.headers[REQUEST_ID_HEADER]).version == 7


async def test_a_well_formed_incoming_id_is_kept(client: AsyncClient) -> None:
    response = await client.get("/healthz", headers={REQUEST_ID_HEADER: "mobile-7f3a.42_x"})

    assert response.headers[REQUEST_ID_HEADER] == "mobile-7f3a.42_x"


@pytest.mark.parametrize("incoming", ["has space", "x" * 65, '{"inject":"json"}', ""])
async def test_a_malformed_incoming_id_is_replaced(client: AsyncClient, incoming: str) -> None:
    response = await client.get("/healthz", headers={REQUEST_ID_HEADER: incoming})

    assert response.headers[REQUEST_ID_HEADER] != incoming
    assert UUID(response.headers[REQUEST_ID_HEADER]).version == 7


@pytest.mark.usefixtures("things_route")
async def test_the_endpoint_sees_the_request_id(client: AsyncClient) -> None:
    response = await client.get("/v1/things/42", headers={REQUEST_ID_HEADER: "req-1"})

    assert response.json() == {"thing_id": "42", "request_id": "req-1"}


@pytest.mark.usefixtures("things_route")
async def test_the_access_log_line_carries_the_request_id_and_route_template(
    client: AsyncClient, log_lines: LogLines
) -> None:
    await client.get("/v1/things/42?token=not-logged", headers={REQUEST_ID_HEADER: "req-2"})

    (line,) = [line for line in log_lines() if line["event"] == "http_request"]
    assert line["request_id"] == "req-2"
    assert line["method"] == "GET"
    assert line["path"] == "/v1/things/42"
    assert line["route"] == "/v1/things/{thing_id}"
    assert line["status"] == 200
    assert line["duration_ms"] >= 0
    assert "not-logged" not in str(line)


async def test_the_request_id_does_not_leak_into_the_next_request(client: AsyncClient) -> None:
    first = await client.get("/healthz", headers={REQUEST_ID_HEADER: "req-3"})
    second = await client.get("/healthz")

    assert first.headers[REQUEST_ID_HEADER] == "req-3"
    assert second.headers[REQUEST_ID_HEADER] != "req-3"
    assert get_request_id() is None


async def test_probe_endpoints_are_not_logged(client: AsyncClient, log_lines: LogLines) -> None:
    await client.get("/healthz")
    await client.get("/metrics")

    assert [line for line in log_lines() if line["event"] == "http_request"] == []
