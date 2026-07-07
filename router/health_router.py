from fastapi import APIRouter

from core.container import container


router = APIRouter(
    prefix="/api/v1",
    tags=["Health"],
)


@router.get("/health")
async def health_check():
    settings = container.settings()

    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "message": "KESCO DigitalTwin AI API server is running.",
    }