"""The OpenAPI document is the source of the generated client, so its names are a contract."""

from typing import Any

from api.main import create_app

EXPECTED_OPERATIONS = {
    ("post", "/v1/auth/register"): "auth_register_user",
    ("post", "/v1/auth/login"): "auth_login",
    ("post", "/v1/auth/refresh"): "auth_refresh_token",
    ("post", "/v1/auth/logout"): "auth_logout",
    ("get", "/v1/me"): "auth_get_me",
    ("post", "/v1/me/roles/author"): "auth_add_author_role",
    ("patch", "/v1/admin/users/{user_id}"): "admin_update_user",
    ("post", "/v1/admin/jobs/ping"): "admin_enqueue_ping",
    ("get", "/v1/author/wuf-presets"): "author_list_wuf_presets",
    ("post", "/v1/author/works"): "author_create_work",
    ("get", "/v1/author/works"): "author_list_works",
    ("get", "/v1/author/works/{work_id}"): "author_get_work",
    ("patch", "/v1/author/works/{work_id}"): "author_update_work",
    ("post", "/v1/author/works/{work_id}/episodes"): "author_create_episode",
    ("get", "/v1/author/works/{work_id}/episodes"): "author_list_episodes",
    ("get", "/v1/author/episodes/{episode_id}"): "author_get_episode",
    ("put", "/v1/author/episodes/{episode_id}/draft"): "author_save_draft",
    ("get", "/v1/author/episodes/{episode_id}/draft"): "author_get_draft",
    ("get", "/v1/author/episodes/{episode_id}/versions"): "author_list_versions",
    ("get", "/v1/author/episodes/{episode_id}/versions/{version_id}"): "author_get_version",
    (
        "post",
        "/v1/author/episodes/{episode_id}/versions/{version_id}/restore",
    ): "author_restore_version",
    ("post", "/v1/author/episodes/{episode_id}/publish"): "author_publish_episode",
    ("post", "/v1/author/episodes/{episode_id}/schedule"): "author_schedule_episode",
    ("delete", "/v1/author/episodes/{episode_id}/schedule"): "author_unschedule_episode",
    ("get", "/v1/works"): "catalogue_list_works",
    ("get", "/v1/works/{work_id}"): "catalogue_get_work",
    ("get", "/v1/works/{work_id}/episodes"): "catalogue_list_episodes",
    ("get", "/v1/search"): "catalogue_search_works",
    ("get", "/v1/genres"): "catalogue_list_genres",
    ("get", "/v1/episodes/{episode_id}/content"): "reader_get_episode_content",
    ("put", "/v1/progress/{episode_id}"): "reader_save_progress",
    ("get", "/v1/library"): "reader_get_library",
    ("put", "/v1/favourites/{work_id}"): "reader_add_favourite",
    ("delete", "/v1/favourites/{work_id}"): "reader_remove_favourite",
}

ERROR_REF = {"$ref": "#/components/schemas/ErrorResponse"}


def operations() -> dict[tuple[str, str], dict[str, Any]]:
    paths: dict[str, dict[str, dict[str, Any]]] = create_app().openapi()["paths"]
    return {
        (method, path): operation
        for path, methods in paths.items()
        for method, operation in methods.items()
    }


def test_every_v1_operation_has_its_explicit_operation_id() -> None:
    assert {key: operation["operationId"] for key, operation in operations().items()} == (
        EXPECTED_OPERATIONS
    )


def test_every_v1_operation_documents_the_error_envelope() -> None:
    for key, operation in operations().items():
        responses = operation["responses"]
        assert responses["default"]["content"]["application/json"]["schema"] == ERROR_REF, key
        assert responses["422"]["content"]["application/json"]["schema"] == ERROR_REF, key


def test_fastapis_own_validation_error_schema_is_not_exposed() -> None:
    schemas = create_app().openapi()["components"]["schemas"]

    assert "HTTPValidationError" not in schemas
    assert "ErrorResponse" in schemas


def test_probe_endpoints_stay_out_of_the_schema() -> None:
    paths = create_app().openapi()["paths"]

    assert not {"/healthz", "/readyz", "/metrics"} & set(paths)
