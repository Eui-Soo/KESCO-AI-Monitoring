"""가짜 관제 DB 생성기 (로컬 PostgreSQL 자동 생성 + 고속 적재)

실제 관제 DB DDL(tb_emc_* 테이블)과 동일한 구조로 로컬 PostgreSQL에
가짜 관제 DB를 만들고, 여러 ESS 사이트의 배터리 분단위 데이터를 넣는다.
정상/화재/불량 사이트가 섞여 있으며, 화재 사이트에는 실제 리튬이온 화재처럼
"잠복 열화 -> 열폭주 -> 데이터 두절" 시나리오가 시간에 걸쳐 전개된다.

이 스크립트를 실행하면:
    1) (없으면) 가짜 관제 DB를 자동 생성
    2) tb_emc_* 테이블을 DROP 후 재생성 (실제 DDL과 동일)
    3) 사이트/장치/분단위 데이터를 COPY로 고속 적재 (700만 건도 수 분)
    4) mock_labels.json (정답 라벨) 생성 - AI 탐지 성능 채점용

그 다음 AI 서버 .env에서 원격지(DB_REMOTE_*)만 이 가짜 DB로 바꾸면
실제 관제 서버 없이 파이프라인 전체를 테스트할 수 있다.

────────────────────────────────────────────────────────────
특징
────────────────────────────────────────────────────────────
    - 별도 설치 불필요: 프로젝트가 이미 쓰는 asyncpg만 사용
      (psycopg2 안 깔아도 됨)
    - 프로젝트 Settings 재사용: 접속 정보를 .env와 자동 일치
    - COPY 고속 적재 + 하루치씩 스트리밍 -> 대용량도 안 멈춤

────────────────────────────────────────────────────────────
사용법
────────────────────────────────────────────────────────────
    # 이 파일을 레포 루트(main.py 옆) 또는 scripts/ 아래에 두고
    python create_mock_remote_db.py

    아래 CONFIG 값만 바꾸면 원하는 대로 데이터가 생성된다.
"""

import asyncio
import json
import math
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ════════════════════════════════════════════════════════════
#  CONFIG ─ 여기 값만 바꾸면 됩니다
# ════════════════════════════════════════════════════════════

CONFIG = {
    # ── 가짜 관제 DB 이름 ────────────────────────────────────
    #   접속 정보(host/port/user/password)는 프로젝트 .env의
    #   DB_* (로컬 결과 DB) 설정을 그대로 재사용한다.
    #   여기서는 "가짜 관제 DB의 이름"만 새로 정한다.
    "target_db": "kesco_monitoring_fake",

    # ── 기간 / 주기 ──────────────────────────────────────────
    "end_date": "2026-07-05",     # 데이터 마지막 날짜 (YYYY-MM-DD)
    "days": 92,                   # 생성 기간(일). 92 ≈ 3개월
    "interval_minutes": 1,        # 센싱 주기(분). 실운영 기준 1분
                                  #   ↑ 빠른 테스트는 5나 10으로 올리면 훨씬 빨라짐

    # ── 사이트 구성 ──────────────────────────────────────────
    "normal_site_count": 3,       # 정상 사이트 수
    "fire_site_count": 2,         # 화재 사이트 수 (잠복->열폭주->두절)
    "fault_site_count": 1,        # 불량 사이트 수 (화재는 아니나 이상값 지속)
    "add_closed_site": True,      # use_yn='N' 폐쇄 사이트 1곳 추가 여부

    # ── 랙 / 모듈 규모 (사이트마다 이 범위에서 랜덤) ──────────
    "rack_count_min": 2,          # 사이트당 최소 랙 수
    "rack_count_max": 3,          # 사이트당 최대 랙 수
    "modules_per_rack_min": 2,    # 랙당 최소 모듈 수
    "modules_per_rack_max": 4,    # 랙당 최대 모듈 수

    # ── 정상 배터리 전기적 특성 ──────────────────────────────
    "nominal_cell_voltage": 3.70, # 셀 기준 전압(V)
    "voltage_swing": 0.15,        # 하루 충방전 전압 변동폭(V)
    "nominal_temp": 26.0,         # 기준 모듈 온도(℃)
    "temp_swing": 4.0,            # 하루 온도 변동폭(℃)

    # ── 화재 시나리오 파라미터 ──────────────────────────────
    "incipient_days": 14,             # 잠복기: 화재 며칠 전부터 서서히 열화
    "runaway_minutes": 45,            # 열폭주: 발화 몇 분 전부터 급격히 붕괴
    "fire_day_ratio": 0.7,            # 기간 중 화재 발생 시점 (0.7=70% 지점)
    "incipient_voltage_drop": 0.45,   # 잠복기 이상 셀 전압 하락폭(V)
    "runaway_peak_temp": 160.0,       # 열폭주 정점 모듈 온도(℃)

    # ── 불량(fault) 사이트 파라미터 ─────────────────────────
    #   화재는 아니지만 특정 모듈 온도가 높고 셀 전압 편차가 큰 상태가
    #   기간 후반부부터 지속된다 (교체 대상 수준의 열화).
    "fault_start_ratio": 0.6,     # 기간의 60% 지점부터 불량 증상 시작
    "fault_temp_rise": 15.0,      # 불량 모듈 온도 상승폭(℃)
    "fault_voltage_drop": 0.25,   # 불량 셀 전압 하락폭(V)

    # ── 정상 사이트에 심는 센서 고장(화재 아님) ─────────────
    "add_sensor_fault": True,     # 정상 사이트 1곳에 NULL 셀 하나 추가

    # ── 실행 옵션 ────────────────────────────────────────────
    "drop_and_recreate": True,    # True면 매 실행마다 테이블 DROP 후 재생성
    "labels_file": "mock_labels.json",
    "copy_batch_days": 3,         # 며칠치씩 모아서 COPY할지 (메모리/속도 조절)
    "random_seed": 42,            # 같은 seed면 항상 같은 데이터
}

# ════════════════════════════════════════════════════════════
#  프로젝트 Settings 로드 (접속 정보 재사용)
# ════════════════════════════════════════════════════════════

ROOT = Path(__file__).resolve().parent
if ROOT.name == "scripts":       # scripts/ 아래 두어도 동작하도록
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

# Settings는 main()에서 지연 로드한다 (import 실패 시 안내 메시지를 주기 위해).

# ════════════════════════════════════════════════════════════
#  이 아래는 수정하지 않아도 됩니다
# ════════════════════════════════════════════════════════════

CELL_COUNT = 20
SEED_INS_ID = "SEED"
BMS_NO = 1

SITE_NAME_POOL = [
    ("대전 본원 ESS",       "대전광역시 유성구 테스트로 1",    36.3504, 127.3845),
    ("세종 지사 ESS",       "세종특별자치시 테스트대로 2",      36.4800, 127.2890),
    ("청주 물류센터 ESS",   "충청북도 청주시 테스트산단로 3",   36.6424, 127.4890),
    ("전주 공장 ESS",       "전라북도 전주시 테스트공단길 4",   35.8242, 127.1480),
    ("부산 항만 ESS",       "부산광역시 영도구 테스트부두로 5",  35.0951, 129.0400),
    ("광주 데이터센터 ESS", "광주광역시 북구 테스트첨단로 6",   35.1595, 126.8526),
    ("인천 물류 ESS",       "인천광역시 서구 테스트산업로 7",   37.5093, 126.6980),
    ("울산 석유화학 ESS",   "울산광역시 남구 테스트공단로 8",   35.5384, 129.3114),
]

# 실제 관제 DB DDL과 동일한 스키마 (owner 지정만 제거)
SCHEMA_SQL = r"""
DROP TABLE IF EXISTS tb_emc_bms_mntly_rcd CASCADE;
DROP TABLE IF EXISTS tb_emc_mdul_mntly_rcd CASCADE;
DROP TABLE IF EXISTS tb_emc_btrrck_mntly_rcd CASCADE;
DROP TABLE IF EXISTS tb_emc_dvc_info CASCADE;
DROP TABLE IF EXISTS tb_emc_dvc_group_info CASCADE;
DROP TABLE IF EXISTS tb_emc_site_info CASCADE;

CREATE TABLE tb_emc_site_info (
    site_no      integer PRIMARY KEY,
    eqpm_site_nm varchar(100) NOT NULL,
    site_type    varchar(21)  NOT NULL,
    prtcl_ver    integer,
    lat_vl       numeric(13, 10),
    lot_vl       numeric(13, 10),
    site_addr    varchar(300),
    sys_reg_dt   timestamp default now() NOT NULL,
    ins_id       varchar(20)  NOT NULL,
    ins_dt       timestamp default now() NOT NULL,
    upt_id       varchar(20),
    upt_dt       timestamp,
    use_yn       char default 'Y' NOT NULL
        CONSTRAINT site_info_use_yn CHECK (use_yn = ANY (ARRAY['Y'::bpchar, 'N'::bpchar]))
);

CREATE TABLE tb_emc_dvc_group_info (
    group_id varchar(20) PRIMARY KEY,
    group_nm varchar(100)
);

CREATE TABLE tb_emc_dvc_info (
    dvc_id           varchar(20) PRIMARY KEY,
    site_no          integer NOT NULL REFERENCES tb_emc_site_info ON UPDATE CASCADE ON DELETE CASCADE,
    dvc_no           integer NOT NULL,
    dvc_nm           varchar(300),
    dvc_type         varchar(21) NOT NULL,
    dvc_usg          varchar(21) NOT NULL,
    mkr_nm           varchar(100),
    dvc_mdl_nm       varchar(100),
    mkr_prtcl_ver_nm varchar(100),
    wrhs_dt          timestamp default now() NOT NULL,
    spmt_dt          timestamp,
    rdtg_yn          char default 'N' NOT NULL
        CONSTRAINT redtag_yn CHECK (rdtg_yn = ANY (ARRAY['Y'::bpchar, 'N'::bpchar])),
    dvc_cpct         numeric(7, 2),
    btrrck_cnt       integer,
    btrrck_mdul_cnt  integer,
    mdul_cll_cnt     integer,
    ctrl_psblty_yn   char default 'N' NOT NULL
        CONSTRAINT ctrl_possibility_yn CHECK (ctrl_psblty_yn = ANY (ARRAY['Y'::bpchar, 'N'::bpchar])),
    ins_id           varchar(20) NOT NULL,
    ins_dt           timestamp default now() NOT NULL,
    upt_id           varchar(20),
    upt_dt           timestamp default now(),
    group_id         varchar(20) REFERENCES tb_emc_dvc_group_info ON UPDATE CASCADE ON DELETE SET NULL,
    up_dvc_id        varchar(20) REFERENCES tb_emc_dvc_info ON UPDATE CASCADE ON DELETE SET NULL,
    spec_data        jsonb default '{}'::jsonb
);

CREATE TABLE tb_emc_btrrck_mntly_rcd (
    site_no              integer NOT NULL,
    bms_id               varchar(20) NOT NULL,
    srvr_rcd_dt          timestamp default now() NOT NULL,
    dvc_rcd_dt           timestamp default now() NOT NULL,
    bms_no               integer NOT NULL,
    dvc_no               integer NOT NULL,
    dvc_stts             integer,
    mdul_cnt             integer,
    soc                  numeric(6, 3),
    soh                  numeric(6, 3),
    dc_vltg              numeric(9, 3),
    dc_crnt              numeric(8, 3),
    charg_crnt_lmt       numeric(8, 3),
    dcharge_crnt_lmt     numeric(8, 3),
    charg_actpw_lmt      numeric(8, 3),
    dcharg_actpw_lmt     numeric(8, 3),
    avg_cll_vltg         numeric(9, 3),
    max_cll_vltg         numeric(9, 3),
    min_cll_vltg         numeric(9, 3),
    avg_mdul_tp          numeric(6, 2),
    max_mdul_tp          numeric(6, 2),
    min_mdul_tp          numeric(6, 2),
    max_cll_vltg_mdul_no integer,
    max_cll_vltg_cll_no  integer,
    min_cll_vltg_mdul_no integer,
    min_cll_vltg_cll_no  integer,
    max_mdul_tp_mdul_no  integer,
    max_mdul_tp_cll_no   integer,
    min_mdul_tp_mdul_no  integer,
    min_mdul_tp_cll_no   integer,
    warn_1 numeric(10), warn_2 numeric(10), warn_3 numeric(10), warn_4 numeric(10), warn_5 numeric(10),
    warn_6 numeric(10), warn_7 numeric(10), warn_8 numeric(10), warn_9 numeric(10), warn_10 numeric(10),
    bkdn_1 numeric(10), bkdn_2 numeric(10), bkdn_3 numeric(10), bkdn_4 numeric(10), bkdn_5 numeric(10),
    bkdn_6 numeric(10), bkdn_7 numeric(10), bkdn_8 numeric(10), bkdn_9 numeric(10), bkdn_10 numeric(10),
    CONSTRAINT tb_emc_btrrck_mntly_rcd_pk PRIMARY KEY (site_no, bms_id, dvc_no, srvr_rcd_dt)
);
CREATE INDEX idx_tb_emc_btrrck_mntly_rcd_srvr_rcd_dt ON tb_emc_btrrck_mntly_rcd (srvr_rcd_dt);

CREATE TABLE tb_emc_mdul_mntly_rcd (
    site_no     integer NOT NULL,
    bms_id      varchar(20) NOT NULL,
    srvr_rcd_dt timestamp default now() NOT NULL,
    dvc_rcd_dt  timestamp default now() NOT NULL,
    bms_no      integer NOT NULL,
    btrrck_no   integer NOT NULL,
    dvc_no      integer NOT NULL,
    mdul_tp_1   numeric(6, 2),
    cll_1_vltg numeric(9,3), cll_2_vltg numeric(9,3), cll_3_vltg numeric(9,3), cll_4_vltg numeric(9,3),
    cll_5_vltg numeric(9,3), cll_6_vltg numeric(9,3), cll_7_vltg numeric(9,3), cll_8_vltg numeric(9,3),
    cll_9_vltg numeric(9,3), cll_10_vltg numeric(9,3), cll_11_vltg numeric(9,3), cll_12_vltg numeric(9,3),
    cll_13_vltg numeric(9,3), cll_14_vltg numeric(9,3), cll_15_vltg numeric(9,3), cll_16_vltg numeric(9,3),
    cll_17_vltg numeric(9,3), cll_18_vltg numeric(9,3), cll_19_vltg numeric(9,3), cll_20_vltg numeric(9,3),
    mdul_tp_2   numeric(6, 2),
    mdul_tp_3   numeric(6, 2),
    CONSTRAINT tb_emc_mdul_mntly_rcd_pk PRIMARY KEY (site_no, bms_id, dvc_no, btrrck_no, srvr_rcd_dt)
);
CREATE INDEX idx_tb_emc_mdul_mntly_rcd_srvr_rcd_dt ON tb_emc_mdul_mntly_rcd (srvr_rcd_dt);

CREATE TABLE tb_emc_bms_mntly_rcd (
    site_no         integer NOT NULL,
    dvc_id          varchar(20) NOT NULL,
    srvr_rcd_dt     timestamp default now() NOT NULL,
    dvc_rcd_dt      timestamp default now() NOT NULL,
    dvc_no          integer NOT NULL,
    dvc_stts        integer,
    onln_btrrck_cnt integer,
    whol_btrrck_cnt integer,
    max_cll_vltg_btrrck_no integer, max_cll_vltg_mdul_no integer, max_cll_vltg_cll_no integer,
    min_cll_vltg_btrrck_no integer, min_cll_vltg_mdul_no integer, min_cll_vltg_cll_no integer,
    max_mdul_tp_btrrck_no  integer, max_mdul_tp_mdul_no  integer, max_mdul_tp_cll_no  integer,
    min_mdul_tp_btrrck_no  integer, min_mdul_tp_mdul_no  integer, min_mdul_tp_cll_no  integer,
    hb              integer,
    soc numeric(6,3), soh numeric(6,3), dc_vltg numeric(9,3), dc_crnt numeric(8,3),
    charg_crnt_lmt numeric(8,3), dcharge_crnt_lmt numeric(8,3),
    charg_actpw_lmt numeric(8,3), dcharg_actpw_lmt numeric(8,3),
    max_cll_vltg numeric(9,3), min_cll_vltg numeric(9,3),
    max_mdul_tp numeric(6,2), min_mdul_tp numeric(6,2),
    warn_1 numeric(10), warn_2 numeric(10), warn_3 numeric(10), warn_4 numeric(10), warn_5 numeric(10),
    warn_6 numeric(10), warn_7 numeric(10), warn_8 numeric(10), warn_9 numeric(10), warn_10 numeric(10),
    bkdn_1 numeric(10), bkdn_2 numeric(10), bkdn_3 numeric(10), bkdn_4 numeric(10), bkdn_5 numeric(10),
    bkdn_6 numeric(10), bkdn_7 numeric(10), bkdn_8 numeric(10), bkdn_9 numeric(10), bkdn_10 numeric(10),
    eol numeric(15, 4),
    CONSTRAINT tb_emc_bms_mntly_rcd_pk PRIMARY KEY (site_no, dvc_id, srvr_rcd_dt)
);
CREATE INDEX idx_tb_emc_bms_mntly_rcd_srvr_rcd_dt ON tb_emc_bms_mntly_rcd (srvr_rcd_dt);
"""


# ────────────────────────────────────────────────────────────
#  계획 (토폴로지 + 화재/불량 시나리오)
# ────────────────────────────────────────────────────────────

@dataclass
class FirePlan:
    incipient_start: date
    fire_date: date
    fire_minute: int
    rack_no: int
    module_no: int
    cells: List[int]


@dataclass
class FaultPlan:
    start_date: date
    rack_no: int
    module_no: int
    cells: List[int]


@dataclass
class SitePlan:
    site_no: int
    name: str
    addr: str
    lat: float
    lot: float
    use_yn: str
    active: bool
    scenario: str = "normal"      # normal / fire / fault
    bms_id: str = ""
    rack_cnt: int = 0
    modules_per_rack: int = 0
    fire: Optional[FirePlan] = None
    fault: Optional[FaultPlan] = None
    sensor_fault: Optional[Dict] = None


def build_plan(cfg: Dict) -> Dict:
    rng = random.Random(cfg["random_seed"])
    end_date = date.fromisoformat(cfg["end_date"])
    days = cfg["days"]
    start_date = end_date - timedelta(days=days - 1)

    normal_n = cfg["normal_site_count"]
    fire_n = cfg["fire_site_count"]
    fault_n = cfg["fault_site_count"]
    total_active = normal_n + fire_n + fault_n
    if total_active > len(SITE_NAME_POOL):
        raise ValueError(
            f"사이트가 너무 많습니다. 최대 {len(SITE_NAME_POOL)}곳 지원 (요청 {total_active}곳). "
            "SITE_NAME_POOL에 이름을 추가하세요."
        )

    scenarios = ["fire"] * fire_n + ["fault"] * fault_n + ["normal"] * normal_n
    rng.shuffle(scenarios)

    # 센서 고장 심을 정상 사이트 하나
    normal_positions = [i for i, s in enumerate(scenarios) if s == "normal"]
    sensor_fault_pos = normal_positions[0] if (cfg["add_sensor_fault"] and normal_positions) else -1

    sites: List[SitePlan] = []
    for idx, scenario in enumerate(scenarios):
        site_no = idx + 1
        name, addr, lat, lot = SITE_NAME_POOL[idx]
        rack_cnt = rng.randint(cfg["rack_count_min"], cfg["rack_count_max"])
        modules_per_rack = rng.randint(cfg["modules_per_rack_min"], cfg["modules_per_rack_max"])

        site = SitePlan(
            site_no=site_no, name=name, addr=addr, lat=lat, lot=lot,
            use_yn="Y", active=True, scenario=scenario,
            bms_id=f"BMS{site_no:03d}", rack_cnt=rack_cnt, modules_per_rack=modules_per_rack,
        )

        if scenario == "fire":
            offset = int(days * cfg["fire_day_ratio"]) + rng.randint(-5, 5)
            offset = max(cfg["incipient_days"] + 1, min(days - 2, offset))
            fire_date = start_date + timedelta(days=offset)
            cell_a = rng.randint(1, CELL_COUNT)
            site.fire = FirePlan(
                incipient_start=fire_date - timedelta(days=cfg["incipient_days"]),
                fire_date=fire_date, fire_minute=rng.randint(9 * 60, 20 * 60),
                rack_no=rng.randint(1, rack_cnt), module_no=rng.randint(1, modules_per_rack),
                cells=sorted([cell_a, cell_a % CELL_COUNT + 1]),
            )
        elif scenario == "fault":
            fstart = start_date + timedelta(days=int(days * cfg["fault_start_ratio"]))
            cell_a = rng.randint(1, CELL_COUNT)
            site.fault = FaultPlan(
                start_date=fstart,
                rack_no=rng.randint(1, rack_cnt), module_no=rng.randint(1, modules_per_rack),
                cells=sorted([cell_a, cell_a % CELL_COUNT + 1]),
            )

        if idx == sensor_fault_pos:
            site.sensor_fault = {"rack_no": 1, "module_no": min(2, modules_per_rack), "cell_no": 13}

        sites.append(site)

    if cfg["add_closed_site"]:
        sites.append(SitePlan(
            site_no=len(scenarios) + 1, name="폐쇄 테스트 사이트", addr="폐쇄됨",
            lat=36.0, lot=127.0, use_yn="N", active=False,
        ))

    return {"start_date": start_date, "end_date": end_date, "days": days, "sites": sites}


# ────────────────────────────────────────────────────────────
#  하루치 데이터 생성
# ────────────────────────────────────────────────────────────

def generate_site_day(
    site: SitePlan, target_date: date, cfg: Dict, rng: random.Random,
) -> Tuple[List[tuple], List[tuple], List[tuple]]:
    fire = site.fire
    fault = site.fault

    # 화재 다음 날부터 데이터 두절
    if fire and target_date > fire.fire_date:
        return [], [], []

    # 화재 잠복 진행률
    incipient_severity = 0.0
    is_fire_day = False
    fire_minute = None
    if fire:
        if fire.incipient_start <= target_date <= fire.fire_date:
            incipient_severity = min(1.0, (target_date - fire.incipient_start).days / cfg["incipient_days"])
        if target_date == fire.fire_date:
            is_fire_day = True
            fire_minute = fire.fire_minute

    # 불량 활성 여부
    fault_active = bool(fault and target_date >= fault.start_date)

    base_v0 = cfg["nominal_cell_voltage"]; v_swing = cfg["voltage_swing"]
    base_t0 = cfg["nominal_temp"]; t_swing = cfg["temp_swing"]
    interval = cfg["interval_minutes"]

    mod_rows, rack_rows, bms_rows = [], [], []
    day_start = datetime.combine(target_date, time.min)
    steps = (24 * 60) // interval
    uni = rng.uniform

    for step in range(steps):
        minute_of_day = step * interval
        if is_fire_day and minute_of_day > fire_minute:
            break

        ts = day_start + timedelta(minutes=minute_of_day)
        dvc_ts = ts - timedelta(seconds=2)
        day_frac = minute_of_day / 1440.0
        cycle = math.sin(2 * math.pi * day_frac)
        base_v = base_v0 + v_swing * cycle
        base_temp = base_t0 + t_swing * cycle
        soc = round(min(100.0, max(5.0, 55.0 + 35.0 * cycle)), 1)
        dc_current = round(40.0 * cycle + uni(-2, 2), 1)

        runaway = 0.0
        if is_fire_day and minute_of_day > fire_minute - cfg["runaway_minutes"]:
            runaway = min(1.0, (minute_of_day - (fire_minute - cfg["runaway_minutes"])) / cfg["runaway_minutes"])

        site_min_v, site_max_v, site_max_tp = 99.0, -99.0, -99.0

        for rack_no in range(1, site.rack_cnt + 1):
            rack_min_v, rack_max_v = 99.0, -99.0
            rack_temps = []

            for module_no in range(1, site.modules_per_rack + 1):
                fire_mod = fire is not None and rack_no == fire.rack_no and module_no == fire.module_no
                fault_mod = fault_active and rack_no == fault.rack_no and module_no == fault.module_no

                temp = base_temp + uni(-0.5, 0.5)
                if fire_mod:
                    temp += 10.0 * incipient_severity
                    if runaway > 0:
                        temp = base_temp + 10.0 + (cfg["runaway_peak_temp"] - base_temp) * (runaway ** 2)
                elif fire and runaway > 0.6 and rack_no == fire.rack_no:
                    temp += 40.0 * (runaway - 0.6)
                elif fault_mod:
                    temp += cfg["fault_temp_rise"]
                temp = round(temp, 2)
                rack_temps.append(temp)

                cells: List[Optional[float]] = []
                for cell_idx in range(1, CELL_COUNT + 1):
                    if (site.sensor_fault and rack_no == site.sensor_fault["rack_no"]
                            and module_no == site.sensor_fault["module_no"]
                            and cell_idx == site.sensor_fault["cell_no"]):
                        cells.append(None)
                        continue

                    v = base_v + uni(-0.03, 0.03)
                    if fire_mod and cell_idx in fire.cells:
                        v -= cfg["incipient_voltage_drop"] * incipient_severity
                        if runaway > 0:
                            v = max(0.05, v * (1.0 - runaway) ** 2 + uni(0.0, 0.1))
                    elif fire_mod and runaway > 0.5:
                        v -= 1.2 * (runaway - 0.5)
                    elif fault_mod and cell_idx in fault.cells:
                        v -= cfg["fault_voltage_drop"]
                    cells.append(round(max(0.0, v), 3))

                valid = [c for c in cells if c is not None]
                if valid:
                    rack_min_v = min(rack_min_v, min(valid))
                    rack_max_v = max(rack_max_v, max(valid))

                mod_rows.append((
                    site.site_no, site.bms_id, ts, dvc_ts, BMS_NO, rack_no, module_no,
                    temp, round(temp + uni(-0.5, 0.5), 2), round(temp + uni(-0.5, 0.5), 2), *cells,
                ))

            avg_tp = round(sum(rack_temps) / len(rack_temps), 1)
            max_tp = round(max(rack_temps), 1)
            in_fire_rack = fire is not None and rack_no == fire.rack_no
            in_fault_rack = fault_active and rack_no == fault.rack_no
            warn = 1 if ((in_fire_rack and (incipient_severity > 0.7 or runaway > 0)) or in_fault_rack) else 0
            bkdn = 1 if (in_fire_rack and runaway > 0.7) else 0
            stts = 3 if bkdn else (2 if warn else 1)

            rack_rows.append((
                site.site_no, site.bms_id, ts, dvc_ts, BMS_NO, rack_no, stts,
                site.modules_per_rack, soc, round(97.0 + uni(-0.3, 0.3), 1),
                round(base_v * CELL_COUNT * site.modules_per_rack, 1), dc_current,
                round(base_v, 3), round(rack_max_v, 3), round(rack_min_v, 3),
                avg_tp, max_tp, round(min(rack_temps), 1), warn, bkdn,
            ))
            site_min_v = min(site_min_v, rack_min_v)
            site_max_v = max(site_max_v, rack_max_v)
            site_max_tp = max(site_max_tp, max_tp)

        s_warn = 1 if ((fire and (incipient_severity > 0.7 or runaway > 0)) or fault_active) else 0
        s_bkdn = 1 if runaway > 0.7 else 0
        bms_rows.append((
            site.site_no, site.bms_id, ts, dvc_ts, BMS_NO,
            3 if s_bkdn else (2 if s_warn else 1),
            site.rack_cnt, site.rack_cnt, step % 256, soc, round(97.0 + uni(-0.3, 0.3), 1),
            round(base_v * CELL_COUNT * site.modules_per_rack, 1), dc_current,
            round(site_max_v, 3), round(site_min_v, 3),
            round(site_max_tp, 1), round(base_temp - 2.0, 1), s_warn, s_bkdn,
        ))

    return mod_rows, rack_rows, bms_rows


# COPY 대상 컬럼 (row 생성 순서와 정확히 일치)
MODULE_COLS = (
    ["site_no", "bms_id", "srvr_rcd_dt", "dvc_rcd_dt", "bms_no", "btrrck_no", "dvc_no",
     "mdul_tp_1", "mdul_tp_2", "mdul_tp_3"] + [f"cll_{i}_vltg" for i in range(1, CELL_COUNT + 1)]
)
RACK_COLS = [
    "site_no", "bms_id", "srvr_rcd_dt", "dvc_rcd_dt", "bms_no", "dvc_no", "dvc_stts", "mdul_cnt",
    "soc", "soh", "dc_vltg", "dc_crnt", "avg_cll_vltg", "max_cll_vltg", "min_cll_vltg",
    "avg_mdul_tp", "max_mdul_tp", "min_mdul_tp", "warn_1", "bkdn_1",
]
BMS_COLS = [
    "site_no", "dvc_id", "srvr_rcd_dt", "dvc_rcd_dt", "dvc_no", "dvc_stts",
    "onln_btrrck_cnt", "whol_btrrck_cnt", "hb", "soc", "soh", "dc_vltg", "dc_crnt",
    "max_cll_vltg", "min_cll_vltg", "max_mdul_tp", "min_mdul_tp", "warn_1", "bkdn_1",
]


# ────────────────────────────────────────────────────────────
#  DB 준비 (asyncpg raw 접속으로 자동 생성 + COPY)
# ────────────────────────────────────────────────────────────

def _remote_conn_kwargs(settings, dbname: str) -> dict:
    """프로젝트 .env의 로컬 결과 DB(DB_*) 접속 정보를 재사용해
    지정한 dbname에 붙기 위한 asyncpg 접속 파라미터를 만든다."""
    return {
        "host": settings.DB_HOST,
        "port": settings.DB_PORT,
        "user": settings.DB_USER,
        "password": settings.DB_PASSWORD,
        "database": dbname,
    }


async def ensure_database(settings, target_db: str) -> None:
    """target_db가 없으면 기본 'postgres' DB에 붙어서 CREATE DATABASE."""
    import asyncpg

    try:
        admin = await asyncpg.connect(**_remote_conn_kwargs(settings, "postgres"))
    except Exception as e:
        print("❌ PostgreSQL 접속 실패. .env의 DB_HOST/PORT/USER/PASSWORD를 확인하세요.")
        print(f"   상세: {e}")
        raise SystemExit(1)

    try:
        exists = await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", target_db)
        if exists:
            print(f"ℹ️  DB '{target_db}' 이미 존재 -> 그대로 사용")
        else:
            await admin.execute(f'CREATE DATABASE "{target_db}"')
            print(f"✅ DB '{target_db}' 생성 완료")
    finally:
        await admin.close()


# ────────────────────────────────────────────────────────────
#  메인
# ────────────────────────────────────────────────────────────

async def main(cfg: Dict) -> None:
    try:
        from core.setting import Settings
    except Exception as e:
        print("❌ 프로젝트 Settings를 불러오지 못했습니다.")
        print("   이 스크립트를 레포 루트(main.py 옆) 또는 scripts/ 아래에 두고 실행하세요.")
        print(f"   상세: {e}")
        raise SystemExit(1)

    import asyncpg

    settings = Settings()
    plan = build_plan(cfg)
    active_sites = [s for s in plan["sites"] if s.active]

    steps_per_day = (24 * 60) // cfg["interval_minutes"]
    est_mod = sum(s.rack_cnt * s.modules_per_rack for s in active_sites) * steps_per_day * cfg["days"]

    print("=" * 60)
    print("가짜 관제 DB 생성기 (하이브리드: asyncpg + COPY + 자동생성)")
    print("=" * 60)
    print(f"접속     : {settings.DB_USER}@{settings.DB_HOST}:{settings.DB_PORT}")
    print(f"대상 DB  : {cfg['target_db']}  (없으면 자동 생성)")
    print(f"기간     : {plan['start_date']} ~ {plan['end_date']} ({cfg['days']}일)")
    print(f"센싱주기 : {cfg['interval_minutes']}분  (하루 {steps_per_day} 스텝)")
    print(f"사이트   : 정상 {cfg['normal_site_count']} + 화재 {cfg['fire_site_count']} + 불량 {cfg['fault_site_count']}"
          + (" + 폐쇄 1곳" if cfg["add_closed_site"] else ""))
    print(f"예상 모듈 레코드 : 약 {est_mod:,}건")
    print("-" * 60)
    for s in active_sites:
        tag = {"fire": "🔥화재", "fault": "⚠️ 불량", "normal": "정상 "}[s.scenario]
        line = f"  site {s.site_no} {s.name:<16} [{tag}] 랙{s.rack_cnt}×모듈{s.modules_per_rack}"
        if s.fire:
            fm = s.fire.fire_minute
            line += f"  발화 {s.fire.fire_date} {fm//60:02d}:{fm%60:02d} (r{s.fire.rack_no}/m{s.fire.module_no}/c{s.fire.cells})"
        if s.fault:
            line += f"  불량시작 {s.fault.start_date} (r{s.fault.rack_no}/m{s.fault.module_no})"
        if s.sensor_fault:
            line += f"  [센서고장 c{s.sensor_fault['cell_no']}]"
        print(line)
    print("=" * 60)

    # 1. DB 준비
    await ensure_database(settings, cfg["target_db"])

    conn = await asyncpg.connect(**_remote_conn_kwargs(settings, cfg["target_db"]))
    started = asyncio.get_event_loop().time()

    try:
        # 2. 스키마
        if cfg["drop_and_recreate"]:
            await conn.execute(SCHEMA_SQL)
            print("✅ 테이블 DROP 후 재생성 완료")

        # 3. 사이트 / 장치
        await conn.executemany(
            """INSERT INTO tb_emc_site_info
               (site_no, eqpm_site_nm, site_type, prtcl_ver, lat_vl, lot_vl, site_addr, use_yn, ins_id)
               VALUES ($1,$2,'ESS',2,$3,$4,$5,$6,$7)
               ON CONFLICT (site_no) DO UPDATE SET use_yn=EXCLUDED.use_yn""",
            [(s.site_no, s.name, s.lat, s.lot, s.addr, s.use_yn, SEED_INS_ID) for s in plan["sites"]],
        )
        await conn.executemany(
            """INSERT INTO tb_emc_dvc_info
               (dvc_id, site_no, dvc_no, dvc_nm, dvc_type, dvc_usg, mkr_nm,
                btrrck_cnt, btrrck_mdul_cnt, mdul_cll_cnt, spec_data, ins_id)
               VALUES ($1,$2,1,$3,'BMS','BATTERY','FAKE전자',$4,$5,$6,$7::jsonb,$8)
               ON CONFLICT (dvc_id) DO UPDATE SET btrrck_cnt=EXCLUDED.btrrck_cnt""",
            [(s.bms_id, s.site_no, f"{s.name} BMS", s.rack_cnt, s.modules_per_rack,
              CELL_COUNT, json.dumps({"vendor": "FAKE"}), SEED_INS_ID) for s in active_sites],
        )
        print(f"✅ 사이트 {len(plan['sites'])}곳 / BMS {len(active_sites)}대 등록 완료")

        # 4. 분단위 데이터 (며칠치씩 모아 COPY)
        rng = random.Random(cfg["random_seed"] + 1000)
        total_mod = total_rack = total_bms = 0
        buf_mod, buf_rack, buf_bms = [], [], []
        batch_days = max(1, cfg["copy_batch_days"])

        async def flush():
            nonlocal buf_mod, buf_rack, buf_bms
            if buf_mod:
                await conn.copy_records_to_table("tb_emc_mdul_mntly_rcd", records=buf_mod, columns=MODULE_COLS)
                await conn.copy_records_to_table("tb_emc_btrrck_mntly_rcd", records=buf_rack, columns=RACK_COLS)
                await conn.copy_records_to_table("tb_emc_bms_mntly_rcd", records=buf_bms, columns=BMS_COLS)
            buf_mod, buf_rack, buf_bms = [], [], []

        for day_idx in range(cfg["days"]):
            target_date = plan["start_date"] + timedelta(days=day_idx)
            for site in active_sites:
                m, r, b = generate_site_day(site, target_date, cfg, rng)
                buf_mod.extend(m); buf_rack.extend(r); buf_bms.extend(b)
                total_mod += len(m); total_rack += len(r); total_bms += len(b)

            if (day_idx + 1) % batch_days == 0:
                await flush()
            if (day_idx + 1) % 10 == 0 or day_idx == cfg["days"] - 1:
                el = asyncio.get_event_loop().time() - started
                print(f"  진행 {day_idx + 1}/{cfg['days']}일 | 모듈 {total_mod:,}건 | {el:,.0f}초")
        await flush()

        print(f"✅ 분단위 적재 완료: 모듈 {total_mod:,} / 랙 {total_rack:,} / BMS {total_bms:,} 건")

        await conn.execute("ANALYZE tb_emc_mdul_mntly_rcd")
        await conn.execute("ANALYZE tb_emc_btrrck_mntly_rcd")

    finally:
        await conn.close()

    # 5. 정답 라벨
    labels = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_db": cfg["target_db"],
        "config": {k: cfg[k] for k in ("random_seed", "interval_minutes", "days")},
        "period": {"start": plan["start_date"].isoformat(), "end": plan["end_date"].isoformat()},
        "sites": [],
    }
    for s in active_sites:
        item = {"site_no": s.site_no, "site_name": s.name, "bms_id": s.bms_id,
                "rack_cnt": s.rack_cnt, "modules_per_rack": s.modules_per_rack, "label": s.scenario}
        if s.fire:
            fm = s.fire.fire_minute
            item["fire"] = {
                "incipient_start": s.fire.incipient_start.isoformat(),
                "fire_datetime": f"{s.fire.fire_date}T{fm//60:02d}:{fm%60:02d}:00",
                "rack_no": s.fire.rack_no, "module_no": s.fire.module_no, "cells": s.fire.cells,
                "note": "잠복기부터 셀 전압 점진 하락, 발화 45분 전 열폭주, 발화 후 데이터 두절",
                "detection_hint": (
                    "이 화재는 '점진적 시계열 열화'라 현재 더미 ai_process(하루 평균 전압 기준)"
                    "로는 탐지되지 않는 것이 정상이다. 실제 시계열 AI 모델을 붙였을 때 "
                    "incipient_start 이후를 며칠 전에 예측하는지 평가하는 용도의 정답 라벨이다."
                ),
            }
        if s.fault:
            item["fault"] = {
                "start_date": s.fault.start_date.isoformat(),
                "rack_no": s.fault.rack_no, "module_no": s.fault.module_no, "cells": s.fault.cells,
                "note": "불량시작일부터 모듈 온도 상승 + 셀 전압 편차 지속 (화재는 아님)",
            }
        if s.sensor_fault:
            item["sensor_fault"] = {**s.sensor_fault, "note": "전 기간 해당 셀 NULL (화재 아님)"}
        labels["sites"].append(item)

    Path(cfg["labels_file"]).write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")

    print("-" * 60)
    print(f"✅ 완료!  정답 라벨: {cfg['labels_file']}")
    print()
    print("다음 순서로 테스트하세요:")
    print(f"  1. AI 서버 .env(.env.dev)의 원격지를 이 DB로 변경:")
    print(f"       DB_REMOTE_HOST={settings.DB_HOST}")
    print(f"       DB_REMOTE_PORT={settings.DB_PORT}")
    print(f"       DB_REMOTE_NAME={cfg['target_db']}")
    print(f"       DB_REMOTE_USER={settings.DB_USER}")
    print(f"       DB_REMOTE_PASSWORD=<로컬 DB 비밀번호>")
    print("  2. python main.py")
    print("  3. POST /api/v1/sites/sync  ->  POST /api/v1/pipeline/run")
    print("-" * 60)
    print("참고(중요):")
    print("  현재 ai_process는 '하루 평균 전압' 기준의 더미 스코어러라,")
    print("  점진적 화재 열화는 설계상 탐지하지 못합니다(정상 동작).")
    print("  파이프라인이 이상을 '잡는' 걸 눈으로 확인하려면 센서고장 NULL 셀을 보세요:")
    if any(s.sensor_fault for s in active_sites):
        sf = next(s for s in active_sites if s.sensor_fault)
        print(f"    site {sf.site_no} / {sf.bms_id} / rack {sf.sensor_fault['rack_no']}"
              f" / module {sf.sensor_fault['module_no']} / cell {sf.sensor_fault['cell_no']}")
        print("    -> 이 셀은 전압이 NULL이라 더미 AI가 0.70 이상 높은 점수를 줍니다.")
    print("  화재 사이트의 정답은 mock_labels.json에 기록됩니다(시계열 모델 검증용).")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main(CONFIG))