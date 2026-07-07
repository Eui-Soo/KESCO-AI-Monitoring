"""AI 서버 로컬 사이트/장치 Repository

이 파일은 우리 AI 서버 로컬 DB의 ess_site, ess_device 테이블을 관리한다.

원본 데이터:
    - 관제 DB tb_emc_site_info
    - 관제 DB tb_emc_dvc_info

로컬 저장 테이블:
    - ess_site
    - ess_device

주요 역할:
    1. 관제 DB에서 조회한 사이트/장치 목록을 로컬 DB에 저장 또는 갱신
    2. 로컬 DB에 저장된 사이트 목록 조회
    3. AI 분석 대상으로 활성화된 장치 목록 조회
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.model.models import EssDevice, EssSite


class SiteRepository:
    """AI 서버 로컬 사이트/장치 WRITE / READ 전담 Repository"""

    async def upsert_sites(
        self,
        session: AsyncSession,
        remote_rows: List[Dict],
    ) -> Dict:
        """관제 DB에서 조회한 사이트/장치 목록을 로컬 DB에 저장 또는 갱신한다."""

        now = datetime.now()

        site_created_count = 0
        site_updated_count = 0
        device_created_count = 0
        device_updated_count = 0
        skipped_device_count = 0

        # 같은 site_no가 여러 번 나올 수 있으므로 사이트는 먼저 중복 제거한다.
        site_map: Dict[int, Dict] = {}

        for row in remote_rows:
            site_no = row.get("site_no")

            if site_no is None:
                continue

            site_map[int(site_no)] = row

        # 1. ess_site upsert
        for site_no, row in site_map.items():
            existing_site = await self._find_site_by_site_no(
                session=session,
                site_no=site_no,
            )

            if existing_site is None:
                site = EssSite(
                    site_no=site_no,
                    site_name=self._to_str(
                        row.get("site_name"),
                        default=f"SITE_{site_no}",
                    ),
                    site_type=self._to_str(row.get("site_type")),
                    prtcl_ver=self._to_str(row.get("prtcl_ver")),
                    site_addr=self._to_str(row.get("site_addr")),
                    lat_vl=self._to_float(row.get("lat_vl")),
                    lot_vl=self._to_float(row.get("lot_vl")),
                    use_yn=self._to_str(row.get("use_yn"), default="Y"),
                    ai_enabled="Y",
                    last_synced_at=now,
                )

                session.add(site)
                site_created_count += 1

            else:
                existing_site.site_name = self._to_str(
                    row.get("site_name"),
                    default=existing_site.site_name,
                )
                existing_site.site_type = self._to_str(row.get("site_type"))
                existing_site.prtcl_ver = self._to_str(row.get("prtcl_ver"))
                existing_site.site_addr = self._to_str(row.get("site_addr"))
                existing_site.lat_vl = self._to_float(row.get("lat_vl"))
                existing_site.lot_vl = self._to_float(row.get("lot_vl"))
                existing_site.use_yn = self._to_str(row.get("use_yn"), default="Y")
                existing_site.last_synced_at = now

                # ai_enabled는 사용자가 직접 관리할 수 있으므로 동기화 때 덮어쓰지 않는다.
                site_updated_count += 1

        # 2. ess_device upsert
        for row in remote_rows:
            dvc_id = self._to_str(row.get("dvc_id"))

            if not dvc_id:
                skipped_device_count += 1
                continue

            site_no = row.get("site_no")
            if site_no is None:
                skipped_device_count += 1
                continue

            existing_device = await self._find_device_by_dvc_id(
                session=session,
                dvc_id=dvc_id,
            )

            if existing_device is None:
                device = EssDevice(
                    site_no=int(site_no),
                    dvc_id=dvc_id,
                    dvc_no=self._to_int(row.get("dvc_no")),
                    dvc_name=self._to_str(row.get("dvc_name")),
                    dvc_type=self._to_str(row.get("dvc_type")),
                    dvc_usg=self._to_str(row.get("dvc_usg")),
                    up_dvc_id=self._to_str(row.get("up_dvc_id")),
                    btrrck_cnt=self._to_int(row.get("btrrck_cnt")),
                    btrrck_mdul_cnt=self._to_int(row.get("btrrck_mdul_cnt")),
                    mdul_cll_cnt=self._to_int(row.get("mdul_cll_cnt")),
                    spec_data=self._to_str(row.get("spec_data")),
                    ai_enabled="Y",
                    last_synced_at=now,
                )

                session.add(device)
                device_created_count += 1

            else:
                existing_device.site_no = int(site_no)
                existing_device.dvc_no = self._to_int(row.get("dvc_no"))
                existing_device.dvc_name = self._to_str(row.get("dvc_name"))
                existing_device.dvc_type = self._to_str(row.get("dvc_type"))
                existing_device.dvc_usg = self._to_str(row.get("dvc_usg"))
                existing_device.up_dvc_id = self._to_str(row.get("up_dvc_id"))
                existing_device.btrrck_cnt = self._to_int(row.get("btrrck_cnt"))
                existing_device.btrrck_mdul_cnt = self._to_int(row.get("btrrck_mdul_cnt"))
                existing_device.mdul_cll_cnt = self._to_int(row.get("mdul_cll_cnt"))
                existing_device.spec_data = self._to_str(row.get("spec_data"))
                existing_device.last_synced_at = now

                # ai_enabled는 사용자가 직접 관리할 수 있으므로 동기화 때 덮어쓰지 않는다.
                device_updated_count += 1

        return {
            "site_created_count": site_created_count,
            "site_updated_count": site_updated_count,
            "device_created_count": device_created_count,
            "device_updated_count": device_updated_count,
            "skipped_device_count": skipped_device_count,
        }

    async def find_sites(self, session: AsyncSession) -> List[Dict]:
        """로컬 DB에 저장된 사이트 목록을 조회한다."""

        site_result = await session.execute(
            select(EssSite).order_by(EssSite.site_no)
        )
        sites = site_result.scalars().all()

        device_result = await session.execute(
            select(EssDevice).order_by(
                EssDevice.site_no,
                EssDevice.dvc_no,
                EssDevice.dvc_id,
            )
        )
        devices = device_result.scalars().all()

        devices_by_site: Dict[int, List[Dict]] = {}

        for device in devices:
            devices_by_site.setdefault(device.site_no, []).append(
                self._device_to_dict(device)
            )

        results = []

        for site in sites:
            site_dict = self._site_to_dict(site)
            site_dict["devices"] = devices_by_site.get(site.site_no, [])
            site_dict["device_count"] = len(site_dict["devices"])
            results.append(site_dict)

        return results

    async def find_site_by_site_no(
        self,
        session: AsyncSession,
        site_no: int,
    ) -> Optional[Dict]:
        """site_no 기준으로 특정 사이트 상세 정보를 조회한다."""

        site = await self._find_site_by_site_no(
            session=session,
            site_no=site_no,
        )

        if site is None:
            return None

        device_result = await session.execute(
            select(EssDevice)
            .where(EssDevice.site_no == site_no)
            .order_by(EssDevice.dvc_no, EssDevice.dvc_id)
        )
        devices = device_result.scalars().all()

        site_dict = self._site_to_dict(site)
        site_dict["devices"] = [self._device_to_dict(device) for device in devices]
        site_dict["device_count"] = len(site_dict["devices"])

        return site_dict

    async def find_active_ai_targets(self, session: AsyncSession) -> List[Dict]:
        """AI 분석 대상으로 활성화된 사이트/장치 목록을 조회한다.

        조건:
            - ess_site.use_yn = 'Y'
            - ess_site.ai_enabled = 'Y'
            - ess_device.ai_enabled = 'Y'

        참고:
            지금은 dvc_type/dvc_usg로 BMS만 강제 필터하지 않는다.
            실제 값 확인 후 필요하면 여기 where 조건에 BMS 필터를 추가하면 된다.
        """

        result = await session.execute(
            select(EssSite, EssDevice)
            .join(EssDevice, EssDevice.site_no == EssSite.site_no)
            .where(EssSite.use_yn == "Y")
            .where(EssSite.ai_enabled == "Y")
            .where(EssDevice.ai_enabled == "Y")
            .order_by(EssSite.site_no, EssDevice.dvc_no, EssDevice.dvc_id)
        )

        targets = []

        for site, device in result.all():
            targets.append(
                {
                    "site_no": site.site_no,
                    "site_name": site.site_name,

                    "dvc_id": device.dvc_id,
                    "bms_id": device.dvc_id,
                    "serial_number": device.dvc_id,

                    "dvc_no": device.dvc_no,
                    "dvc_name": device.dvc_name,
                    "dvc_type": device.dvc_type,
                    "dvc_usg": device.dvc_usg,

                    "btrrck_cnt": device.btrrck_cnt,
                    "btrrck_mdul_cnt": device.btrrck_mdul_cnt,
                    "mdul_cll_cnt": device.mdul_cll_cnt,

                    "ess_id": self.make_ess_id(site.site_no, device.dvc_id),
                }
            )

        return targets

    async def _find_site_by_site_no(
        self,
        session: AsyncSession,
        site_no: int,
    ) -> Optional[EssSite]:
        """EssSite ORM 객체 조회"""

        result = await session.execute(
            select(EssSite).where(EssSite.site_no == site_no)
        )

        return result.scalar_one_or_none()

    async def _find_device_by_dvc_id(
        self,
        session: AsyncSession,
        dvc_id: str,
    ) -> Optional[EssDevice]:
        """EssDevice ORM 객체 조회"""

        result = await session.execute(
            select(EssDevice).where(EssDevice.dvc_id == dvc_id)
        )

        return result.scalar_one_or_none()

    def _site_to_dict(self, site: EssSite) -> Dict:
        """EssSite ORM 객체를 API 응답용 dict로 변환"""

        return {
            "id": site.id,
            "site_no": site.site_no,
            "site_name": site.site_name,
            "site_type": site.site_type,
            "prtcl_ver": site.prtcl_ver,
            "site_addr": site.site_addr,
            "lat_vl": site.lat_vl,
            "lot_vl": site.lot_vl,
            "use_yn": site.use_yn,
            "ai_enabled": site.ai_enabled,
            "last_synced_at": site.last_synced_at.isoformat() if site.last_synced_at else None,
            "inserted": site.inserted.isoformat() if site.inserted else None,
            "updated": site.updated.isoformat() if site.updated else None,
        }

    def _device_to_dict(self, device: EssDevice) -> Dict:
        """EssDevice ORM 객체를 API 응답용 dict로 변환"""

        return {
            "id": device.id,
            "site_no": device.site_no,
            "dvc_id": device.dvc_id,
            "bms_id": device.dvc_id,
            "serial_number": device.dvc_id,
            "dvc_no": device.dvc_no,
            "dvc_name": device.dvc_name,
            "dvc_type": device.dvc_type,
            "dvc_usg": device.dvc_usg,
            "up_dvc_id": device.up_dvc_id,
            "btrrck_cnt": device.btrrck_cnt,
            "btrrck_mdul_cnt": device.btrrck_mdul_cnt,
            "mdul_cll_cnt": device.mdul_cll_cnt,
            "spec_data": device.spec_data,
            "ai_enabled": device.ai_enabled,
            "last_synced_at": device.last_synced_at.isoformat() if device.last_synced_at else None,
            "inserted": device.inserted.isoformat() if device.inserted else None,
            "updated": device.updated.isoformat() if device.updated else None,
        }

    def make_ess_id(self, site_no: int, dvc_id: str) -> str:
        """파일 저장 경로 등에 사용할 ESS ID 문자열 생성"""

        safe_dvc_id = str(dvc_id).strip()

        for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', ' ']:
            safe_dvc_id = safe_dvc_id.replace(ch, "_")

        return f"SITE_{site_no}_BMS_{safe_dvc_id}"

    def _to_str(self, value, default: Optional[str] = None) -> Optional[str]:
        """값을 문자열로 변환"""

        if value is None:
            return default

        text = str(value).strip()

        if not text:
            return default

        return text

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
