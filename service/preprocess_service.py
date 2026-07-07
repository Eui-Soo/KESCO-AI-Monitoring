"""전처리 서비스.

역할:
- 관제 DB에서 조회한 하루치 row 목록을 모듈 단위로 나눈다.
- 각 모듈 데이터를 5분 간격 288포인트로 맞춘다.
- Cell 전압 컬럼을 cel_volt_01 ~ cel_volt_20 형태로 정리한다.

주의:
- 여기서는 AI 모델 추론을 하지 않는다.
- AI 실행 여부 판단과 모델 추론은 다음 단계에서 붙인다.
"""

import logging
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


logger = logging.getLogger("app")


class PreprocessService:
    """관제 DB raw row를 AI 입력 전 단계 데이터로 변환하는 서비스."""

    CELL_COUNT = 20
    RESAMPLE_RULE = "5min"

    def run(
        self,
        data: List[dict],
        target_date: date,
    ) -> List[dict]:
        """하루치 raw 데이터를 전처리한다.

        Args:
            data: DB에서 조회한 raw row 목록
            target_date: 처리 대상 날짜

        Returns:
            전처리된 row 목록.
            모듈 1개당 하루 288 row가 생성되는 것을 목표로 한다.
        """
        if not data:
            logger.info("전처리 입력 데이터 없음")
            return []

        module_groups = self._group_by_module(data=data, target_date=target_date)
        result: List[dict] = []

        for key, rows in module_groups.items():
            try:
                preprocessed = self._preprocess_one_module(
                    rows=rows,
                    target_date=target_date,
                )
            except Exception as exc:
                logger.exception(f"모듈 전처리 실패 [key={key}, error={exc}]")
                continue

            result.extend(preprocessed)

        logger.info(
            f"전처리 완료 [input_rows={len(data)}, output_rows={len(result)}, "
            f"module_count={len(module_groups)}]"
        )

        return result

    def _group_by_module(
        self,
        data: List[dict],
        target_date: date,
    ) -> Dict[Tuple, List[dict]]:
        """raw row를 site/bms/rack/module 단위로 묶는다."""
        groups: Dict[Tuple, List[dict]] = {}

        for row in data:
            site_no = row.get("site_no")
            bms_id = row.get("bms_id")
            bank_no = self._to_int(row.get("bank_no"), default=0)
            rack_no = self._to_int(row.get("rack_no", row.get("rack_idx")), default=0)
            string_no = self._to_int(row.get("string_no"), default=0)
            module_no = self._to_int(row.get("module_no", row.get("index")), default=0)

            key = (
                site_no,
                bms_id,
                bank_no,
                rack_no,
                string_no,
                module_no,
                target_date.isoformat(),
            )

            groups.setdefault(key, []).append(row)

        return groups

    def _preprocess_one_module(
        self,
        rows: List[dict],
        target_date: date,
    ) -> List[dict]:
        """모듈 하나의 하루치 데이터를 5분 간격으로 전처리한다."""
        if not rows:
            return []

        first = rows[0]

        meta = {
            "site_no": first.get("site_no"),
            "bms_id": first.get("bms_id"),
            "serial_number": first.get("serial_number") or first.get("bms_id"),
            "target_date": target_date.isoformat(),
            "bank_no": self._to_int(first.get("bank_no"), default=0),
            "rack_no": self._to_int(first.get("rack_no", first.get("rack_idx")), default=0),
            "string_no": self._to_int(first.get("string_no"), default=0),
            "module_no": self._to_int(first.get("module_no", first.get("index")), default=0),
        }

        df = self._rows_to_dataframe(rows)

        if df.empty:
            return []

        df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")
        df = df.dropna(subset=["Datetime"]).sort_values("Datetime")
        df = df.drop_duplicates(subset=["Datetime"], keep="last")

        if df.empty:
            return []

        volt_cols = [f"cel_volt_{i:02d}" for i in range(1, self.CELL_COUNT + 1)]

        for col in volt_cols:
            if col not in df.columns:
                df[col] = np.nan
            df[col] = pd.to_numeric(df[col], errors="coerce")

        start_dt = datetime.combine(target_date, time(0, 0, 0))
        end_dt = start_dt + timedelta(days=1)

        full_index = pd.date_range(
            start=start_dt,
            end=end_dt - timedelta(minutes=5),
            freq=self.RESAMPLE_RULE,
        )

        df = df.set_index("Datetime")
        df = df[(df.index >= start_dt) & (df.index < end_dt)]

        if df.empty:
            return []

        df_5min = df[volt_cols].resample(self.RESAMPLE_RULE).mean()
        df_5min = df_5min.reindex(full_index)

        row_all_zero = (df_5min[volt_cols] == 0).all(axis=1)
        df_5min.loc[row_all_zero, volt_cols] = np.nan

        df_5min[volt_cols] = df_5min[volt_cols].interpolate(method="time")
        df_5min[volt_cols] = df_5min[volt_cols].ffill().bfill()

        if df_5min[volt_cols].isna().all().all():
            return []

        df_5min = df_5min.reset_index().rename(columns={"index": "Datetime"})

        output_rows: List[dict] = []

        for _, item in df_5min.iterrows():
            out = dict(meta)
            out["sensing_datetime"] = item["Datetime"].to_pydatetime()

            for cell_no in range(1, self.CELL_COUNT + 1):
                col = f"cel_volt_{cell_no:02d}"
                out[col] = self._to_float(item[col])

            output_rows.append(out)

        return output_rows

    def _rows_to_dataframe(self, rows: List[dict]) -> pd.DataFrame:
        """raw row 목록에서 Datetime/cel_volt 컬럼만 추출한다."""
        normalized_rows: List[dict] = []

        for row in rows:
            normalized = {
                "Datetime": self._pick_datetime(row),
            }

            for cell_no in range(1, self.CELL_COUNT + 1):
                normalized[f"cel_volt_{cell_no:02d}"] = self._pick_cell_voltage(
                    row=row,
                    cell_no=cell_no,
                )

            normalized_rows.append(normalized)

        return pd.DataFrame(normalized_rows)

    def _pick_datetime(self, row: dict):
        """row에서 시간 컬럼을 찾는다."""
        candidates = [
            "sensing_datetime",
            "date_time",
            "measured_at",
            "dvc_rcd_dt",
            "srvr_rcd_dt",
            "Datetime",
            "datetime",
            "time",
            "date",
        ]

        for key in candidates:
            value = row.get(key)
            if value is not None:
                return value

        return None

    def _pick_cell_voltage(
        self,
        row: dict,
        cell_no: int,
    ):
        """row에서 cell 전압 값을 찾는다."""
        candidates = [
            f"cv_{cell_no}",
            f"cell_{cell_no}_voltage",
            f"cell_{cell_no}_v",
            f"cell{cell_no}_v",
            f"cll_{cell_no}_vltg",
            f"cel_volt_{cell_no:02d}",
            f"cel_volt_{cell_no}",
        ]

        for key in candidates:
            value = row.get(key)
            if value is not None:
                return value

        return np.nan

    def _to_int(
        self,
        value,
        default: int = 0,
    ) -> int:
        try:
            if value is None:
                return default
            return int(value)
        except Exception:
            return default

    def _to_float(
        self,
        value,
        default: Optional[float] = None,
    ) -> Optional[float]:
        try:
            if value is None:
                return default

            if pd.isna(value):
                return default

            return float(value)
        except Exception:
            return default
