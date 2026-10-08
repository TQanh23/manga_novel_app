from fastapi import FastAPI
from httpx import AsyncClient
from prometheus_client import REGISTRY


def request_count(method: str, route: str, status: str) -> float:
    value = REGISTRY.get_sample_value(
        "http_request_duration_seconds_count",
        {"method": method, "route": route, "status": status},
    )
    return value or 0.0


async def test_requests_are_measured_by_route_template(app: FastAPI, client: AsyncClient) -> None:
    async def read_thing(thing_id: str) -> dict[str, str]:
        return {"thing_id": thing_id}

    app.add_api_route("/v1/metered/{thing_id}", read_thing)
    before = request_count("GET", "/v1/metered/{thing_id}", "200")

    await client.get("/v1/metered/1")
    await client.get("/v1/metered/2")

    assert request_count("GET", "/v1/metered/{thing_id}", "200") == before + 2
    assert request_count("GET", "/v1/metered/1", "200") == 0


async def test_routes_on_nested_routers_keep_their_prefix(client: AsyncClient) -> None:
    route = "/v1/admin/users/{user_id}"
    before = request_count("PATCH", route, "401")

    await client.patch("/v1/admin/users/0199e2a4-0000-7000-8000-000000000001", json={})

    assert request_count("PATCH", route, "401") == before + 1


async def test_unmatched_paths_share_one_label(client: AsyncClient) -> None:
    before = request_count("GET", "unmatched", "404")

    await client.get("/v1/does-not-exist/a")
    await client.get("/v1/does-not-exist/b")

    assert request_count("GET", "unmatched", "404") == before + 2


async def test_metrics_endpoint_serves_the_prometheus_format(client: AsyncClient) -> None:
    await client.get("/v1/anything")

    response = await client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "http_request_duration_seconds_bucket" in response.text
