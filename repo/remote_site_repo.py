"""관제 DB 사이트/장치 정보 조회 Repository

이 파일은 원격 관제 DB에서 ESS 사이트 목록과 장치 정보를 읽어오는 역할을 한다.

사용 테이블:
    - tb_emc_site_info : 사이트 정보
    - tb_emc_dvc_info  : 사이트별 장치/BMS 정보

현재 목적:
    1. 관제 DB에 어떤 ESS 사이트가 있는지 확인
    2. 각 사이트에 어떤 장치/BMS가 연결되어 있는지 확인
    3. 이후 AI 서버 로컬 DB의 ess_site / ess_device 테이블에 동기화할 원본 데이터 제공

주의:
    이 Repository는 원격 관제 DB READ 전용이다.
    INSERT / UPDATE / DELETE는 하지 않는다.
"""

from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class RemoteSiteRepository:
    """관제 DB 사이트/장치 정보 READ 전담 Repository"""

    async def find_sites(self, session: AsyncSession) -> List[Dict]:
        """관제 DB에서 사용 중인 사이트와 장치 목록을 조회한다.

        조회 기준:
            - tb_emc_site_info.use_yn = 'Y' 인 사이트만 조회
            - 사이트에 연결된 장치 정보는 tb_emc_dvc_info에서 LEFT JOIN으로 조회

        Returns:
            [
                {
                    "site_no": 1,
                    "site_name": "...",
                    "site_type": "...",
                    "prtcl_ver": "...",
                    "lat_vl": ...,
                    "lot_vl": ...,
                    "site_addr": "...",
                    "use_yn": "Y",

                    "dvc_id": "...",
                    "dvc_no": 1,
                    "dvc_name": "...",
                    "dvc_type": "...",
                    "dvc_usg": "...",
                    "btrrck_cnt": 19,
                    "btrrck_mdul_cnt": 30,
                    "mdul_cll_cnt": 20,
                    "up_dvc_id": "...",
                    "spec_data": "..."
                },
                ...
            ]
        """

        result = await session.execute(
            text(
                """
                SELECT
                    s.site_no,
                    s.eqpm_site_nm AS site_name,
                    s.site_type,
                    s.prtcl_ver,
                    s.lat_vl,
                    s.lot_vl,
                    s.site_addr,
                    s.use_yn,

                    d.dvc_id,
                    d.dvc_no,
                    d.dvc_nm AS dvc_name,
                    d.dvc_type,
                    d.dvc_usg,
                    d.btrrck_cnt,
                    d.btrrck_mdul_cnt,
                    d.mdul_cll_cnt,
                    d.up_dvc_id,
                    d.spec_data
                FROM tb_emc_site_info s
                LEFT JOIN tb_emc_dvc_info d
                    ON d.site_no = s.site_no
                WHERE s.use_yn = 'Y'
                ORDER BY
                    s.site_no,
                    d.dvc_no
                """
            )
        )

        return [dict(row) for row in result.mappings()]

    async def find_device_type_summary(self, session: AsyncSession) -> List[Dict]:
        """관제 DB 장치 유형/용도 분포를 조회한다.

        왜 필요한가?
            tb_emc_dvc_info 안에 여러 종류의 장치가 있을 수 있다.
            그중 어떤 dvc_type / dvc_usg 조합이 BMS인지 확인해야
            AI 분석 대상 장치만 정확히 골라낼 수 있다.

        Returns:
            [
                {
                    "dvc_type": "...",
                    "dvc_usg": "...",
                    "count": 10
                },
                ...
            ]
        """

        result = await session.execute(
            text(
                """
                SELECT
                    dvc_type,
                    dvc_usg,
                    COUNT(*) AS count
                FROM tb_emc_dvc_info
                GROUP BY
                    dvc_type,
                    dvc_usg
                ORDER BY
                    dvc_type,
                    dvc_usg
                """
            )
        )

        return [dict(row) for row in result.mappings()]