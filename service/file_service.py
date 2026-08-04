"""파일 저장 서비스.

역할:
- raw 원본 하루치 저장
- preprocess 전처리 하루치 저장
- result AI 결과 저장
- 오래된 raw/preprocess 파일 정리

저장 구조:
    files/
    ├─ raw/{ess_id}/{YYYY-MM-DD}/battery_raw.parquet
    ├─ preprocess/{ess_id}/{YYYY-MM-DD}/battery_preprocessed.parquet
    └─ result/{ess_id}/{YYYY-MM-DD}/anomaly_scores.parquet
"""

import json
import logging
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from core.setting import Settings


logger = logging.getLogger("app")


class FileService:
    """raw / preprocess / result 파일 저장 담당 서비스."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._root_dir = settings.files_dir_path
        self._root_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"FileService 초기화 완료: {self._root_dir}")

    def save_raw(
        self,
        data: List[dict],
        target_date: date,
        ess_id: Optional[str] = None,
    ) -> str:
        """관제 DB에서 가져온 원본 하루치 데이터를 저장한다."""
        return self._save_parquet(
            data=data,
            data_type="raw",
            target_date=target_date,
            file_name="battery_raw.parquet",
            ess_id=ess_id,
        )

    def save_preprocessed(
        self,
        data: List[dict],
        target_date: date,
        ess_id: Optional[str] = None,
    ) -> str:
        """전처리된 하루치 데이터를 files/preprocess 아래에 저장한다."""
        return self._save_parquet(
            data=data,
            data_type="preprocess",
            target_date=target_date,
            file_name="battery_preprocessed.parquet",
            ess_id=ess_id,
        )

    def save_result(
        self,
        data: List[dict],
        target_date: date,
        ess_id: Optional[str] = None,
    ) -> str:
        """AI 결과 데이터를 저장한다.

        schedule_service.py에서 data=... 형태로 호출하므로
        파라미터 이름은 반드시 data로 유지한다.
        """
        return self._save_parquet(
            data=data,
            data_type="result",
            target_date=target_date,
            file_name="anomaly_scores.parquet",
            ess_id=ess_id,
        )

    def save(
        self,
        data: List[dict],
        target_date: date,
        ess_id: Optional[str] = None,
    ) -> str:
        """기존 코드 호환용. 기본 저장은 raw 저장으로 처리한다."""
        return self.save_raw(data=data, target_date=target_date, ess_id=ess_id)

    def cleanup_old_raw(self, reference_date: Optional[date] = None) -> int:
        retention_days = self._settings.RAW_RETENTION_DAYS

        return self._cleanup_old_date_dirs(
            data_type="raw",
            retention_days=retention_days,
            reference_date=reference_date,
        )

    def cleanup_old_preprocess(self, reference_date: Optional[date] = None) -> int:
        retention_days = self._settings.ROLLING_PREPROCESS_DAYS

        return self._cleanup_old_date_dirs(
            data_type="preprocess",
            retention_days=retention_days,
            reference_date=reference_date,
        )
        
    def cleanup_old_preprocessed(self, reference_date: Optional[date] = None) -> int:
        return self.cleanup_old_preprocess(reference_date=reference_date)

    def count_preprocess_days(self, ess_id: Optional[str] = None) -> int:
        """해당 ess_id에 전처리 날짜 폴더가 며칠치 있는지 센다."""
        safe_ess_id = self._safe_name(ess_id or self._settings.DEFAULT_ESS_ID)
        preprocess_dir = self._root_dir / "preprocess" / safe_ess_id

        if not preprocess_dir.exists():
            return 0

        count = 0
        for date_dir in preprocess_dir.iterdir():
            if not date_dir.is_dir():
                continue

            try:
                datetime.strptime(date_dir.name, "%Y-%m-%d").date()
            except ValueError:
                continue

            count += 1

        return count

    def list_preprocessed_dates(
        self,
        ess_id: Optional[str] = None,
        end_date: Optional[date] = None,
    ) -> List[date]:
        """전처리 파일이 존재하는 날짜 목록을 반환한다.

        기준:
        - ess_id별 preprocess 폴더를 확인한다.
        - 실제 battery_preprocessed.parquet 파일이 있는 날짜만 인정한다.
        - end_date가 있으면 end_date 이하 날짜만 반환한다.
        - 날짜가 연속될 필요는 없다.

        사용 목적:
        AI 실행 조건을 "연속 7일"이 아니라
        "대상일 기준 이전 누적 7일"로 판단하기 위해 사용한다.
        """

        safe_ess_id = self._safe_name(ess_id or self._settings.DEFAULT_ESS_ID)
        preprocess_dir = self._root_dir / "preprocess" / safe_ess_id

        if not preprocess_dir.exists():
            return []

        dates: List[date] = []

        for date_dir in preprocess_dir.iterdir():
            if not date_dir.is_dir():
                continue

            try:
                folder_date = datetime.strptime(date_dir.name, "%Y-%m-%d").date()
            except ValueError:
                continue

            if end_date is not None and folder_date > end_date:
                continue

            file_path = date_dir / "battery_preprocessed.parquet"

            if not file_path.exists():
                continue

            dates.append(folder_date)

        return sorted(dates)

    def get_preprocess_file_path(
        self,
        target_date: date,
        ess_id: Optional[str] = None,
    ) -> Path:
        """전처리 parquet 파일 경로를 반환한다."""
        safe_ess_id = self._safe_name(ess_id or self._settings.DEFAULT_ESS_ID)
        return (
            self._root_dir
            / "preprocess"
            / safe_ess_id
            / target_date.isoformat()
            / "battery_preprocessed.parquet"
        )

    def read_preprocessed(
        self,
        target_date: date,
        ess_id: Optional[str] = None,
    ) -> List[dict]:
        """저장된 전처리 parquet 파일을 읽어서 dict 목록으로 반환한다."""
        file_path = self.get_preprocess_file_path(
            target_date=target_date,
            ess_id=ess_id,
        )

        if not file_path.exists():
            return []

        df = pd.read_parquet(file_path)
        return df.to_dict(orient="records")

    def get_raw_file_path(
        self,
        target_date: date,
        ess_id: Optional[str] = None,
    ) -> Path:
        """raw parquet 파일 경로를 반환한다."""

        return self._get_parquet_file_path(
            data_type="raw",
            target_date=target_date,
            file_name="battery_raw.parquet",
            ess_id=ess_id,
        )

    def get_result_file_path(
        self,
        target_date: date,
        ess_id: Optional[str] = None,
    ) -> Path:
        """result parquet 파일 경로를 반환한다."""

        return self._get_parquet_file_path(
            data_type="result",
            target_date=target_date,
            file_name="anomaly_scores.parquet",
            ess_id=ess_id,
        )

    def inspect_pipeline_files(
        self,
        target_date: date,
        ess_id: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """특정 날짜의 raw/preprocess/result 파일 상태를 점검한다.

        반환값은 정합성 검사 API에서 사용한다.
        각 파일에 대해 존재 여부, 파일 경로, metadata.json 여부, row_count를 반환한다.
        row_count는 metadata.json을 우선 사용하고, 없으면 parquet 파일을 직접 읽어 계산한다.
        """

        return {
            "raw": self._inspect_parquet_file(
                data_type="raw",
                target_date=target_date,
                file_name="battery_raw.parquet",
                ess_id=ess_id,
            ),
            "preprocess": self._inspect_parquet_file(
                data_type="preprocess",
                target_date=target_date,
                file_name="battery_preprocessed.parquet",
                ess_id=ess_id,
            ),
            "result": self._inspect_parquet_file(
                data_type="result",
                target_date=target_date,
                file_name="anomaly_scores.parquet",
                ess_id=ess_id,
            ),
        }

    def _get_parquet_file_path(
        self,
        data_type: str,
        target_date: date,
        file_name: str,
        ess_id: Optional[str] = None,
    ) -> Path:
        """공통 parquet 파일 경로를 반환한다."""

        safe_ess_id = self._safe_name(ess_id or self._settings.DEFAULT_ESS_ID)

        return (
            self._root_dir
            / data_type
            / safe_ess_id
            / target_date.isoformat()
            / file_name
        )

    def _inspect_parquet_file(
        self,
        data_type: str,
        target_date: date,
        file_name: str,
        ess_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """parquet 파일과 metadata.json 상태를 확인한다."""

        file_path = self._get_parquet_file_path(
            data_type=data_type,
            target_date=target_date,
            file_name=file_name,
            ess_id=ess_id,
        )
        metadata_path = file_path.parent / "metadata.json"

        metadata: Optional[Dict[str, Any]] = None
        metadata_error: Optional[str] = None
        read_error: Optional[str] = None
        row_count: Optional[int] = None

        if metadata_path.exists():
            try:
                with metadata_path.open("r", encoding="utf-8") as f:
                    metadata = json.load(f)

                if metadata.get("row_count") is not None:
                    row_count = int(metadata.get("row_count"))

            except Exception as exc:
                metadata_error = str(exc)

        if file_path.exists() and row_count is None:
            try:
                row_count = int(pd.read_parquet(file_path).shape[0])
            except Exception as exc:
                read_error = str(exc)

        return {
            "exists": file_path.exists(),
            "path": str(file_path),
            "row_count": row_count,
            "metadata_exists": metadata_path.exists(),
            "metadata_path": str(metadata_path),
            "metadata": metadata,
            "metadata_error": metadata_error,
            "read_error": read_error,
        }

    def _save_parquet(
        self,
        data: List[dict],
        data_type: str,
        target_date: date,
        file_name: str,
        ess_id: Optional[str] = None,
    ) -> str:
        """공통 parquet 저장 함수."""
        safe_ess_id = self._safe_name(ess_id or self._settings.DEFAULT_ESS_ID)
        date_text = target_date.isoformat()

        save_dir = self._root_dir / data_type / safe_ess_id / date_text
        save_dir.mkdir(parents=True, exist_ok=True)

        file_path = save_dir / file_name

        df = pd.DataFrame(data)
        df.to_parquet(file_path, index=False)

        metadata = {
            "ess_id": safe_ess_id,
            "target_date": date_text,
            "data_type": data_type,
            "file_name": file_name,
            "file_path": str(file_path),
            "row_count": len(data),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

        metadata_path = save_dir / "metadata.json"
        with metadata_path.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(
            f"Parquet 저장 완료 "
            f"[type={data_type}, ess_id={safe_ess_id}, date={date_text}, "
            f"rows={len(data)}, path={file_path}]"
        )

        return str(file_path)

    def _cleanup_old_date_dirs(
        self,
        data_type: str,
        retention_days: int,
        reference_date: Optional[date] = None,
    ) -> int:
        if retention_days <= 0:
            logger.info(
                f"{data_type} 자동 삭제 비활성화 "
                f"[retention_days={retention_days}]"
            )
            return 0

        root = self._root_dir / data_type

        if not root.exists():
            logger.info(f"{data_type} 폴더 없음 - 삭제할 데이터 없음")
            return 0

        base_date = reference_date or date.today()
        cutoff_date = base_date - timedelta(days=retention_days)
        deleted_count = 0

        for ess_dir in root.iterdir():
            if not ess_dir.is_dir():
                continue

            for date_dir in ess_dir.iterdir():
                if not date_dir.is_dir():
                    continue

                try:
                    folder_date = datetime.strptime(date_dir.name, "%Y-%m-%d").date()
                except ValueError:
                    logger.warning(f"날짜 형식이 아닌 폴더라 삭제 생략: {date_dir}")
                    continue

                if folder_date < cutoff_date:
                    shutil.rmtree(date_dir)
                    deleted_count += 1
                    logger.info(
                        f"오래된 {data_type} 삭제 완료 "
                        f"[path={date_dir}, folder_date={folder_date}, "
                        f"cutoff={cutoff_date}, reference_date={base_date}]"
                    )

        logger.info(
            f"{data_type} 자동 정리 완료 "
            f"[retention_days={retention_days}, reference_date={base_date}, "
            f"deleted_count={deleted_count}]"
        )

        return deleted_count

    def _safe_name(self, value: Any) -> str:
        """폴더명으로 안전하게 사용할 수 있도록 문자열을 정리한다."""
        text = str(value).strip()

        if not text:
            return self._settings.DEFAULT_ESS_ID

        for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', ' ']:
            text = text.replace(ch, "_")

        return text
