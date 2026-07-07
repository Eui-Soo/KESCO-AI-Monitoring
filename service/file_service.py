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
from typing import Any, List, Optional

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
