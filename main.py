"""KESCO AI API Server Main"""

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# SQLAlchemy 모델 등록용 import
# 이 import가 있어야 Base.metadata.create_all() 할 때 테이블들이 등록된다.
import core.model.models  # noqa: F401

from core.container import container
from router.anomaly_router import router as anomaly_router
from router.health_router import router as health_router
from router.monitor_router import router as monitor_router
from router.pipeline_router import router as pipeline_router
from router.site_router import router as site_router


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SWAGGER_UI_DIR = STATIC_DIR / "swagger-ui"
MONITOR_UI_DIR = STATIC_DIR / "monitor"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 시작/종료 처리"""

    logger = container.logger()
    settings = container.settings()

    logger.info("==================================================")
    logger.info(f"🚀 {settings.APP_NAME} API Server starting...")
    logger.info(f"🚀 Version: {settings.APP_VERSION}")
    logger.info("==================================================")

    db_local_service = container.db_local_service()
    await db_local_service.init_db()

    scheduler_service = container.scheduler_service()
    scheduler_service.start()

    logger.info("✅ FastAPI startup complete")

    yield

    logger.info("==================================================")
    logger.info("🛑 KESCO AI API Server shutting down...")
    logger.info("==================================================")

    scheduler_service.stop()

    remote_db_service = container.remote_db_service()
    await remote_db_service.close()

    await db_local_service.close()

    logger.info("✅ FastAPI shutdown complete")


app = FastAPI(
    title="KESCO AI API Server",
    description="""
KESCO ESS 관제 데이터 기반 AI 분석 API 서버

주요 기능:
- 관제 DB 사이트/장치 목록 조회
- 관제 DB 사이트/장치 목록 로컬 DB 동기화
- 하루 1회 AI 파이프라인 자동 실행
- Swagger를 통한 AI 파이프라인 수동 실행
- AI 결과 데이터 조회
- 파이프라인 실행 이력 조회
""",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)


# ============================================================
# Static files
# ============================================================

if SWAGGER_UI_DIR.exists():
    app.mount(
        "/static/swagger-ui",
        StaticFiles(directory=str(SWAGGER_UI_DIR)),
        name="swagger-ui",
    )

if MONITOR_UI_DIR.exists():
    app.mount(
        "/static/monitor",
        StaticFiles(directory=str(MONITOR_UI_DIR)),
        name="monitor-ui",
    )


# ============================================================
# Offline Swagger UI
# ============================================================

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """외부 CDN 없이 로컬 정적 파일로 Swagger UI를 제공한다."""

    if not SWAGGER_UI_DIR.exists():
        return {
            "status": "error",
            "message": "static/swagger-ui 폴더가 없습니다. 오프라인 Swagger 정적 파일을 먼저 배치하세요.",
        }

    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="KESCO AI API Server - Swagger UI",
        swagger_js_url="/static/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui/swagger-ui.css",
        swagger_favicon_url="/static/swagger-ui/favicon-32x32.png",
        swagger_ui_parameters={
            "deepLinking": True,
            "displayRequestDuration": True,
            "defaultModelsExpandDepth": -1,
            "tryItOutEnabled": True,
        },
    )


# ============================================================
# Monitor UI
# ============================================================

@app.get("/monitor", include_in_schema=False)
@app.get("/monitor/", include_in_schema=False)
async def monitor_ui():
    """내부망 AI 모니터링 웹 화면을 제공한다."""

    return FileResponse(str(MONITOR_UI_DIR / "index.html"))


# ============================================================
# Routers
# ============================================================

app.include_router(health_router)
app.include_router(site_router)
app.include_router(pipeline_router)
app.include_router(monitor_router)
app.include_router(anomaly_router)


@app.get(
    "/",
    tags=["Root"],
    summary="Root API",
)
async def root():
    """루트 API"""

    settings = container.settings()

    return {
        "status": "success",
        "message": "KESCO AI API Server is running.",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "monitor": "/monitor",
        "health": "/api/v1/health",
    }


if __name__ == "__main__":
    settings = container.settings()

    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
