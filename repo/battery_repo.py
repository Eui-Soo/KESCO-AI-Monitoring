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
