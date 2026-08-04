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


    async def get_latest_site_scores(self, limit: int = 100) -> list[dict[str, Any]]:
        """anomaly_score 기반 사이트별 최신 위험 요약을 반환한다."""

        limit = max(1, min(int(limit), 500))
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
                return []

            columns = await self._columns_with_conn(conn, "anomaly_score")
            required = {"site_no", "bms_id", "max_score"}
            if not required.issubset(set(columns)):
                return []

            has_target_date = "target_date" in columns
            has_prediction_time = "prediction_time" in columns
            has_sensing_datetime = "sensing_datetime" in columns
            has_average_score = "average_score" in columns
            has_max_level = "max_level" in columns

            count_exprs = []
            for col, alias in [
                ("bank_no", "bank_count"),
                ("rack_no", "rack_count"),
                ("string_no", "string_count"),
                ("module_no", "module_count"),
            ]:
                if col in columns:
                    count_exprs.append(f'COUNT(DISTINCT "{col}") AS {alias}')
                else:
                    count_exprs.append(f'0 AS {alias}')

            target_expr = 'MAX("target_date") AS target_date' if has_target_date else 'NULL AS target_date'
            prediction_expr = 'MAX("prediction_time") AS last_analysis_time' if has_prediction_time else 'NULL AS last_analysis_time'
            sensing_expr = 'MAX("sensing_datetime") AS last_data_time' if has_sensing_datetime else 'NULL AS last_data_time'
            avg_expr = 'AVG("average_score") AS average_score' if has_average_score else 'AVG("max_score") AS average_score'
            level_expr = 'MAX("max_level") AS max_level' if has_max_level else 'NULL AS max_level'

            if has_target_date:
                source_sql = """
                    WITH latest AS (
                        SELECT "site_no", "bms_id", MAX("target_date") AS target_date
                        FROM "anomaly_score"
                        GROUP BY "site_no", "bms_id"
                    )
                    SELECT a.*
                    FROM "anomaly_score" a
                    JOIN latest l
                      ON l."site_no" = a."site_no"
                     AND l."bms_id" = a."bms_id"
                     AND l.target_date = a."target_date"
                """
            else:
                source_sql = 'SELECT * FROM "anomaly_score"'

            sql = f"""
                WITH src AS ({source_sql})
                SELECT
                    "site_no",
                    "bms_id",
                    {target_expr},
                    {prediction_expr},
                    {sensing_expr},
                    MAX("max_score") AS latest_score,
                    {avg_expr},
                    {level_expr},
                    COUNT(*) AS score_row_count,
                    {", ".join(count_exprs)}
                FROM src
                GROUP BY "site_no", "bms_id"
                ORDER BY MAX("max_score") DESC NULLS LAST
                LIMIT $1
            """
            rows = await conn.fetch(sql, limit)
            return [{key: _json_safe(value) for key, value in dict(row).items()} for row in rows]
        finally:
            await conn.close()

    async def get_pipeline_status_summary(self) -> dict[str, Any]:
        """pipeline_run_log의 성공/실패/최근 실행 현황을 반환한다."""

        conn = await self._connect()
        try:
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = 'pipeline_run_log'
                )
                """
            )
            if not exists:
                return {"exists": False, "total_count": 0, "success_count": 0, "failed_count": 0}

            columns = await self._columns_with_conn(conn, "pipeline_run_log")
            if "status" not in columns:
                return {"exists": True, "total_count": 0, "success_count": 0, "failed_count": 0}

            time_col = next((col for col in ["finished_at", "started_at", "inserted", "target_date"] if col in columns), None)
            time_expr = f'MAX("{time_col}") AS last_run_time' if time_col else 'NULL AS last_run_time'
            row = await conn.fetchrow(
                f"""
                SELECT
                    COUNT(*) AS total_count,
                    COUNT(*) FILTER (WHERE "status" = 'success') AS success_count,
                    COUNT(*) FILTER (WHERE "status" <> 'success') AS failed_count,
                    {time_expr}
                FROM "pipeline_run_log"
                """
            )
            result = {key: _json_safe(value) for key, value in dict(row).items()} if row else {}
            result["exists"] = True
            return result
        finally:
            await conn.close()

    async def get_latest_module_score_row(self, site_no: int, bms_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        """특정 site_no/bms_id의 최신 또는 최악 module row를 반환한다."""

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
                return None

            columns = await self._columns_with_conn(conn, "anomaly_score")
            if "site_no" not in columns or "max_score" not in columns:
                return None

            selected = [
                col for col in [
                    "id", "pipeline_run_id", "site_no", "bms_id", "target_date", "serial_number",
                    "sensing_datetime", "prediction_time", "bank_no", "rack_no", "string_no", "module_no",
                    *[f"cell_{i}_score" for i in range(1, 21)],
                    *[f"cell_{i}_level" for i in range(1, 21)],
                    "max_score", "max_level", "average_score", "inserted", "updated",
                ] if col in columns
            ]
            if not selected:
                return None
            select_sql = ", ".join(f'"{col}"' for col in selected)
            order_candidates = [col for col in ["max_score", "prediction_time", "sensing_datetime", "inserted", "id"] if col in columns]
            order_sql = ", ".join(f'"{col}" DESC NULLS LAST' for col in order_candidates)
            if bms_id and "bms_id" in columns:
                row = await conn.fetchrow(
                    f'SELECT {select_sql} FROM "anomaly_score" WHERE "site_no" = $1 AND "bms_id" = $2 ORDER BY {order_sql} LIMIT 1',
                    site_no,
                    bms_id,
                )
            else:
                row = await conn.fetchrow(
                    f'SELECT {select_sql} FROM "anomaly_score" WHERE "site_no" = $1 ORDER BY {order_sql} LIMIT 1',
                    site_no,
                )
            return {key: _json_safe(value) for key, value in dict(row).items()} if row else None
        finally:
            await conn.close()

    async def _columns_with_conn(self, conn: Any, table_name: str) -> list[str]:
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


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
