from time import perf_counter

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.core.errors import internal_error_response
from api.core.metrics import observe_request
from api.core.request_id import REQUEST_ID_HEADER, resolve_request_id

logger = structlog.get_logger(__name__)

# Probed every few seconds by Compose and scrapers; logging them would drown the rest.
_QUIET_PATHS = frozenset({"/healthz", "/readyz", "/metrics"})
_UNMATCHED_ROUTE = "unmatched"


def _route_template(scope: Scope) -> str:
    """The matched path with parameter values swapped back for their names.

    Rebuilt from the path and its parameters because the route object's own
    path is relative to its router and so lacks the /v1 prefix. Anything that
    matched no route shares one label, which keeps metric cardinality bounded.
    """
    if "endpoint" not in scope:
        return _UNMATCHED_ROUTE
    names = {str(value): name for name, value in scope.get("path_params", {}).items()}
    return "/".join(
        f"{{{names[segment]}}}" if segment in names else segment
        for segment in scope["path"].split("/")
    )


class RequestContextMiddleware:
    """Outermost middleware: request id, access log, latency metric, last-resort 500.

    Written as plain ASGI so the request id bound here is visible to the endpoint
    and to anything it awaits, and so streamed responses (SSE) are not buffered.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = resolve_request_id(Headers(scope=scope).get(REQUEST_ID_HEADER))
        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_started = True
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        started = perf_counter()
        with structlog.contextvars.bound_contextvars(request_id=request_id):
            try:
                await self.app(scope, receive, send_with_request_id)
            except Exception:
                # The message of an unexpected exception is not trusted to be
                # free of content, so the client only ever gets the envelope.
                logger.exception("unhandled_exception")
                if not response_started:
                    await internal_error_response()(scope, receive, send_with_request_id)
            finally:
                if scope["path"] not in _QUIET_PATHS:
                    route_path = _route_template(scope)
                    duration = perf_counter() - started
                    observe_request(scope["method"], route_path, status_code, duration)
                    logger.info(
                        "http_request",
                        method=scope["method"],
                        path=scope["path"],
                        route=route_path,
                        status=status_code,
                        duration_ms=round(duration * 1000, 2),
                    )
