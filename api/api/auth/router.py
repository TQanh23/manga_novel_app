from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from api.auth import service
from api.auth.deps import CurrentUser, Session, limit_by_user
from api.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from api.auth.service import IssuedTokens
from api.core.config import get_settings
from api.core.errors import AppError
from api.core.rate_limit import limit_by_identity, limit_by_ip

router = APIRouter(tags=["auth"])

REFRESH_COOKIE = "refresh_token"
# The cookie is only ever sent to the endpoints that need it.
_REFRESH_COOKIE_PATH = "/v1/auth"

RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE, include_in_schema=False)]


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    # SameSite=Strict assumes the web app and the API share a site, as they do
    # locally. A demo host on another site needs this revisited (D7).
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_ttl_seconds,
        path=_REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=_REFRESH_COOKIE_PATH,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="strict",
    )


def _require_allowed_origin(request: Request) -> None:
    """Second line of defence for cookie-authenticated calls, behind SameSite.

    Browsers always send Origin on a cross-origin POST; clients that are not
    browsers do not hold the cookie in the first place.
    """
    origin = request.headers.get("origin")
    if origin is not None and origin not in get_settings().cors_origins:
        raise AppError("origin_not_allowed", "Origin not allowed", status_code=403)


def _token_response(response: Response, tokens: IssuedTokens, *, use_cookie: bool) -> TokenResponse:
    if use_cookie:
        _set_refresh_cookie(response, tokens.refresh_token)
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        refresh_token=None if use_cookie else tokens.refresh_token,
        user=UserResponse.from_user(tokens.user),
    )


@router.post(
    "/auth/register",
    operation_id="auth_register_user",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_by_ip("register"))],
)
async def register(payload: RegisterRequest, session: Session) -> UserResponse:
    user = await service.register(
        session,
        email=payload.email,
        password=payload.password.get_secret_value(),
        display_name=payload.display_name,
        locale=payload.locale,
    )
    return UserResponse.from_user(user)


@router.post(
    "/auth/login",
    operation_id="auth_login",
    dependencies=[Depends(limit_by_ip("login"))],
)
async def login(payload: LoginRequest, response: Response, session: Session) -> TokenResponse:
    # Per account as well as per address, so a spread-out guessing run against
    # one email is slowed down too.
    await limit_by_identity("login", payload.email)
    tokens = await service.login(
        session, email=payload.email, password=payload.password.get_secret_value()
    )
    use_cookie = payload.token_transport == "cookie"  # noqa: S105 - a transport name
    return _token_response(response, tokens, use_cookie=use_cookie)


@router.post(
    "/auth/refresh",
    operation_id="auth_refresh_token",
    dependencies=[Depends(limit_by_ip("refresh"))],
)
async def refresh(
    request: Request,
    response: Response,
    session: Session,
    payload: RefreshRequest | None = None,
    cookie_token: RefreshCookie = None,
) -> TokenResponse:
    if cookie_token is not None:
        _require_allowed_origin(request)
    refresh_token = cookie_token or (payload.refresh_token if payload else None)
    if not refresh_token:
        raise AppError("invalid_refresh_token", "Sign in again", status_code=401)

    tokens = await service.refresh(session, refresh_token=refresh_token)
    return _token_response(response, tokens, use_cookie=cookie_token is not None)


@router.post(
    "/auth/logout",
    operation_id="auth_logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(limit_by_ip("logout"))],
)
async def logout(
    request: Request,
    response: Response,
    session: Session,
    payload: RefreshRequest | None = None,
    cookie_token: RefreshCookie = None,
) -> None:
    if cookie_token is not None:
        _require_allowed_origin(request)
    await service.logout(
        session, refresh_token=cookie_token or (payload.refresh_token if payload else None)
    )
    _clear_refresh_cookie(response)


@router.get("/me", operation_id="auth_get_me")
async def get_me(user: CurrentUser) -> UserResponse:
    return UserResponse.from_user(user)


@router.post(
    "/me/roles/author",
    operation_id="auth_add_author_role",
    dependencies=[Depends(limit_by_user("become-author"))],
)
async def add_author_role(user: CurrentUser, session: Session) -> UserResponse:
    user = await service.add_author_role(session, user)
    return UserResponse.from_user(user)
