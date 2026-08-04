"""관제 DB 배터리 원본 데이터 조회 Repository

이 파일은 원격 관제 DB에서 AI 분석에 필요한 배터리 원본 데이터를 조회한다.

주요 조회 테이블:
    - tb_emc_mdul_mntly_rcd
        모듈 분단위 기록
        cell voltage 1~20, module temperature 포함

    - tb_emc_btrrck_mntly_rcd
        랙 분단위 기록
        SOC, SOH, DC 전압, DC 전류 포함

    - tb_emc_dvc_info
        장치 정보
        serial_number 후보값 조회용

현재 매핑:
    - serial_number: 우선 dvc_info.dvc_id, 없으면 m.bms_id
    - bank_no: 원본에 명확한 컬럼이 없어 기본값 0
    - rack_no: m.btrrck_no
    - string_no: 원본에 명확한 컬럼이 없어 기본값 0
    - module_no: m.dvc_no
"""

from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class BatteryRepository:
    """관제 DB 배터리 데이터 READ 전담 Repository"""

    async def find_by_date(
        self,
        session: AsyncSession,
        target_date: date,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> List[dict]:
        """특정 날짜/사이트/BMS의 배터리 원본 데이터를 조회한다.

        조회 범위:
            target_date 00:00:00 이상
            target_date + 1일 00:00:00 미만
        """

        start_datetime = datetime.combine(target_date, time.min)
        end_datetime = start_datetime + timedelta(days=1)

        query = self._build_query(
            site_no=site_no,
            bms_id=bms_id,
        )

        params = {
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
        }

        if site_no is not None:
            params["site_no"] = site_no

        if bms_id is not None:
            params["bms_id"] = bms_id

        result = await session.execute(
            text(query),
            params,
        )

        rows = result.mappings().all()

        return [
            self._to_standard_dict(
                row=dict(row),
                target_date=target_date,
            )
            for row in rows
        ]

    def _build_query(
        self,
        site_no: Optional[int],
        bms_id: Optional[str],
    ) -> str:
        """관제 DB 배터리 데이터 조회 SQL 생성"""

        where_conditions = [
            "m.srvr_rcd_dt >= :start_datetime",
            "m.srvr_rcd_dt < :end_datetime",
        ]

        if site_no is not None:
            where_conditions.append("m.site_no = :site_no")

        if bms_id is not None:
            where_conditions.append("m.bms_id = :bms_id")

        where_sql = "\n                  AND ".join(where_conditions)

        return f"""
            SELECT
                m.site_no,
                m.bms_id,
                m.bms_no,
                m.btrrck_no AS rack_no,
                m.dvc_no AS module_no,
                m.srvr_rcd_dt AS measured_at,
                m.dvc_rcd_dt,

                COALESCE(d.dvc_id, m.bms_id) AS serial_number,

                m.mdul_tp_1,
                m.mdul_tp_2,
                m.mdul_tp_3,

                m.cll_1_vltg  AS cv_1,
                m.cll_2_vltg  AS cv_2,
                m.cll_3_vltg  AS cv_3,
                m.cll_4_vltg  AS cv_4,
                m.cll_5_vltg  AS cv_5,
                m.cll_6_vltg  AS cv_6,
                m.cll_7_vltg  AS cv_7,
                m.cll_8_vltg  AS cv_8,
                m.cll_9_vltg  AS cv_9,
                m.cll_10_vltg AS cv_10,
                m.cll_11_vltg AS cv_11,
                m.cll_12_vltg AS cv_12,
                m.cll_13_vltg AS cv_13,
                m.cll_14_vltg AS cv_14,
                m.cll_15_vltg AS cv_15,
                m.cll_16_vltg AS cv_16,
                m.cll_17_vltg AS cv_17,
                m.cll_18_vltg AS cv_18,
                m.cll_19_vltg AS cv_19,
                m.cll_20_vltg AS cv_20,

                r.soc,
                r.soh,
                r.dc_vltg,
                r.dc_crnt,
                r.avg_cll_vltg,
                r.max_cll_vltg,
                r.min_cll_vltg,
                r.avg_mdul_tp,
                r.max_mdul_tp,
                r.min_mdul_tp,
                r.dvc_stts AS rack_status

            FROM tb_emc_mdul_mntly_rcd m

            LEFT JOIN tb_emc_btrrck_mntly_rcd r
                ON r.site_no = m.site_no
               AND r.bms_id = m.bms_id
               AND r.dvc_no = m.btrrck_no
               AND r.srvr_rcd_dt = m.srvr_rcd_dt

            LEFT JOIN tb_emc_dvc_info d
                ON d.site_no = m.site_no
               AND d.dvc_id = m.bms_id

            WHERE {where_sql}

            ORDER BY
                m.site_no,
                m.bms_id,
                m.btrrck_no,
                m.dvc_no,
                m.srvr_rcd_dt
        """

    def _to_standard_dict(
        self,
        row: Dict,
        target_date: date,
    ) -> Dict:
        """관제 DB row를 AI 서버 내부 표준 dict로 변환한다."""

        site_no = self._to_int(row.get("site_no"), default=0)
        bms_id = self._to_str(row.get("bms_id"), default="UNKNOWN")
        rack_no = self._to_int(row.get("rack_no"), default=0)
        module_no = self._to_int(row.get("module_no"), default=0)

        serial_number = self._to_str(
            row.get("serial_number") or bms_id,
            default=bms_id,
        )

        measured_at = row.get("measured_at")

        standard = {
            # ----------------------------------------------------
            # 내부 관리 / 식별 정보
            # ----------------------------------------------------
            "site_no": site_no,
            "bms_id": bms_id,
            "bms_no": self._to_int(row.get("bms_no")),
            "ess_id": self._make_ess_id(site_no=site_no, bms_id=bms_id),

            # ----------------------------------------------------
            # 관제 시스템 결과 규격에 필요한 정보
            # ----------------------------------------------------
            "serial_number": serial_number,
            "sensing_datetime": measured_at,
            "date_time": measured_at,
            "measured_at": measured_at,
            "dvc_rcd_dt": row.get("dvc_rcd_dt"),

            # 원본 DB에 bank/string 명확한 컬럼이 없으므로 기본값 0
            "bank_no": 0,
            "rack_no": rack_no,
            "string_no": 0,
            "module_no": module_no,

            # 기존 코드 일부 호환용
            "rack_idx": rack_no,
            "index": rack_no,

            # 날짜 검색용
            "target_date": target_date,
            "date": target_date,

            # ----------------------------------------------------
            # 랙 단위 값
            # tb_emc_btrrck_mntly_rcd
            # ----------------------------------------------------
            "soc": self._to_float(row.get("soc")),
            "soh": self._to_float(row.get("soh")),
            "voltage_v": self._to_float(row.get("dc_vltg")),
            "current_a": self._to_float(row.get("dc_crnt")),
            "avg_cell_voltage": self._to_float(row.get("avg_cll_vltg")),
            "max_cell_voltage": self._to_float(row.get("max_cll_vltg")),
            "min_cell_voltage": self._to_float(row.get("min_cll_vltg")),
            "avg_module_temperature": self._to_float(row.get("avg_mdul_tp")),
            "max_module_temperature": self._to_float(row.get("max_mdul_tp")),
            "min_module_temperature": self._to_float(row.get("min_mdul_tp")),
            "rack_status": self._to_str(row.get("rack_status")),

            # ----------------------------------------------------
            # 모듈 온도
            # tb_emc_mdul_mntly_rcd
            # ----------------------------------------------------
            "temperature_1": self._to_float(row.get("mdul_tp_1")),
            "temperature_2": self._to_float(row.get("mdul_tp_2")),
            "temperature_3": self._to_float(row.get("mdul_tp_3")),
        }

        for idx in range(1, 21):
            standard[f"cv_{idx}"] = self._to_float(row.get(f"cv_{idx}"))

        return standard

    def _make_ess_id(
        self,
        site_no: Optional[int],
        bms_id: Optional[str],
    ) -> str:
        """파일 저장 경로 등에 사용할 ESS ID 생성"""

        safe_site_no = site_no if site_no is not None else "UNKNOWN_SITE"
        safe_bms_id = str(bms_id or "UNKNOWN_BMS").strip()

        for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', ' ']:
            safe_bms_id = safe_bms_id.replace(ch, "_")

        return f"SITE_{safe_site_no}_BMS_{safe_bms_id}"

    def _to_str(self, value, default: Optional[str] = None) -> Optional[str]:
        """값을 문자열로 변환"""

        if value is None:
            return default

        text_value = str(value).strip()

        if text_value == "":
            return default

        return text_value

    def _to_int(self, value, default: Optional[int] = None) -> Optional[int]:
        """값을 int로 변환"""

        if value is None:
            return default

        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _to_float(self, value, default: Optional[float] = None) -> Optional[float]:
        """값을 float로 변환"""

        if value is None:
            return default

        try:
            return float(value)
        except (TypeError, ValueError):
            return default
        
    async def find_data_range(
        self,
        session: AsyncSession,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> Dict:
        """관제 DB에 저장된 배터리 원본 데이터의 보유 기간을 조회한다.

        기준:
            - module 데이터: tb_emc_mdul_mntly_rcd
            - rack 데이터: tb_emc_btrrck_mntly_rcd

        반환:
            특정 site_no / bms_id 기준으로
            데이터 시작 시각, 종료 시각, row 개수를 반환한다.
        """

        module_where = self._build_data_range_where(
            alias="m",
            site_no=site_no,
            bms_id=bms_id,
        )

        rack_where = self._build_data_range_where(
            alias="r",
            site_no=site_no,
            bms_id=bms_id,
        )

        params = {}

        if site_no is not None:
            params["site_no"] = site_no

        if bms_id is not None:
            params["bms_id"] = bms_id

        query = f"""
            SELECT
                md.module_start_datetime,
                md.module_end_datetime,
                md.module_device_start_datetime,
                md.module_device_end_datetime,
                md.module_count,
                md.module_bms_count,
                md.module_rack_count,
                md.module_device_count,

                rk.rack_start_datetime,
                rk.rack_end_datetime,
                rk.rack_device_start_datetime,
                rk.rack_device_end_datetime,
                rk.rack_count,
                rk.rack_bms_count,
                rk.rack_device_count

            FROM (
                SELECT
                    MIN(m.srvr_rcd_dt) AS module_start_datetime,
                    MAX(m.srvr_rcd_dt) AS module_end_datetime,
                    MIN(m.dvc_rcd_dt)  AS module_device_start_datetime,
                    MAX(m.dvc_rcd_dt)  AS module_device_end_datetime,
                    COUNT(*)           AS module_count,
                    COUNT(DISTINCT m.bms_id)    AS module_bms_count,
                    COUNT(DISTINCT m.btrrck_no) AS module_rack_count,
                    COUNT(DISTINCT m.dvc_no)    AS module_device_count
                FROM tb_emc_mdul_mntly_rcd m
                WHERE {module_where}
            ) md

            CROSS JOIN (
                SELECT
                    MIN(r.srvr_rcd_dt) AS rack_start_datetime,
                    MAX(r.srvr_rcd_dt) AS rack_end_datetime,
                    MIN(r.dvc_rcd_dt)  AS rack_device_start_datetime,
                    MAX(r.dvc_rcd_dt)  AS rack_device_end_datetime,
                    COUNT(*)           AS rack_count,
                    COUNT(DISTINCT r.bms_id) AS rack_bms_count,
                    COUNT(DISTINCT r.dvc_no) AS rack_device_count
                FROM tb_emc_btrrck_mntly_rcd r
                WHERE {rack_where}
            ) rk
        """

        result = await session.execute(text(query), params)
        row = dict(result.mappings().first() or {})

        module_count = int(row.get("module_count") or 0)
        rack_count = int(row.get("rack_count") or 0)

        module_start = row.get("module_start_datetime")
        module_end = row.get("module_end_datetime")

        return {
            "available": module_count > 0,
            "module": {
                "start_datetime": module_start,
                "end_datetime": module_end,
                "device_start_datetime": row.get("module_device_start_datetime"),
                "device_end_datetime": row.get("module_device_end_datetime"),
                "row_count": module_count,
                "bms_count": int(row.get("module_bms_count") or 0),
                "rack_count": int(row.get("module_rack_count") or 0),
                "device_count": int(row.get("module_device_count") or 0),
            },
            "rack": {
                "start_datetime": row.get("rack_start_datetime"),
                "end_datetime": row.get("rack_end_datetime"),
                "device_start_datetime": row.get("rack_device_start_datetime"),
                "device_end_datetime": row.get("rack_device_end_datetime"),
                "row_count": rack_count,
                "bms_count": int(row.get("rack_bms_count") or 0),
                "device_count": int(row.get("rack_device_count") or 0),
            },
            "analysis_base": {
                "start_datetime": module_start,
                "end_datetime": module_end,
                "basis": "tb_emc_mdul_mntly_rcd.srvr_rcd_dt",
                "reason": (
                    "현재 AI 원본 데이터 조회 기준이 "
                    "tb_emc_mdul_mntly_rcd.srvr_rcd_dt 이기 때문입니다."
                ),
            },
        }


    async def find_data_quality(
        self,
        session: AsyncSession,
        start_date: date,
        end_date: date,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
        expected_row_count_per_day: Optional[int] = None,
        minimum_completeness_rate: float = 0.8,
    ) -> Dict:
        """관제 DB 원본 데이터의 일자별 품질/충분성 정보를 조회한다.

        목적:
            - 특정 기간 분석을 실행하기 전에 날짜별 원본 데이터가 충분한지 확인한다.
            - 데이터가 아예 없는 날짜, 데이터가 적은 날짜, NULL 값이 많은 날짜를 구분한다.

        기준:
            - module 데이터: tb_emc_mdul_mntly_rcd
            - rack 데이터: tb_emc_btrrck_mntly_rcd
            - 날짜 기준: srvr_rcd_dt

        expected_row_count_per_day:
            - 값이 있으면 해당 값을 하루 기대 row 수로 사용한다.
            - 값이 없으면 조회 기간 중 가장 큰 module row 수를 임시 기대 row 수로 사용한다.
              이 값은 현장 데이터 주기에 따라 달라질 수 있으므로 참고 기준이다.
        """

        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date + timedelta(days=1), time.min)

        module_where = self._build_data_quality_where(
            alias="m",
            site_no=site_no,
            bms_id=bms_id,
        )
        rack_where = self._build_data_quality_where(
            alias="r",
            site_no=site_no,
            bms_id=bms_id,
        )

        params = {
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
        }

        if site_no is not None:
            params["site_no"] = site_no

        if bms_id is not None:
            params["bms_id"] = bms_id

        cell_null_condition = " OR ".join(
            f"m.cll_{idx}_vltg IS NULL" for idx in range(1, 21)
        )

        query = f"""
            WITH module_daily AS (
                SELECT
                    CAST(m.srvr_rcd_dt AS DATE) AS target_date,
                    COUNT(*) AS module_row_count,
                    COUNT(DISTINCT m.bms_id) AS bms_count,
                    COUNT(DISTINCT m.btrrck_no) AS rack_count,
                    COUNT(DISTINCT m.dvc_no) AS module_count,
                    COUNT(DISTINCT m.srvr_rcd_dt) AS measured_time_count,
                    MIN(m.srvr_rcd_dt) AS first_datetime,
                    MAX(m.srvr_rcd_dt) AS last_datetime,
                    SUM(
                        CASE
                            WHEN {cell_null_condition}
                            THEN 1 ELSE 0
                        END
                    ) AS cell_voltage_null_row_count,
                    SUM(
                        CASE
                            WHEN m.mdul_tp_1 IS NULL
                              OR m.mdul_tp_2 IS NULL
                              OR m.mdul_tp_3 IS NULL
                            THEN 1 ELSE 0
                        END
                    ) AS temperature_null_row_count
                FROM tb_emc_mdul_mntly_rcd m
                WHERE {module_where}
                GROUP BY CAST(m.srvr_rcd_dt AS DATE)
            ),
            rack_daily AS (
                SELECT
                    CAST(r.srvr_rcd_dt AS DATE) AS target_date,
                    COUNT(*) AS rack_row_count,
                    COUNT(DISTINCT r.bms_id) AS rack_bms_count,
                    COUNT(DISTINCT r.dvc_no) AS rack_device_count,
                    COUNT(DISTINCT r.srvr_rcd_dt) AS rack_measured_time_count,
                    SUM(
                        CASE
                            WHEN r.soc IS NULL
                              OR r.soh IS NULL
                              OR r.dc_vltg IS NULL
                              OR r.dc_crnt IS NULL
                            THEN 1 ELSE 0
                        END
                    ) AS rack_main_value_null_row_count
                FROM tb_emc_btrrck_mntly_rcd r
                WHERE {rack_where}
                GROUP BY CAST(r.srvr_rcd_dt AS DATE)
            )
            SELECT
                COALESCE(md.target_date, rd.target_date) AS target_date,
                COALESCE(md.module_row_count, 0) AS module_row_count,
                COALESCE(md.bms_count, 0) AS bms_count,
                COALESCE(md.rack_count, 0) AS rack_count,
                COALESCE(md.module_count, 0) AS module_count,
                COALESCE(md.measured_time_count, 0) AS measured_time_count,
                md.first_datetime,
                md.last_datetime,
                COALESCE(md.cell_voltage_null_row_count, 0) AS cell_voltage_null_row_count,
                COALESCE(md.temperature_null_row_count, 0) AS temperature_null_row_count,
                COALESCE(rd.rack_row_count, 0) AS rack_row_count,
                COALESCE(rd.rack_bms_count, 0) AS rack_bms_count,
                COALESCE(rd.rack_device_count, 0) AS rack_device_count,
                COALESCE(rd.rack_measured_time_count, 0) AS rack_measured_time_count,
                COALESCE(rd.rack_main_value_null_row_count, 0) AS rack_main_value_null_row_count
            FROM module_daily md
            FULL OUTER JOIN rack_daily rd
                ON rd.target_date = md.target_date
            ORDER BY COALESCE(md.target_date, rd.target_date)
        """

        result = await session.execute(text(query), params)
        db_rows = [dict(row) for row in result.mappings().all()]

        row_by_date: Dict[str, Dict] = {}
        module_row_counts: List[int] = []

        for row in db_rows:
            target_day = row.get("target_date")
            target_day_text = self._date_to_iso(target_day)

            if target_day_text is None:
                continue

            module_row_count = int(row.get("module_row_count") or 0)
            module_row_counts.append(module_row_count)
            row_by_date[target_day_text] = row

        if expected_row_count_per_day is not None and expected_row_count_per_day > 0:
            effective_expected_row_count = expected_row_count_per_day
            expected_basis = "request.expected_row_count_per_day"
        elif module_row_counts:
            effective_expected_row_count = max(module_row_counts)
            expected_basis = "max_module_row_count_in_range"
        else:
            effective_expected_row_count = None
            expected_basis = "not_available"

        items: List[Dict] = []
        current_date = start_date

        while current_date <= end_date:
            date_text = current_date.isoformat()
            row = row_by_date.get(date_text, {})

            module_row_count = int(row.get("module_row_count") or 0)
            rack_row_count = int(row.get("rack_row_count") or 0)

            completeness_rate = None
            if effective_expected_row_count:
                completeness_rate = round(
                    module_row_count / effective_expected_row_count,
                    4,
                )

            if module_row_count == 0:
                status = "missing"
            elif completeness_rate is None:
                status = "present"
            elif completeness_rate < minimum_completeness_rate:
                status = "insufficient"
            else:
                status = "complete"

            items.append(
                {
                    "date": date_text,
                    "status": status,
                    "module": {
                        "row_count": module_row_count,
                        "expected_row_count": effective_expected_row_count,
                        "completeness_rate": completeness_rate,
                        "bms_count": int(row.get("bms_count") or 0),
                        "rack_count": int(row.get("rack_count") or 0),
                        "module_count": int(row.get("module_count") or 0),
                        "measured_time_count": int(row.get("measured_time_count") or 0),
                        "first_datetime": self._datetime_to_iso(row.get("first_datetime")),
                        "last_datetime": self._datetime_to_iso(row.get("last_datetime")),
                        "cell_voltage_null_row_count": int(
                            row.get("cell_voltage_null_row_count") or 0
                        ),
                        "temperature_null_row_count": int(
                            row.get("temperature_null_row_count") or 0
                        ),
                    },
                    "rack": {
                        "row_count": rack_row_count,
                        "bms_count": int(row.get("rack_bms_count") or 0),
                        "device_count": int(row.get("rack_device_count") or 0),
                        "measured_time_count": int(
                            row.get("rack_measured_time_count") or 0
                        ),
                        "main_value_null_row_count": int(
                            row.get("rack_main_value_null_row_count") or 0
                        ),
                    },
                }
            )

            current_date = current_date + timedelta(days=1)

        total_days = len(items)
        complete_count = sum(1 for item in items if item.get("status") == "complete")
        insufficient_count = sum(
            1 for item in items if item.get("status") == "insufficient"
        )
        missing_count = sum(1 for item in items if item.get("status") == "missing")
        present_count = sum(1 for item in items if item.get("status") == "present")

        if missing_count > 0 or insufficient_count > 0:
            overall_status = "warning"
        elif complete_count > 0 or present_count > 0:
            overall_status = "success"
        else:
            overall_status = "empty"

        return {
            "status": overall_status,
            "filters": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "site_no": site_no,
                "bms_id": bms_id,
            },
            "quality_rule": {
                "expected_row_count_per_day": effective_expected_row_count,
                "expected_basis": expected_basis,
                "minimum_completeness_rate": minimum_completeness_rate,
                "date_basis": "tb_emc_mdul_mntly_rcd.srvr_rcd_dt",
            },
            "summary": {
                "total_days": total_days,
                "complete_count": complete_count,
                "present_count": present_count,
                "insufficient_count": insufficient_count,
                "missing_count": missing_count,
            },
            "results": items,
        }

    def _build_data_quality_where(
        self,
        alias: str,
        site_no: Optional[int],
        bms_id: Optional[str],
    ) -> str:
        """데이터 품질 조회용 WHERE 조건 생성"""

        conditions = [
            f"{alias}.srvr_rcd_dt >= :start_datetime",
            f"{alias}.srvr_rcd_dt < :end_datetime",
        ]

        if site_no is not None:
            conditions.append(f"{alias}.site_no = :site_no")

        if bms_id is not None:
            conditions.append(f"{alias}.bms_id = :bms_id")

        return "\n                  AND ".join(conditions)

    def _date_to_iso(self, value) -> Optional[str]:
        """date/datetime/문자열 값을 YYYY-MM-DD 문자열로 변환"""

        if value is None:
            return None

        if isinstance(value, datetime):
            return value.date().isoformat()

        if isinstance(value, date):
            return value.isoformat()

        text = str(value).strip()
        if not text:
            return None

        return text[:10]

    def _datetime_to_iso(self, value) -> Optional[str]:
        """datetime/date/문자열 값을 ISO 문자열로 변환"""

        if value is None:
            return None

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, date):
            return value.isoformat()

        text = str(value).strip()
        if not text:
            return None

        return text

    def _build_data_range_where(
        self,
        alias: str,
        site_no: Optional[int],
        bms_id: Optional[str],
    ) -> str:
        """데이터 보유 기간 조회용 WHERE 조건 생성"""

        conditions = ["1 = 1"]

        if site_no is not None:
            conditions.append(f"{alias}.site_no = :site_no")

        if bms_id is not None:
            conditions.append(f"{alias}.bms_id = :bms_id")

        return "\n                    AND ".join(conditions)
