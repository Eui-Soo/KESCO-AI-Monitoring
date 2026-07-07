"""KESCO AI API Server Main"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

# SQLAlchemy 모델 등록용 import
# 이 import가 있어야 Base.metadata.create_all() 할 때 테이블들이 등록된다.
import core.model.models  # noqa: F401

from core.container import container
from router.anomaly_router import router as anomaly_router
from router.health_router import router as health_router
from router.pipeline_router import router as pipeline_router
from router.site_router import router as site_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 시작/종료 처리"""

    # ------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------
    logger = container.logger()
    settings = container.settings()

    logger.info("==================================================")
    logger.info(f"🚀 {settings.APP_NAME} API Server starting...")
    logger.info(f"🚀 Version: {settings.APP_VERSION}")
    logger.info("==================================================")

    # 1. 로컬 DB 테이블 생성
    db_local_service = container.db_local_service()
    await db_local_service.init_db()

    # 2. 하루 1회 자동 실행 스케줄러 시작
    scheduler_service = container.scheduler_service()
    scheduler_service.start()

    logger.info("✅ FastAPI startup complete")

    yield

    # ------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------
    logger.info("==================================================")
    logger.info("🛑 KESCO AI API Server shutting down...")
    logger.info("==================================================")

    # 1. 스케줄러 종료
    scheduler_service.stop()

    # 2. DB 연결 종료
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
)


# ============================================================
# Routers
# ============================================================

app.include_router(health_router)
app.include_router(site_router)
app.include_router(pipeline_router)
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