from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Histogram, generate_latest

_KNOWN_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "Time spent handling an HTTP request.",
    ["method", "route", "status"],
)

router = APIRouter()


def observe_request(method: str, route: str, status_code: int, seconds: float) -> None:
    # Labels must stay low-cardinality: the route template, never the raw path,
    # and only methods we know.
    REQUEST_DURATION.labels(
        method=method if method in _KNOWN_METHODS else "OTHER",
        route=route,
        status=str(status_code),
    ).observe(seconds)


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
