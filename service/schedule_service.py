"""AI 파이프라인 스케줄러 서비스.

현재 단계의 흐름:
1. 관제 DB에서 target_date 하루치 raw 데이터 조회
2. files/raw에 저장
3. raw 보관일 초과분 삭제
4. 하루치 전처리 수행
5. files/preprocess에 저장
6. preprocess 날짜 폴더가 7일치 미만이면 AI 실행 대기
7. 7일치 이상이면 현재 AIProcessingService 실행
8. result 저장
9. anomaly_score DB 저장

주의:
- 실제 STGCN 모델 추론은 다음 단계에서 AIProcessingService 쪽에 붙인다.
- 여기서는 rolling 7일 조건을 스케줄 흐름에 먼저 넣는다.
"""
import asyncio
import inspect
import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.setting import Settings
from service.ai_service import AIProcessingService
from service.file_service import FileService
from service.preprocess_service import PreprocessService


logger = logging.getLogger("app")


class SchedulerService:
    """AI 파이프라인 자동/수동 실행 서비스."""

    def __init__(
        self,
        settings: Settings,
        remote_db_service,
        db_local_service,
        file_service: FileService,
        preprocess_service: PreprocessService,
        ai_processing_service: AIProcessingService,
    ):
        self._settings = settings
        self._remote_db_service = remote_db_service
        self._db_local_service = db_local_service
        self._file_service = file_service
        self._preprocess_service = preprocess_service
        self._ai_processing_service = ai_processing_service

        self._scheduler = AsyncIOScheduler()
        self._is_running = False

        # run-range 백그라운드 실행 상태는 우선 메모리에서 관리한다.
        # 서버가 재시작되면 이 상태는 초기화된다.
        # 운영 고도화 단계에서는 별도 DB 테이블로 영속화하는 것을 권장한다.
        self._range_runs: Dict[str, Dict] = {}
        self._range_run_tasks: Dict[str, asyncio.Task] = {}

        logger.info("SchedulerService 초기화 완료")

    def start(self) -> None:
        """스케줄러를 시작한다."""

        if self._scheduler.running:
            logger.warning("스케줄러가 이미 실행 중입니다.")
            return

        self._scheduler.add_job(
            self._process_all_active_targets,
            trigger="cron",
            hour=self._settings.SCHEDULE_HOUR,
            minute=self._settings.SCHEDULE_MINUTE,
            second=self._settings.SCHEDULE_SECOND,
            id="daily_ai_pipeline",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )

        self._scheduler.start()

        logger.info(
            "스케줄러 시작 완료 "
            f"(매일 {self._settings.SCHEDULE_HOUR:02d}:"
            f"{self._settings.SCHEDULE_MINUTE:02d}:"
            f"{self._settings.SCHEDULE_SECOND:02d} 실행)"
        )

    def stop(self) -> None:
        """스케줄러를 종료한다."""

        if not self._scheduler.running:
            logger.info("스케줄러가 실행 중이 아닙니다.")
            return

        self._scheduler.shutdown(wait=False)
        logger.info("스케줄러 종료 완료")

    def start_range_run_background(
        self,
        start_date: date,
        end_date: date,
        site_no: int,
        bms_id: str,
        force: Optional[bool] = None,
    ) -> Dict:
        """기간 분석 작업을 백그라운드로 등록한다.

        기존 POST /api/v1/pipeline/run-range는 요청이 끝날 때까지
        기다리는 동기 실행 방식이다.

        이 함수는 긴 기간 분석에서 Swagger/브라우저 timeout을 피하기 위해
        즉시 range_run_id를 반환하고 실제 분석은 event loop의 task로 실행한다.
        """

        if self._has_active_range_run():
            raise RuntimeError(
                "Another range run is already queued or running. "
                "Wait until the current range run is completed."
            )

        effective_force = (
            self._settings.FORCE_RERUN_DEFAULT
            if force is None
            else force
        )

        if effective_force and not self._settings.FORCE_RERUN_ENABLED:
            raise ValueError(
                "Force rerun is disabled by server setting. "
                "Set FORCE_RERUN_ENABLED=true to allow force=true."
            )

        range_run_id = self._make_range_run_id(
            start_date=start_date,
            end_date=end_date,
            site_no=site_no,
            bms_id=bms_id,
        )

        now_text = datetime.now().isoformat(timespec="seconds")
        total_days = (end_date - start_date).days + 1

        range_run = {
            "range_run_id": range_run_id,
            "status": "queued",
            "message": "Range pipeline job queued.",
            "started_at": now_text,
            "updated_at": now_text,
            "finished_at": None,
            "current_date": None,
            "request": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "site_no": site_no,
                "bms_id": bms_id,
                "force": effective_force,
            },
            "settings": {
                "force_rerun_enabled": self._settings.FORCE_RERUN_ENABLED,
                "force_rerun_default": self._settings.FORCE_RERUN_DEFAULT,
            },
            "summary": {
                "total_days": total_days,
                "completed_days": 0,
                "success_count": 0,
                "waiting_count": 0,
                "empty_count": 0,
                "error_count": 0,
                "skipped_count": 0,
                "skipped_existing_count": 0,
            },
            "results": [],
            "error_message": None,
        }

        self._range_runs[range_run_id] = range_run

        task = asyncio.create_task(
            self._run_range_pipeline_background(
                range_run_id=range_run_id,
                start_date=start_date,
                end_date=end_date,
                site_no=site_no,
                bms_id=bms_id,
                force=effective_force,
            )
        )

        self._range_run_tasks[range_run_id] = task

        logger.info(
            "기간 AI 파이프라인 백그라운드 작업 등록 완료 "
            f"[range_run_id={range_run_id}, start_date={start_date}, "
            f"end_date={end_date}, site_no={site_no}, bms_id={bms_id}, "
            f"force={effective_force}]"
        )

        return range_run

    def get_range_run_status(self, range_run_id: str) -> Optional[Dict]:
        """백그라운드 기간 분석 작업 상태를 조회한다."""

        return self._range_runs.get(range_run_id)

    def get_recent_range_runs(self, limit: int = 20) -> List[Dict]:
        """최근 백그라운드 기간 분석 작업 목록을 조회한다."""

        rows = list(self._range_runs.values())
        rows.sort(key=lambda item: item.get("started_at") or "", reverse=True)

        return rows[:limit]

    async def _run_range_pipeline_background(
        self,
        range_run_id: str,
        start_date: date,
        end_date: date,
        site_no: int,
        bms_id: str,
        force: bool,
    ) -> None:
        """기간 분석 작업을 실제로 수행한다."""

        range_run = self._range_runs[range_run_id]
        range_run["status"] = "running"
        range_run["message"] = "Range pipeline job is running."
        range_run["updated_at"] = datetime.now().isoformat(timespec="seconds")

        current_date = start_date

        try:
            while current_date <= end_date:
                range_run["current_date"] = current_date.isoformat()
                range_run["updated_at"] = datetime.now().isoformat(timespec="seconds")

                day_result = await self._run_range_pipeline_day(
                    current_date=current_date,
                    site_no=site_no,
                    bms_id=bms_id,
                    force=force,
                )

                range_run["results"].append(day_result)
                self._refresh_range_run_summary(range_run)

                current_date = current_date + timedelta(days=1)

                # 긴 작업 중 다른 coroutine이 실행될 수 있게 event loop에 양보한다.
                await asyncio.sleep(0)

            final_status = self._decide_range_run_status(range_run["results"])
            range_run["status"] = final_status
            range_run["message"] = "Range pipeline job completed."
            range_run["current_date"] = None
            range_run["finished_at"] = datetime.now().isoformat(timespec="seconds")
            range_run["updated_at"] = range_run["finished_at"]

            logger.info(
                "기간 AI 파이프라인 백그라운드 작업 완료 "
                f"[range_run_id={range_run_id}, status={final_status}]"
            )

        except Exception as exc:
            error_message = str(exc)

            range_run["status"] = "error"
            range_run["message"] = "Range pipeline job failed."
            range_run["error_message"] = error_message
            range_run["finished_at"] = datetime.now().isoformat(timespec="seconds")
            range_run["updated_at"] = range_run["finished_at"]

            logger.exception(
                "기간 AI 파이프라인 백그라운드 작업 실패 "
                f"[range_run_id={range_run_id}, error={error_message}]"
            )

        finally:
            self._range_run_tasks.pop(range_run_id, None)

    async def _run_range_pipeline_day(
        self,
        current_date: date,
        site_no: int,
        bms_id: str,
        force: bool,
    ) -> Dict:
        """기간 분석 중 하루치 작업을 실행한다."""

        has_completed_result = await self._db_local_service.exists_success_pipeline_result_by_date(
            target_date=current_date,
            site_no=site_no,
            bms_id=bms_id,
        )

        if has_completed_result and not force:
            return {
                "date": current_date.isoformat(),
                "status": "skipped_existing",
                "message": (
                    "Completed AI result already exists for this date/site/bms. "
                    "Use force=true to rerun."
                ),
                "skip_basis": "pipeline_run_log.status=success and saved_score_count>0",
                "run_id": None,
                "battery_count": 0,
                "preprocessed_count": 0,
                "saved_score_count": 0,
                "raw_file_path": None,
                "preprocessed_file_path": None,
                "result_file_path": None,
                "error_message": None,
            }

        result = await self.run_once(
            target_date=current_date,
            site_no=site_no,
            bms_id=bms_id,
        )

        return {
            "date": current_date.isoformat(),
            "status": result.get("status"),
            "message": result.get("message"),
            "run_id": result.get("run_id"),
            "battery_count": result.get("battery_count", 0),
            "preprocessed_count": result.get("preprocessed_count", 0),
            "preprocess_day_count": result.get("preprocess_day_count", 0),
            "saved_score_count": result.get("saved_score_count", 0),
            "loaded_dates": result.get("loaded_dates"),
            "raw_file_path": result.get("raw_file_path"),
            "preprocessed_file_path": result.get("preprocessed_file_path"),
            "result_file_path": result.get("result_file_path"),
            "error_message": result.get("error_message"),
        }

    def _refresh_range_run_summary(self, range_run: Dict) -> None:
        """기간 분석 작업의 진행률/집계 정보를 갱신한다."""

        results = range_run.get("results", [])
        summary = range_run["summary"]

        summary["completed_days"] = len(results)
        summary["success_count"] = sum(
            1 for item in results if item.get("status") == "success"
        )
        summary["waiting_count"] = sum(
            1 for item in results if item.get("status") == "waiting_7days"
        )
        summary["empty_count"] = sum(
            1 for item in results if item.get("status") == "empty"
        )
        summary["error_count"] = sum(
            1 for item in results if item.get("status") == "error"
        )
        summary["skipped_count"] = sum(
            1 for item in results if item.get("status") == "skipped"
        )
        summary["skipped_existing_count"] = sum(
            1 for item in results if item.get("status") == "skipped_existing"
        )

    def _decide_range_run_status(self, results: List[Dict]) -> str:
        """날짜별 실행 결과를 바탕으로 기간 작업 최종 상태를 결정한다."""

        if not results:
            return "empty"

        error_count = sum(1 for item in results if item.get("status") == "error")
        success_count = sum(1 for item in results if item.get("status") == "success")
        waiting_count = sum(1 for item in results if item.get("status") == "waiting_7days")
        empty_count = sum(1 for item in results if item.get("status") == "empty")
        skipped_existing_count = sum(
            1 for item in results if item.get("status") == "skipped_existing"
        )
        skipped_count = sum(1 for item in results if item.get("status") == "skipped")

        if error_count > 0:
            return "partial_error"

        if success_count > 0:
            return "success"

        if waiting_count > 0:
            return "waiting_7days"

        if empty_count > 0:
            return "empty"

        if skipped_existing_count > 0:
            return "skipped_existing"

        if skipped_count > 0:
            return "skipped"

        return "unknown"

    def _has_active_range_run(self) -> bool:
        """현재 실행 중이거나 대기 중인 기간 분석 작업이 있는지 확인한다."""

        for item in self._range_runs.values():
            if item.get("status") in {"queued", "running"}:
                return True

        return False

    def _make_range_run_id(
        self,
        start_date: date,
        end_date: date,
        site_no: int,
        bms_id: str,
    ) -> str:
        """기간 분석 작업 ID를 생성한다."""

        safe_bms_id = self._make_ess_id(site_no=site_no, bms_id=bms_id)
        suffix = uuid.uuid4().hex[:8]

        return (
            f"RANGE_{datetime.now():%Y%m%d_%H%M%S}_"
            f"{start_date.isoformat()}_{end_date.isoformat()}_"
            f"{safe_bms_id}_{suffix}"
        )

    async def run_once(
        self,
        target_date: Optional[date] = None,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> Dict:
        """Swagger/API에서 수동으로 파이프라인을 1회 실행한다."""

        if self._is_running:
            logger.warning("이전 AI 파이프라인이 아직 실행 중입니다.")
            return {
                "status": "skipped",
                "message": "Previous AI pipeline is still running.",
                "site_no": site_no,
                "bms_id": bms_id,
            }

        if target_date is None:
            target_date = self._get_target_date()

        if site_no is not None and bms_id:
            self._is_running = True

            try:
                return await self._run_pipeline(
                    manual=True,
                    target_date=target_date,
                    site_no=site_no,
                    bms_id=bms_id,
                )
            finally:
                self._is_running = False

        return await self._run_all_active_targets(
            manual=True,
            target_date=target_date,
        )

    async def _process_all_active_targets(self) -> None:
        """스케줄러가 매일 호출하는 자동 실행 함수."""

        if self._is_running:
            logger.warning("이전 AI 파이프라인이 아직 실행 중이므로 자동 실행을 건너뜁니다.")
            return

        target_date = self._get_target_date()

        logger.info(
            "일일 AI 파이프라인 자동 실행 시작 "
            f"(target_date={target_date}, "
            f"schedule={self._settings.SCHEDULE_HOUR:02d}:"
            f"{self._settings.SCHEDULE_MINUTE:02d}:"
            f"{self._settings.SCHEDULE_SECOND:02d})"
        )

        await self._run_all_active_targets(
            manual=False,
            target_date=target_date,
        )

    async def _run_all_active_targets(
        self,
        manual: bool,
        target_date: date,
    ) -> Dict:
        """로컬 DB에 등록된 AI 분석 대상을 전체 실행한다.

        실행 순서:
        1. 원격 관제 DB에서 ESS/BMS 목록을 조회한다.
        2. 로컬 DB의 ess_site / ess_device를 동기화한다.
        3. 동기화된 로컬 DB 기준으로 AI 분석 대상을 조회한다.
        4. 각 대상별로 raw 조회 / 전처리 / AI 추론 / 결과 저장을 수행한다.
        """

        self._is_running = True

        try:
            sync_result = await self._sync_sites_before_pipeline()

            if sync_result.get("status") == "error":
                return {
                    "status": "error",
                    "message": "ESS/BMS list sync failed before AI pipeline.",
                    "target_date": target_date.isoformat(),
                    "sync_result": sync_result,
                    "target_count": 0,
                    "results": [],
                }

            targets = await self._db_local_service.find_active_ai_targets()

            if not targets:
                logger.warning("AI 분석 대상 사이트/BMS가 없습니다.")

                return {
                    "status": "empty",
                    "message": (
                        "No active AI targets found after ESS/BMS sync. "
                        "Check remote site/device data or ai_enabled setting."
                    ),
                    "target_date": target_date.isoformat(),
                    "sync_result": sync_result,
                    "target_count": 0,
                    "results": [],
                }

            logger.info(
                "전체 AI 분석 대상 실행 시작 "
                f"(target_date={target_date}, target_count={len(targets)})"
            )

            results: List[Dict] = []

            for target in targets:
                site_no = target.get("site_no")
                bms_id = target.get("bms_id") or target.get("dvc_id")

                if site_no is None or not bms_id:
                    results.append(
                        {
                            "status": "skipped",
                            "message": "Invalid target. site_no or bms_id is missing.",
                            "target": target,
                        }
                    )
                    continue

                result = await self._run_pipeline(
                    manual=manual,
                    target_date=target_date,
                    site_no=int(site_no),
                    bms_id=str(bms_id),
                )

                results.append(result)

            success_count = sum(1 for item in results if item.get("status") == "success")
            waiting_count = sum(1 for item in results if item.get("status") == "waiting_7days")
            empty_count = sum(1 for item in results if item.get("status") == "empty")
            error_count = sum(1 for item in results if item.get("status") == "error")
            skipped_count = sum(1 for item in results if item.get("status") == "skipped")

            overall_status = "success"

            if error_count > 0:
                overall_status = "partial_error"
            elif success_count == 0 and waiting_count > 0:
                overall_status = "waiting_7days"
            elif success_count == 0 and empty_count > 0:
                overall_status = "empty"

            return {
                "status": overall_status,
                "message": "AI pipeline completed for active targets.",
                "target_date": target_date.isoformat(),
                "sync_result": sync_result,
                "target_count": len(targets),
                "success_count": success_count,
                "waiting_count": waiting_count,
                "empty_count": empty_count,
                "error_count": error_count,
                "skipped_count": skipped_count,
                "results": results,
            }

        finally:
            self._is_running = False

    async def _sync_sites_before_pipeline(self) -> Dict:
        """AI 파이프라인 실행 전에 원격 ESS/BMS 목록을 로컬 DB에 동기화한다.

        기존에는 POST /api/v1/sites/sync를 사람이 직접 눌러야 했다.
        이제는 자동 스케줄 실행 전에 매번 원격 ESS/BMS 목록을 확인한다.
        """

        try:
            remote_sites = await self._call_first_existing_method(
                self._remote_db_service,
                [
                    "find_sites",
                    "find_remote_sites",
                    "find_site_devices",
                    "find_sites_and_devices",
                    "find_ess_sites",
                ],
            )

            remote_count = len(remote_sites) if remote_sites else 0

            logger.info(
                "스케줄러 실행 전 원격 ESS/BMS 목록 조회 완료 "
                f"[count={remote_count}]"
            )

            if not remote_sites:
                logger.warning("원격 ESS/BMS 목록이 비어 있습니다.")

                return {
                    "status": "empty",
                    "message": "Remote ESS/BMS list is empty.",
                    "remote_count": 0,
                }

            sync_result = await self._call_first_existing_method(
                self._db_local_service,
                [
                    "sync_sites_and_devices",
                    "sync_remote_sites",
                    "sync_sites",
                    "upsert_sites_and_devices",
                    "upsert_remote_sites",
                    "upsert_sites",
                ],
                remote_sites,
            )

            if sync_result is None:
                sync_result = {}

            if not isinstance(sync_result, dict):
                sync_result = {
                    "raw_result": sync_result,
                }

            sync_result.setdefault("status", "success")
            sync_result.setdefault("remote_count", remote_count)

            logger.info(
                "스케줄러 실행 전 ESS/BMS 목록 자동 동기화 완료 "
                f"[remote_count={remote_count}, "
                f"site_created={sync_result.get('site_created', 0)}, "
                f"site_updated={sync_result.get('site_updated', 0)}, "
                f"device_created={sync_result.get('device_created', 0)}, "
                f"device_updated={sync_result.get('device_updated', 0)}, "
                f"skipped_device={sync_result.get('skipped_device', 0)}]"
            )

            return sync_result

        except Exception as exc:
            error_message = str(exc)

            logger.exception(
                "스케줄러 실행 전 ESS/BMS 목록 자동 동기화 실패 "
                f"[error={error_message}]"
            )

            return {
                "status": "error",
                "message": "ESS/BMS sync failed before AI pipeline.",
                "error_message": error_message,
            }


    async def _call_first_existing_method(
        self,
        owner,
        method_names: List[str],
        *args,
        **kwargs,
    ):
        """객체 안에 존재하는 첫 번째 메서드를 찾아 실행한다.

        이유:
        - site_router.py의 정확한 함수명을 아직 이 파일에서 직접 볼 수 없다.
        - 이미 POST /api/v1/sites/sync가 성공했던 구조를 재사용해야 한다.
        - 그래서 가능한 함수명 후보 중 실제 존재하는 것을 찾아 호출한다.
        """

        last_error: Optional[Exception] = None

        for method_name in method_names:
            method = getattr(owner, method_name, None)

            if method is None:
                continue

            try:
                result = method(*args, **kwargs)

                if inspect.isawaitable(result):
                    result = await result

                return result

            except TypeError as exc:
                last_error = exc
                continue

        owner_name = owner.__class__.__name__

        raise AttributeError(
            f"{owner_name}에서 사용 가능한 메서드를 찾지 못했습니다. "
            f"후보={method_names}, "
            f"last_error={last_error}"
        )

    async def _run_pipeline(
        self,
        manual: bool,
        target_date: date,
        site_no: int,
        bms_id: str,
    ) -> Dict:
        """특정 site_no / bms_id 기준으로 파이프라인을 1회 실행한다."""

        ess_id = self._make_ess_id(site_no=site_no, bms_id=bms_id)

        run_id: Optional[int] = None
        raw_file_path: Optional[str] = None
        preprocessed_file_path: Optional[str] = None
        result_file_path: Optional[str] = None

        battery_count = 0
        preprocessed_count = 0
        saved_score_count = 0
        deleted_raw_count = 0
        deleted_preprocessed_count = 0

        logger.info(
            "AI 파이프라인 실행 시작 "
            f"[manual={manual}, target_date={target_date}, "
            f"site_no={site_no}, bms_id={bms_id}, ess_id={ess_id}]"
        )

        try:
            run_id = await self._db_local_service.create_pipeline_run(
                ess_id=ess_id,
                target_date=target_date,
                site_no=site_no,
                bms_id=bms_id,
                message=(
                    "Manual AI pipeline started."
                    if manual
                    else "Scheduled daily AI pipeline started."
                ),
            )

            battery_data = await self._remote_db_service.find_battery_by_date(
                target_date=target_date,
                site_no=site_no,
                bms_id=bms_id,
            )

            battery_count = len(battery_data)

            if not battery_data:
                await self._db_local_service.mark_pipeline_empty(
                    run_id=run_id,
                    battery_count=0,
                    saved_score_count=0,
                    deleted_preprocessed_count=0,
                    message=(
                        "No battery data found. "
                        f"target_date={target_date}, site_no={site_no}, bms_id={bms_id}"
                    ),
                )

                return {
                    "status": "empty",
                    "message": "No battery data found for target date/site/bms.",
                    "run_id": run_id,
                    "ess_id": ess_id,
                    "site_no": site_no,
                    "bms_id": bms_id,
                    "target_date": target_date.isoformat(),
                    "battery_count": 0,
                    "saved_score_count": 0,
                }

            raw_file_path = self._file_service.save_raw(
                ess_id=ess_id,
                target_date=target_date,
                data=battery_data,
            )

            deleted_raw_count = self._file_service.cleanup_old_raw(
                reference_date=target_date
            )

            preprocessed_data = self._preprocess_service.run(
                data=battery_data,
                target_date=target_date,
            )
            preprocessed_count = len(preprocessed_data)

            if not preprocessed_data:
                await self._db_local_service.mark_pipeline_empty(
                    run_id=run_id,
                    battery_count=battery_count,
                    saved_score_count=0,
                    deleted_preprocessed_count=0,
                    raw_file_path=raw_file_path,
                    message=(
                        "Preprocess result is empty. "
                        f"target_date={target_date}, site_no={site_no}, bms_id={bms_id}"
                    ),
                )

                return {
                    "status": "empty",
                    "message": "Preprocess result is empty.",
                    "run_id": run_id,
                    "ess_id": ess_id,
                    "site_no": site_no,
                    "bms_id": bms_id,
                    "target_date": target_date.isoformat(),
                    "battery_count": battery_count,
                    "preprocessed_count": 0,
                    "saved_score_count": 0,
                    "raw_file_path": raw_file_path,
                }

            preprocessed_file_path = self._file_service.save_preprocessed(
                ess_id=ess_id,
                target_date=target_date,
                data=preprocessed_data,
            )

            deleted_preprocessed_count = self._file_service.cleanup_old_preprocess(
                reference_date=target_date
            )

            available_preprocess_dates = self._file_service.list_preprocessed_dates(
                ess_id=ess_id,
                end_date=target_date,
            )

            preprocess_day_count = len(available_preprocess_dates)

            if preprocess_day_count < self._settings.AI_MIN_PREPROCESS_DAYS:
                message = (
                    "Waiting for enough accumulated preprocess days. "
                    f"current_days={preprocess_day_count}, "
                    f"required_days={self._settings.AI_MIN_PREPROCESS_DAYS}, "
                    f"target_date={target_date}, site_no={site_no}, bms_id={bms_id}"
                )

                await self._db_local_service.mark_pipeline_success(
                    run_id=run_id,
                    battery_count=battery_count,
                    saved_score_count=0,
                    deleted_preprocessed_count=deleted_preprocessed_count,
                    raw_file_path=raw_file_path,
                    preprocessed_file_path=preprocessed_file_path,
                    result_file_path=None,
                    message=message,
                )

                logger.info(
                    "AI 실행 대기 - 누적 전처리 일수 부족 "
                    f"[ess_id={ess_id}, current_days={preprocess_day_count}, "
                    f"required_days={self._settings.AI_MIN_PREPROCESS_DAYS}, "
                    f"available_dates={[d.isoformat() for d in available_preprocess_dates]}]"
                )

                return {
                    "status": "waiting_7days",
                    "message": message,
                    "run_id": run_id,
                    "ess_id": ess_id,
                    "site_no": site_no,
                    "bms_id": bms_id,
                    "target_date": target_date.isoformat(),
                    "battery_count": battery_count,
                    "preprocessed_count": preprocessed_count,
                    "preprocess_day_count": preprocess_day_count,
                    "required_days": self._settings.AI_MIN_PREPROCESS_DAYS,
                    "available_preprocess_dates": [
                        d.isoformat() for d in available_preprocess_dates
                    ],
                    "saved_score_count": 0,
                    "raw_file_path": raw_file_path,
                    "preprocessed_file_path": preprocessed_file_path,
                    "deleted_raw_count": deleted_raw_count,
                    "deleted_preprocessed_count": deleted_preprocessed_count,
                }

            accumulated_preprocessed_data, loaded_dates = (
                self._load_accumulated_preprocessed_data(
                    ess_id=ess_id,
                    target_date=target_date,
                )
            )

            if len(loaded_dates) < self._settings.AI_MIN_PREPROCESS_DAYS:
                message = (
                    "Waiting for complete accumulated preprocess data. "
                    f"loaded_days={len(loaded_dates)}, "
                    f"required_days={self._settings.AI_MIN_PREPROCESS_DAYS}, "
                    f"target_date={target_date}, site_no={site_no}, bms_id={bms_id}"
                )

                await self._db_local_service.mark_pipeline_success(
                    run_id=run_id,
                    battery_count=battery_count,
                    saved_score_count=0,
                    deleted_preprocessed_count=deleted_preprocessed_count,
                    raw_file_path=raw_file_path,
                    preprocessed_file_path=preprocessed_file_path,
                    result_file_path=None,
                    message=message,
                )

                logger.info(message)

                return {
                    "status": "waiting_7days",
                    "message": message,
                    "run_id": run_id,
                    "ess_id": ess_id,
                    "site_no": site_no,
                    "bms_id": bms_id,
                    "target_date": target_date.isoformat(),
                    "battery_count": battery_count,
                    "preprocessed_count": preprocessed_count,
                    "preprocess_day_count": preprocess_day_count,
                    "loaded_dates": loaded_dates,
                    "saved_score_count": 0,
                    "raw_file_path": raw_file_path,
                    "preprocessed_file_path": preprocessed_file_path,
                    "deleted_raw_count": deleted_raw_count,
                    "deleted_preprocessed_count": deleted_preprocessed_count,
                }

            scores = await self._ai_processing_service.run(
                accumulated_preprocessed_data
            )

            if not scores:
                raise RuntimeError(
                    "AI inference produced no score rows. "
                    "Check model files, model loading errors, or input preprocessing data. "
                    f"target_date={target_date}, site_no={site_no}, bms_id={bms_id}"
                )

            scores = self._attach_score_metadata(
                scores=scores,
                pipeline_run_id=run_id,
                site_no=site_no,
                bms_id=bms_id,
                target_date=target_date,
            )

            result_file_path = self._file_service.save_result(
                ess_id=ess_id,
                target_date=target_date,
                data=scores,
            )

            saved_score_count = await self._db_local_service.save_anomaly_scores(scores)

            await self._db_local_service.mark_pipeline_success(
                run_id=run_id,
                battery_count=battery_count,
                saved_score_count=saved_score_count,
                deleted_preprocessed_count=deleted_preprocessed_count,
                raw_file_path=raw_file_path,
                preprocessed_file_path=preprocessed_file_path,
                result_file_path=result_file_path,
                message=(
                    "AI pipeline completed successfully. "
                    f"target_date={target_date}, site_no={site_no}, bms_id={bms_id}"
                ),
            )

            logger.info(
                "AI 파이프라인 성공 "
                f"[run_id={run_id}, ess_id={ess_id}, "
                f"battery_count={battery_count}, "
                f"preprocessed_count={preprocessed_count}, "
                f"saved_score_count={saved_score_count}]"
            )

            return {
                "status": "success",
                "message": "AI pipeline completed successfully.",
                "run_id": run_id,
                "ess_id": ess_id,
                "site_no": site_no,
                "bms_id": bms_id,
                "target_date": target_date.isoformat(),
                "battery_count": battery_count,
                "preprocessed_count": preprocessed_count,
                "preprocess_day_count": preprocess_day_count,
                "saved_score_count": saved_score_count,
                "raw_file_path": raw_file_path,
                "preprocessed_file_path": preprocessed_file_path,
                "result_file_path": result_file_path,
                "deleted_raw_count": deleted_raw_count,
                "deleted_preprocessed_count": deleted_preprocessed_count,
            }

        except Exception as exc:
            error_message = str(exc)

            logger.exception(
                "AI 파이프라인 실패 "
                f"[run_id={run_id}, target_date={target_date}, "
                f"site_no={site_no}, bms_id={bms_id}]"
            )

            if run_id is not None:
                await self._db_local_service.mark_pipeline_error(
                    run_id=run_id,
                    error_message=error_message,
                    battery_count=battery_count,
                    saved_score_count=saved_score_count,
                    deleted_preprocessed_count=deleted_preprocessed_count,
                    raw_file_path=raw_file_path,
                    preprocessed_file_path=preprocessed_file_path,
                    result_file_path=result_file_path,
                )

            return {
                "status": "error",
                "message": "AI pipeline failed.",
                "error_message": error_message,
                "run_id": run_id,
                "ess_id": ess_id,
                "site_no": site_no,
                "bms_id": bms_id,
                "target_date": target_date.isoformat(),
                "battery_count": battery_count,
                "preprocessed_count": preprocessed_count,
                "saved_score_count": saved_score_count,
            }

    def _load_accumulated_preprocessed_data(
        self,
        ess_id: str,
        target_date: date,
    ) -> Tuple[List[dict], List[str]]:
        """AI 입력용 누적 N일 전처리 데이터를 읽어온다.

        기준:
        - target_date 이하의 전처리 날짜만 사용한다.
        - 날짜가 연속될 필요는 없다.
        - 사용 가능한 날짜 중 가장 최근 N개 날짜를 사용한다.

        예:
            AI_MIN_PREPROCESS_DAYS=7
            target_date=2026-07-10

            전처리 파일 존재 날짜:
            2026-07-01, 2026-07-03, 2026-07-04,
            2026-07-06, 2026-07-07, 2026-07-09, 2026-07-10

            위 7개 날짜의 파일을 모두 읽어서 AI 입력으로 사용한다.
        """

        required_days = self._settings.AI_MIN_PREPROCESS_DAYS

        available_dates = self._file_service.list_preprocessed_dates(
            ess_id=ess_id,
            end_date=target_date,
        )

        selected_dates = available_dates[-required_days:]

        rows: List[dict] = []
        loaded_dates: List[str] = []

        for current_date in selected_dates:
            daily_rows = self._file_service.read_preprocessed(
                ess_id=ess_id,
                target_date=current_date,
            )

            if not daily_rows:
                logger.warning(
                    "AI 입력용 전처리 파일은 있으나 데이터가 비어 있음 "
                    f"[ess_id={ess_id}, date={current_date}]"
                )
                continue

            rows.extend(daily_rows)
            loaded_dates.append(current_date.isoformat())

        logger.info(
            "AI 입력용 누적 preprocess 로드 완료 "
            f"[ess_id={ess_id}, target_date={target_date}, "
            f"days={loaded_dates}, rows={len(rows)}]"
        )

        return rows, loaded_dates
    
    
    def _attach_score_metadata(
        self,
        scores: List[dict],
        pipeline_run_id: int,
        site_no: int,
        bms_id: str,
        target_date: date,
    ) -> List[dict]:
        """AI 결과에 DB 저장용 메타데이터를 붙인다."""

        prediction_time = datetime.now()
        enriched_scores: List[dict] = []

        for item in scores:
            row = dict(item)

            row["pipeline_run_id"] = pipeline_run_id
            row["site_no"] = site_no
            row["bms_id"] = bms_id
            row["target_date"] = target_date
            row["date"] = target_date

            row["serial_number"] = (
                row.get("serial_number")
                or row.get("serial_no")
                or row.get("ess_serial_number")
                or row.get("bms_id")
                or bms_id
            )

            row["prediction_time"] = prediction_time

            row["bank_no"] = row.get("bank_no", row.get("bank_number", 0))
            row["rack_no"] = row.get(
                "rack_no",
                row.get("rack_number", row.get("rack_idx", row.get("index", 0))),
            )
            row["string_no"] = row.get("string_no", row.get("string_number", 0))
            row["module_no"] = row.get("module_no", row.get("module_number", 0))

            enriched_scores.append(row)

        return enriched_scores

    def _get_target_date(self) -> date:
        """설정값 기준으로 분석 대상 날짜를 계산한다."""

        return date.today() + timedelta(days=self._settings.TARGET_DATE_OFFSET_DAYS)

    def _make_ess_id(self, site_no: int, bms_id: str) -> str:
        """파일 저장 경로에 사용할 ESS ID를 만든다."""

        safe_bms_id = str(bms_id).strip()

        for ch in ['\\\\', '/', ':', '*', '?', '"', '<', '>', '|', ' ']:
            safe_bms_id = safe_bms_id.replace(ch, "_")

        return f"SITE_{site_no}_BMS_{safe_bms_id}"
