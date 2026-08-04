"""Monitor DB repository.

1차 실제 DB 연동 준비 계층이다.
- 현재 화면 응답 구조는 service의 mock 데이터를 유지한다.
- 이 repository는 로컬 DB에 실제로 연결 가능한지, anomaly_score / pipeline_run_log에
  어떤 데이터가 있는지 안전하게 확인하는 용도다.
- 테이블/컬럼이 일부 달라도 서버가 죽지 않도록 information_schema 기반으로 동작한다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class DbConnectConfig:
    host: str = "127.0.0.1"
    port: int = 5432
    database: str = "kesco_digitaltwin"
    user: str = "kesco"
    password: str = "kesco"

    @classmethod
    def from_env(cls) -> "DbConnectConfig":
        return cls(
            host=os.getenv("DB_HOST", os.getenv("LOCAL_DB_HOST", "127.0.0.1")),
            port=int(os.getenv("DB_PORT", os.getenv("LOCAL_DB_PORT", "5432"))),
            database=os.getenv("DB_NAME", os.getenv("LOCAL_DB_NAME", "kesco_digitaltwin")),
            user=os.getenv("DB_USER", os.getenv("LOCAL_DB_USER", "kesco")),
            password=os.getenv("DB_PASSWORD", os.getenv("LOCAL_DB_PASSWORD", "kesco")),
        )


class MonitorRepository:
    """로컬 PostgreSQL 조회 전담 계층.

    asyncpg를 직접 사용한다. 기존 SQLAlchemy 세션 구조를 건드리지 않아서,
    현재 프로젝트의 pipeline/anomaly 코드와 충돌 가능성이 낮다.
    """

    def __init__(self, config: Optional[DbConnectConfig] = None):
        self.config = config or DbConnectConfig.from_env()

    async def _connect(self):
        try:
            import asyncpg  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("asyncpg 패키지를 import 할 수 없습니다.") from exc

        return await asyncpg.connect(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.user,
            password=self.config.password,
            timeout=3,
        )

    async def ping(self) -> dict[str, Any]:
        try:
            conn = await self._connect()
            try:
                value = await conn.fetchval("SELECT 1")
                return {"ok": value == 1, "message": "local db connected"}
            finally:
                await conn.close()
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    async def table_exists(self, table_name: str) -> bool:
        conn = await self._connect()
        try:
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = $1
                )
                """,
                table_name,
            )
            return bool(exists)
        finally:
            await conn.close()

    async def get_columns(self, table_name: str) -> list[str]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = $1
                ORDER BY ordinal_position
                """,
                table_name,
            )
            return [row["column_name"] for row in rows]
        finally:
            await conn.close()

    async def get_table_summary(self, table_name: str) -> dict[str, Any]:
        """테이블 존재/건수/주요 시간 컬럼 범위를 안전하게 반환한다."""

        conn = await self._connect()
        try:
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = $1
                )
                """,
                table_name,
            )
            if not exists:
                return {"table": table_name, "exists": False, "row_count": 0, "columns": []}

            rows = await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = $1
                ORDER BY ordinal_position
                """,
                table_name,
            )
            columns = [row["column_name"] for row in rows]
            row_count = await conn.fetchval(f'SELECT COUNT(*) FROM "{table_name}"')

            time_candidates = [
                "prediction_time",
                "sensing_datetime",
                "date_time",
                "target_date",
                "inserted",
                "created_at",
                "updated_at",
            ]
            time_column = next((col for col in time_candidates if col in columns), None)
            time_range = None
            if time_column:
                time_row = await conn.fetchrow(
                    f'SELECT MIN("{time_column}") AS min_time, MAX("{time_column}") AS max_time FROM "{table_name}"'
                )
                time_range = {
                    "column": time_column,
                    "min": str(time_row["min_time"]) if time_row and time_row["min_time"] is not None else None,
                    "max": str(time_row["max_time"]) if time_row and time_row["max_time"] is not None else None,
                }

            return {
                "table": table_name,
                "exists": True,
                "row_count": int(row_count or 0),
                "columns": columns,
                "time_range": time_range,
            }
        finally:
            await conn.close()

    async def get_db_summary(self) -> dict[str, Any]:
        ping = await self.ping()
        if not ping["ok"]:
            return {
                "db_available": False,
                "message": ping["message"],
                "tables": [],
            }

        tables: list[dict[str, Any]] = []
        for table_name in ["anomaly_score", "pipeline_run_log"]:
            try:
                tables.append(await self.get_table_summary(table_name))
            except Exception as exc:
                tables.append({"table": table_name, "exists": False, "error": str(exc)})

        return {
            "db_available": True,
            "message": ping["message"],
            "connection": {
                "host": self.config.host,
                "port": self.config.port,
                "database": self.config.database,
                "user": self.config.user,
            },
            "tables": tables,
        }

    async def get_recent_anomaly_scores(self, limit: int = 20) -> dict[str, Any]:
        """anomaly_score 최근 행을 스키마 유연하게 조회한다."""

        limit = max(1, min(int(limit), 100))
        conn = await self._connect()
        try:
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = 'anomaly_score'
                )
                """
            )
            if not exists:
                return {"table": "anomaly_score", "exists": False, "items": []}

            rows = await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'anomaly_score'
                ORDER BY ordinal_position
                """
            )
            columns = [row["column_name"] for row in rows]
            preferred = [
                "id",
                "serial_number",
                "site_no",
                "bms_id",
                "date_time",
                "sensing_datetime",
                "prediction_time",
                "bank_no",
                "rack_no",
                "string_no",
                "module_no",
                "max_score",
                "max_level",
                "average_score",
                "inserted",
            ]
            selected = [col for col in preferred if col in columns]
            if not selected:
                selected = columns[:12]

            order_column = next(
                (col for col in ["prediction_time", "date_time", "sensing_datetime", "inserted", "id"] if col in columns),
                selected[0],
            )
            select_sql = ", ".join(f'"{col}"' for col in selected)
            rows = await conn.fetch(
                f'SELECT {select_sql} FROM "anomaly_score" ORDER BY "{order_column}" DESC LIMIT $1',
                limit,
            )
            items = [{key: _json_safe(value) for key, value in dict(row).items()} for row in rows]
            return {
                "table": "anomaly_score",
                "exists": True,
                "order_column": order_column,
                "columns": selected,
                "items": items,
            }
        finally:
            await conn.close()


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
