"""로컬 AI 결과 DB 테이블 초기화 스크립트

주의:
    이 스크립트는 .env.dev의 로컬 DB 설정을 사용한다.
    관제 원본 DB가 아니라 AI 서버 결과 DB를 초기화한다.
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

# 이 스크립트는 레포 루트에 있으므로 parent가 곧 프로젝트 루트다.
# (기존 parents[1]은 레포 상위 폴더를 가리켜 잘못된 경로였다.)
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

# SQLAlchemy 모델 등록
import core.model.models  # noqa: F401

from core.db import Base
from core.setting import Settings


async def main():
    settings = Settings()

    print("========================================")
    print("Local AI Result DB Reset")
    print("========================================")
    print(f"DB_HOST = {settings.DB_HOST}")
    print(f"DB_PORT = {settings.DB_PORT}")
    print(f"DB_NAME = {settings.DB_NAME}")
    print(f"DB_USER = {settings.DB_USER}")
    print("========================================")

    engine = create_async_engine(
        settings.async_db_url,
        echo=True,
        future=True,
    )

    async with engine.begin() as conn:
        print("기존 테이블 삭제 중...")
        await conn.run_sync(Base.metadata.drop_all)

        print("새 테이블 생성 중...")
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()

    print("========================================")
    print("로컬 DB 테이블 초기화 완료")
    print("========================================")


if __name__ == "__main__":
    asyncio.run(main())