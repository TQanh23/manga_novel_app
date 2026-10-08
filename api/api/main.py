from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Manga & Novel API", version="0.1.0")

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
