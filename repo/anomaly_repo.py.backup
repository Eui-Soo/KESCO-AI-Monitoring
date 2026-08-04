"""AI 결과 데이터 Repository

이 파일은 anomaly_score 테이블의 저장/조회 로직을 담당한다.

결과 규격:
    - Serial Number
    - Date Time
    - Prediction Time
    - Bank / Rack / String / Module Number
    - Cell 1~20 Score
    - Cell 1~20 Level
    - Max Score
    - Max Level
    - Average Score

점수 범위:
    - 0.00 ~ 1.00

등급 기준:
    - Normal  : 0.00 이상 0.50 미만
    - Caution : 0.50 이상 0.70 미만
    - Warning : 0.70 이상 0.85 미만
    - Danger  : 0.85 이상 1.00 이하
"""

from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.model.models import AnomalyScore


class AnomalyScoreRepository:
    """anomaly_score 테이블 WRITE / READ 전담 Repository"""

    async def bulk_insert(
        self,
        session: AsyncSession,
        scores: List[dict],
    ) -> int:
        """AI 결과 데이터를 일괄 저장한다.

        Args:
            session:
                SQLAlchemy AsyncSession

            scores:
                AI 결과 목록

                새 규격 예:
                [
                    {
                        "pipeline_run_id": 1,
                        "site_no": 1,
                        "bms_id": "BMS001",
                        "serial_number": "210531-K0001",
                        "sensing_datetime": datetime(...),
                        "prediction_time": datetime(...),
                        "bank_no": 1,
                        "rack_no": 2,
                        "string_no": 3,
                        "module_no": 4,
                        "cell_1_score": 0.66,
                        ...
                        "cell_20_score": 0.85
                    }
                ]

                기존 임시 AI 코드 호환:
                    sc_c1 ~ sc_c20 이 들어와도
                    cell_1_score ~ cell_20_score로 변환해서 저장한다.

        Returns:
            저장한 row 개수
        """

        if not scores:
            return 0

        now = datetime.now()
        rows: List[AnomalyScore] = []

        for item in scores:
            prediction_time = self._to_datetime(
                item.get("prediction_time"),
                default=now,
            )

            sensing_datetime = self._to_datetime(
                item.get("sensing_datetime")
                or item.get("date_time")
                or item.get("datetime")
                or item.get("measured_at"),
                default=prediction_time,
            )

            target_date = self._to_date(
                item.get("target_date")
                or item.get("date")
                or sensing_datetime.date(),
                default=sensing_datetime.date(),
            )

            site_no = self._to_int(item.get("site_no"), default=0)

            serial_number = self._to_str(
                item.get("serial_number")
                or item.get("serial_no")
                or item.get("ess_serial_number")
                or item.get("bms_id")
                or item.get("dvc_id"),
                default="UNKNOWN",
            )

            bms_id = self._to_str(
                item.get("bms_id")
                or item.get("dvc_id")
                or serial_number,
                default="UNKNOWN",
            )

            cell_scores: Dict[int, float] = {}

            for cell_idx in range(1, 21):
                raw_score = (
                    item.get(f"cell_{cell_idx}_score")
                    if item.get(f"cell_{cell_idx}_score") is not None
                    else item.get(f"sc_c{cell_idx}")
                )

                cell_scores[cell_idx] = self._normalize_score(raw_score)

            max_score = max(cell_scores.values()) if cell_scores else 0.0
            average_score = (
                round(sum(cell_scores.values()) / len(cell_scores), 2)
                if cell_scores
                else 0.0
            )

            row = AnomalyScore(
                # 내부 관리용
                pipeline_run_id=item.get("pipeline_run_id"),
                site_no=site_no,
                bms_id=bms_id,
                target_date=target_date,

                # 관제 시스템 전달용
                serial_number=serial_number,
                sensing_datetime=sensing_datetime,
                prediction_time=prediction_time,

                bank_no=self._to_int(
                    item.get("bank_no")
                    or item.get("bank_number"),
                    default=0,
                ),
                rack_no=self._to_int(
                    item.get("rack_no")
                    or item.get("rack_number")
                    or item.get("rack_idx")
                    or item.get("index"),
                    default=0,
                ),
                string_no=self._to_int(
                    item.get("string_no")
                    or item.get("string_number"),
                    default=0,
                ),
                module_no=self._to_int(
                    item.get("module_no")
                    or item.get("module_number"),
                    default=0,
                ),

                cell_1_score=cell_scores[1],
                cell_2_score=cell_scores[2],
                cell_3_score=cell_scores[3],
                cell_4_score=cell_scores[4],
                cell_5_score=cell_scores[5],
                cell_6_score=cell_scores[6],
                cell_7_score=cell_scores[7],
                cell_8_score=cell_scores[8],
                cell_9_score=cell_scores[9],
                cell_10_score=cell_scores[10],
                cell_11_score=cell_scores[11],
                cell_12_score=cell_scores[12],
                cell_13_score=cell_scores[13],
                cell_14_score=cell_scores[14],
                cell_15_score=cell_scores[15],
                cell_16_score=cell_scores[16],
                cell_17_score=cell_scores[17],
                cell_18_score=cell_scores[18],
                cell_19_score=cell_scores[19],
                cell_20_score=cell_scores[20],

                cell_1_level=self._get_level(cell_scores[1]),
                cell_2_level=self._get_level(cell_scores[2]),
                cell_3_level=self._get_level(cell_scores[3]),
                cell_4_level=self._get_level(cell_scores[4]),
                cell_5_level=self._get_level(cell_scores[5]),
                cell_6_level=self._get_level(cell_scores[6]),
                cell_7_level=self._get_level(cell_scores[7]),
                cell_8_level=self._get_level(cell_scores[8]),
                cell_9_level=self._get_level(cell_scores[9]),
                cell_10_level=self._get_level(cell_scores[10]),
                cell_11_level=self._get_level(cell_scores[11]),
                cell_12_level=self._get_level(cell_scores[12]),
                cell_13_level=self._get_level(cell_scores[13]),
                cell_14_level=self._get_level(cell_scores[14]),
                cell_15_level=self._get_level(cell_scores[15]),
                cell_16_level=self._get_level(cell_scores[16]),
                cell_17_level=self._get_level(cell_scores[17]),
                cell_18_level=self._get_level(cell_scores[18]),
                cell_19_level=self._get_level(cell_scores[19]),
                cell_20_level=self._get_level(cell_scores[20]),

                max_score=max_score,
                max_level=self._get_level(max_score),
                average_score=average_score,
            )

            rows.append(row)

        session.add_all(rows)

        return len(rows)

    async def find_latest(
        self,
        session: AsyncSession,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> List[Dict]:
        """가장 최근에 저장된 AI 결과 데이터를 조회한다."""

        latest_row = await self._find_latest_row(
            session=session,
            site_no=site_no,
            bms_id=bms_id,
            target_date=None,
        )

        if latest_row is None:
            return []

        stmt = select(AnomalyScore)

        if site_no is not None:
            stmt = stmt.where(AnomalyScore.site_no == site_no)

        if bms_id is not None:
            stmt = stmt.where(AnomalyScore.bms_id == bms_id)

        if latest_row.pipeline_run_id is not None:
            stmt = stmt.where(AnomalyScore.pipeline_run_id == latest_row.pipeline_run_id)
        else:
            stmt = stmt.where(AnomalyScore.prediction_time == latest_row.prediction_time)

        stmt = stmt.order_by(
            AnomalyScore.serial_number,
            AnomalyScore.bank_no,
            AnomalyScore.rack_no,
            AnomalyScore.string_no,
            AnomalyScore.module_no,
            AnomalyScore.sensing_datetime,
        )

        result = await session.execute(stmt)
        rows = result.scalars().all()

        return [self._to_api_dict(row) for row in rows]

    async def find_latest_by_date(
        self,
        session: AsyncSession,
        target_date,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> List[Dict]:
        """특정 날짜의 가장 최근 AI 결과 데이터를 조회한다."""

        latest_row = await self._find_latest_row(
            session=session,
            site_no=site_no,
            bms_id=bms_id,
            target_date=target_date,
        )

        if latest_row is None:
            return []

        stmt = select(AnomalyScore).where(AnomalyScore.target_date == target_date)

        if site_no is not None:
            stmt = stmt.where(AnomalyScore.site_no == site_no)

        if bms_id is not None:
            stmt = stmt.where(AnomalyScore.bms_id == bms_id)

        if latest_row.pipeline_run_id is not None:
            stmt = stmt.where(AnomalyScore.pipeline_run_id == latest_row.pipeline_run_id)
        else:
            stmt = stmt.where(AnomalyScore.prediction_time == latest_row.prediction_time)

        stmt = stmt.order_by(
            AnomalyScore.serial_number,
            AnomalyScore.bank_no,
            AnomalyScore.rack_no,
            AnomalyScore.string_no,
            AnomalyScore.module_no,
            AnomalyScore.sensing_datetime,
        )

        result = await session.execute(stmt)
        rows = result.scalars().all()

        return [self._to_api_dict(row) for row in rows]

    async def _find_latest_row(
        self,
        session: AsyncSession,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
        target_date=None,
    ) -> Optional[AnomalyScore]:
        """조건에 맞는 가장 최근 AnomalyScore row 1개를 찾는다."""

        stmt = select(AnomalyScore)

        if target_date is not None:
            stmt = stmt.where(AnomalyScore.target_date == target_date)

        if site_no is not None:
            stmt = stmt.where(AnomalyScore.site_no == site_no)

        if bms_id is not None:
            stmt = stmt.where(AnomalyScore.bms_id == bms_id)

        stmt = (
            stmt
            .order_by(desc(AnomalyScore.prediction_time), desc(AnomalyScore.id))
            .limit(1)
        )

        result = await session.execute(stmt)

        return result.scalar_one_or_none()

    def _to_api_dict(self, row: AnomalyScore) -> Dict:
        """AnomalyScore ORM 객체를 API 응답용 dict로 변환한다."""

        result = {
            "id": row.id,

            # 내부 관리용
            "pipeline_run_id": row.pipeline_run_id,
            "site_no": row.site_no,
            "bms_id": row.bms_id,
            "target_date": row.target_date.isoformat() if row.target_date else None,

            # 관제 시스템 전달 규격
            "serial_number": row.serial_number,
            "date_time": row.sensing_datetime.isoformat() if row.sensing_datetime else None,
            "sensing_datetime": row.sensing_datetime.isoformat() if row.sensing_datetime else None,
            "prediction_time": row.prediction_time.isoformat() if row.prediction_time else None,

            "bank_no": row.bank_no,
            "rack_no": row.rack_no,
            "string_no": row.string_no,
            "module_no": row.module_no,

            "max_score": self._round_score(row.max_score),
            "max_level": row.max_level,
            "average_score": self._round_score(row.average_score),

            "inserted": row.inserted.isoformat() if row.inserted else None,
            "updated": row.updated.isoformat() if row.updated else None,
        }

        for cell_idx in range(1, 21):
            result[f"cell_{cell_idx}_score"] = self._round_score(
                getattr(row, f"cell_{cell_idx}_score")
            )
            result[f"cell_{cell_idx}_level"] = getattr(row, f"cell_{cell_idx}_level")

        # 기존 프론트/API 호환용
        result["rack_idx"] = row.rack_no

        return result

    def _get_level(self, score: float) -> str:
        """점수를 등급 문자열로 변환한다."""

        score = self._normalize_score(score)

        if score < 0.50:
            return "Normal"

        if score < 0.70:
            return "Caution"

        if score < 0.85:
            return "Warning"

        return "Danger"

    def _normalize_score(self, value) -> float:
        """0.00~1.00 범위의 소수 2자리 점수로 변환한다."""

        if value is None:
            return 0.0

        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0

        # 혹시 0~100 점수로 들어오면 0~1로 변환
        if score > 1:
            score = score / 100.0

        if score < 0:
            score = 0.0

        if score > 1:
            score = 1.0

        return round(score, 2)

    def _round_score(self, value) -> float:
        """응답용 점수 반올림"""

        return self._normalize_score(value)

    def _to_str(self, value, default: str = "") -> str:
        """값을 문자열로 변환한다."""

        if value is None:
            return default

        text = str(value).strip()

        if not text:
            return default

        return text

    def _to_int(self, value, default: int = 0) -> int:
        """값을 int로 변환한다."""

        if value is None:
            return default

        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _to_datetime(self, value, default: datetime) -> datetime:
        """값을 datetime으로 변환한다."""

        if value is None:
            return default

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return default

        return default

    def _to_date(self, value, default: date) -> date:
        """값을 date로 변환한다."""

        if value is None:
            return default

        if isinstance(value, date) and not isinstance(value, datetime):
            return value

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return default

        return default
