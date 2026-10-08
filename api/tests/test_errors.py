"""Every error leaves the API in one envelope, and nothing the client sent is echoed back."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import BaseModel, Field

from api.core.errors import AppError
from api.core.request_id import REQUEST_ID_HEADER

LogLines = Callable[[], list[dict[str, Any]]]


class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=8)


@pytest.fixture
def failing_routes(app: FastAPI) -> None:
    async def out_of_coins() -> None:
        raise AppError(
            "insufficient_coins",
            "Not enough coins",
            status_code=402,
            headers={"X-Balance": "0"},
        )

    async def crash() -> None:
        raise RuntimeError("chapter text that must not reach the client")

    async def login(credentials: Credentials) -> dict[str, str]:
        return {"email": credentials.email}

    app.add_api_route("/v1/out-of-coins", out_of_coins)
    app.add_api_route("/v1/crash", crash)
    app.add_api_route("/v1/login", login, methods=["POST"])


async def test_unknown_path_returns_the_envelope(client: AsyncClient) -> None:
    response = await client.get("/v1/nope", headers={REQUEST_ID_HEADER: "req-404"})

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "request_id": "req-404",
            "details": None,
        }
    }


async def test_wrong_method_returns_the_envelope(client: AsyncClient) -> None:
    response = await client.post("/healthz")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


@pytest.mark.usefixtures("failing_routes")
async def test_app_error_keeps_its_code_status_and_headers(client: AsyncClient) -> None:
    response = await client.get("/v1/out-of-coins")

    assert response.status_code == 402
    assert response.headers["X-Balance"] == "0"
    assert response.json()["error"] == {
        "code": "insufficient_coins",
        "message": "Not enough coins",
        "request_id": response.headers[REQUEST_ID_HEADER],
        "details": None,
    }


@pytest.mark.usefixtures("failing_routes")
async def test_validation_error_lists_fields_without_echoing_input(client: AsyncClient) -> None:
    response = await client.post("/v1/login", json={"email": "a@b.co", "password": "hunter2"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"] == [
        {
            "loc": ["body", "password"],
            "msg": "String should have at least 8 characters",
            "type": "string_too_short",
        }
    ]
    assert "hunter2" not in response.text


@pytest.mark.usefixtures("failing_routes")
async def test_unexpected_exception_becomes_a_500_that_reveals_nothing(
    client: AsyncClient, log_lines: LogLines
) -> None:
    response = await client.get("/v1/crash", headers={REQUEST_ID_HEADER: "req-500"})

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == "req-500"
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Internal server error",
            "request_id": "req-500",
            "details": None,
        }
    }
    assert "chapter text" not in response.text

    events = {line["event"]: line for line in log_lines()}
    assert events["unhandled_exception"]["request_id"] == "req-500"
    assert events["http_request"]["status"] == 500
