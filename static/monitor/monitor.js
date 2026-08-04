const content = document.getElementById('content');
const navItems = document.querySelectorAll('.nav-item');

const sites = [
  ['1','영광 ESS 2호기','전라남도 영광군','전력남서부','삼성SDI','2024-11-15','93.7','비정상','2025-05-19 10:20'],
  ['2','평택 ESS 1호기','경기도 평택시','경기남부','LG에너지솔루션','2024-08-21','87.2','비정상','2025-05-19 10:15'],
  ['3','군산 ESS 3호기','전라북도 군산시','전력동부','삼성SDI','2024-09-30','72.4','주의','2025-05-19 10:18'],
  ['4','김해 ESS 1호기','경상남도 김해시','경남서부','LG에너지솔루션','2024-07-10','68.1','주의','2025-05-19 10:10'],
  ['5','제주 ESS 2호기','제주특별자치도 제주시','제주권','CATL','2024-12-05','34.6','정상','2025-05-19 10:05'],
  ['6','나주 ESS 1호기','전라남도 나주시','전력남서부','삼성SDI','2024-06-18','29.8','정상','2025-05-19 10:02'],
  ['7','울산 ESS 1호기','울산광역시 울주군','영남동부','LG에너지솔루션','2024-10-22','-','진단 불가','2025-05-18 18:45'],
  ['8','세종 ESS 4호기','세종특별자치시','충청권','삼성SDI','2025-01-12','-','데이터 없음','-'],
];

const cells = [18,22,31,26,29,34,92,45,28,33,24,37,41,27,39,32,30,25,48,21];
const smallCells = [18.7,22.4,20.2,26.1,34.6,41.2,82.1,30.8,26.5,24.1,28.7,91.8,37.9,44.8,55.7,22.0,17.8,15.6];

const state = {
  selectedSiteId: '1',
};

function getSelectedSite(){
  return sites.find(site => site[0] === state.selectedSiteId) || sites[0];
}

function siteNo(site){
  return `SITE-${String(Number(site[0]) + 20).padStart(4, '0')}`;
}

function bmsId(site){
  return Number(site[0]) % 2 === 0 ? 'BMS-210531-LG001' : 'BMS-210531-KO001';
}

function siteOptions(){
  return sites.map(site => `<option value="${site[0]}" ${site[0] === state.selectedSiteId ? 'selected' : ''}>${site[1]}</option>`).join('');
}

function selectSite(id){
  state.selectedSiteId = String(id);
  detailPage();
}


function statusClass(status){
  if(status === '정상') return 'good';
  if(status === '주의') return 'warn';
  if(status === '비정상' || status === '위험') return 'bad';
  return 'gray';
}
function scoreClass(score){
  const n = Number(score);
  if(Number.isNaN(n)) return 'gray';
  if(n >= 71) return 'bad';
  if(n >= 40) return 'warn';
  return 'good';
}
function setActive(page){
  navItems.forEach(n => n.classList.toggle('active', n.dataset.page === page));
}
function badge(text){ return `<span class="state-badge ${statusClass(text)}">${text}</span>`; }
function score(score){ return `<span class="score-badge ${scoreClass(score)}">${score}</span>`; }

function dashboard(){
  setActive('dashboard');
  content.innerHTML = `
  <div class="page">
    <div class="dashboard-grid">
      <div class="hero-card">
        <div class="hero-left"><div class="hero-icon">▦</div><div><div class="hero-title">설치 사이트 수</div><div class="hero-value">128</div></div></div>
        <div class="korea-map"></div>
      </div>
      <div class="hero-card">
        <div class="hero-left"><div class="hero-icon" style="background:linear-gradient(135deg,#e8fff7,#d9fbef); color:#008b83">♙</div><div><div class="hero-title">AI 진단 가능 사이트 수</div><div class="hero-value green">96</div></div></div>
        <div class="ai-chip-art"></div>
      </div>
      <div class="stat-split hero-card">
        <h3>정상 / 주의 / 비정상</h3>
        <div class="split-row">
          <div class="split-box"><div class="split-label green">정상</div><div class="split-num green">72</div></div>
          <div class="split-box"><div class="split-label orange">주의</div><div class="split-num orange">18</div></div>
          <div class="split-box"><div class="split-label red">비정상</div><div class="split-num red">6</div></div>
        </div>
      </div>
    </div>

    <div class="dash-main">
      <section class="panel">
        <div class="panel-title"><span class="mini-icon">▥</span>이상 점수 순위별 사이트 리스트</div>
        <div class="ranking-table">
          <table>
            <thead><tr><th>순위</th><th>사이트명</th><th>지역</th><th>제조사</th><th>이상 점수</th><th>상태</th></tr></thead>
            <tbody>
              ${sites.slice(0,6).map((s,i)=>`<tr class="clickable-row" onclick="selectSite('${s[0]}')"><td><b class="rank-num" style="color:${i<2?'#e11d48':i<4?'#f59e0b':'#0969e8'}">${i+1}</b></td><td><b>${s[1]}</b></td><td>${s[2]}</td><td>${s[4]}</td><td>${score(s[6])}</td><td>${badge(s[7])}</td></tr>`).join('')}
            </tbody>
          </table>
        </div>
        <div class="more-link" onclick="sitesPage()">전체 사이트 보기 <span>›</span></div>
      </section>
      <div class="side-stack">
        <section class="panel">
          <div class="panel-title"><span class="mini-icon">⚠</span>우선 점검 필요 사이트 요약</div>
          <div class="priority-list">
            <div class="priority-item clickable-row" onclick="selectSite('1')"><div class="rank-circle">1</div><div class="priority-name">영광 ESS 2호기</div><div class="priority-reason red">이상 점수 매우 높음 (93.7)</div><div class="chev">›</div></div>
            <div class="priority-item clickable-row" onclick="selectSite('2')"><div class="rank-circle r2">2</div><div class="priority-name">평택 ESS 1호기</div><div class="priority-reason orange">이상 점수 높음 (87.2)</div><div class="chev">›</div></div>
            <div class="priority-item clickable-row" onclick="selectSite('3')"><div class="rank-circle r3">3</div><div><div class="priority-name">군산 ESS 3호기</div><small>리스크 확산 가능, 모듈 8개</small></div><div class="priority-reason orange">이상 점수 상승 추세 (↑)</div><div class="chev">›</div></div>
          </div>
        </section>
        <section class="panel">
          <div class="panel-title"><span class="mini-icon">♧</span>데이터 수집 / AI 진단 상태 알림</div>
          <div class="alarm-list">
            <div class="alarm-item"><div class="alarm-icon blue">▤</div><div class="alarm-name">데이터 수집 누락 사이트</div><div class="alarm-value blue">3개 사이트</div><div class="chev">›</div></div>
            <div class="alarm-item"><div class="alarm-icon" style="color:#7c3aed">✺</div><div class="alarm-name">AI 진단 불가 사이트</div><div class="alarm-value" style="color:#7c3aed">29개 사이트</div><div class="chev">›</div></div>
            <div class="alarm-item"><div class="alarm-icon red">⚠</div><div class="alarm-name">최근 분석 실패 건수 <small>(최근 24시간)</small></div><div class="alarm-value red">2건</div><div class="chev">›</div></div>
            <div class="alarm-item"><div class="alarm-icon green">○</div><div class="alarm-name">마지막 분석 성공 시각</div><div class="alarm-value green">2025-05-19 10:20:15</div><div class="chev">›</div></div>
          </div>
        </section>
      </div>
    </div>
  </div>`;
}

function sitesPage(){
  setActive('sites');
  content.innerHTML = `
  <div class="page sites-layout">
    <section>
      <div class="page-heading"><h1>사이트 목록</h1><p>전체 사이트 현황 및 검색</p></div>
      <div class="filter-card">
        <div class="input">사이트명 검색 <span>⌕</span></div><div class="select">제조사 <span>⌄</span></div><div class="select">지역 <span>⌄</span></div><div class="select">설치 구역 <span>⌄</span></div><div class="select">진단 상태 <span>⌄</span></div><div class="select">가나다순 <span>⌄</span></div>
      </div>
      <div class="tabs"><button class="tab active">모두</button><button class="tab">제조사별</button><button class="tab">지역별</button><button class="tab">설치 구역별</button><button class="tab">진단 상태별</button></div>
      <div class="table-card">
        <table class="data-table"><thead><tr><th>번호</th><th>사이트명</th><th>지역</th><th>설치 구역</th><th>제조사</th><th>설치일</th><th>AI 진단 가능</th><th>최신 이상 점수</th><th>상태</th><th>최근 분석일</th><th>상세</th></tr></thead><tbody>
          ${sites.map((s)=>`<tr class="clickable-row" onclick="selectSite('${s[0]}')"><td>${s[0]}</td><td><b>${s[1]}</b></td><td>${s[2]}</td><td>${s[3]}</td><td>${s[4]}</td><td>${s[5]}</td><td>${Number(s[0])<7?'<span class="check">✓</span>':'<span class="dash">−</span>'}</td><td>${score(s[6])}</td><td>${badge(s[7])}</td><td>${s[8]}</td><td><button class="table-action" onclick="event.stopPropagation(); selectSite('${s[0]}')">상세 보기</button></td></tr>`).join('')}
        </tbody></table>
        <div class="pagination"><b>총 128개 중 24개 표시</b><div class="pages"><button class="page-btn">«</button><button class="page-btn">‹</button><button class="page-btn active">1</button><button class="page-btn">2</button><button class="page-btn">3</button><button class="page-btn">›</button><button class="page-btn">»</button></div><div class="select" style="height:40px">24개 / 페이지 <span>⌄</span></div></div>
      </div>
    </section>
    <aside>
      <div class="summary-card"><h3>목록 요약</h3><div class="summary-grid"><div class="summary-box"><span class="mini-icon">▦</span><div><small>전체 사이트</small><div class="big">128개</div></div></div><div class="summary-box"><span class="mini-icon">◎</span><div><small>표시 중</small><div class="big">24개</div></div></div><div class="summary-box"><span class="mini-icon">♙</span><div><small>AI 진단 가능</small><div class="big green">96개</div></div></div><div class="summary-box"><span class="mini-icon">⚠</span><div><small>비정상</small><div class="big red">6개</div></div></div></div></div>
      <div class="summary-card"><h3>빠른 필터</h3><div class="quick-buttons"><button class="bad">비정상만</button><button class="warn">주의 이상</button><button class="purple">진단 불가</button><button>데이터 없음</button><button class="blue-btn">최근 설치</button><button class="blue-btn">점수 높은 순</button></div></div>
      <div class="summary-card"><h3>추천 정렬</h3><div class="sort-list"><button class="sort-item">이상치 점수 순 <span>›</span></button><button class="sort-item">최근 분석일 순 <span>›</span></button><button class="sort-item">가나다순 <span>›</span></button></div></div>
    </aside>
  </div>`;
}

function detailPage(){
  setActive('detail');
  const selected = getSelectedSite();
  const selectedSiteNo = siteNo(selected);
  const selectedBmsId = bmsId(selected);
  content.innerHTML = `
  <div class="page detail-page">
    <section class="detail-left">
      <div class="breadcrumb">사이트 목록 <span>›</span> ${selected[1]} <span>›</span> Bank 01 <span>›</span> Rack 03 <span>›</span> String 02 <span>›</span> Module 05</div>
      <div class="detail-title detail-title-row"><div class="site-icon">▦</div><div><h1>${selected[1]} <span>›</span> Bank 01 <span>›</span> Rack 03 <span>›</span> String 02 <span>›</span> Module 05 <em class="level-tag">Module 레벨</em></h1><p class="site-subline">${selected[2]} · ${selected[4]} · ${selectedSiteNo}</p></div><label class="site-picker"><span>사이트 선택</span><select onchange="selectSite(this.value)">${siteOptions()}</select></label></div>
      <div class="level-buttons"><button>BANK</button><button>RACK</button><button>STRING</button><button class="active">MODULE</button></div>
      <div class="module-grid">
        <div class="info-card"><div class="card-title"><span class="mini-icon">ⓘ</span>Module 기본 정보</div><div class="module-graphic">▥</div><dl><dt>사이트</dt><dd>${selected[1]}</dd><dt>뱅크</dt><dd>Bank 01</dd><dt>랙</dt><dd>Rack 03</dd><dt>스트링</dt><dd>String 02</dd><dt>모듈</dt><dd>Module 05</dd><dt>제조사 / 모델</dt><dd>${selected[4]} / ESS-MODULE</dd><dt>정격 용량</dt><dd>17.0 kWh</dd><dt>설치 일자</dt><dd>2024.04.12</dd><dt>보증 만료</dt><dd>2034.04.11</dd></dl></div>
        <div class="warn-card"><div class="card-title"><span class="mini-icon">⌁</span>진단 상태</div><div class="alert-symbol">⚠</div><h2>주의</h2><p>위험 Cell 3개가 감지되었습니다.<br>조치가 필요한 상태입니다.</p></div>
        <div class="small-card"><div class="card-title"><span class="mini-icon">↗</span>최대 이상 점수</div><div class="metric-value orange">92 <span>/ 100</span></div><p>발생 위치: Cell 07</p></div>
        <div class="small-card"><div class="card-title"><span class="mini-icon">◷</span>최근 분석 시각</div><div class="metric-value" style="font-size:28px">2025.05.21&nbsp; 09:15:23</div><p>분석 주기: 15분 &nbsp; ⟳</p></div>
      </div>
      <div class="two-col">
        <div class="wide-card"><div class="card-title"><span class="mini-icon">▧</span>Cell 상태 지도 <small style="color:#748199">(20 Cells)</small></div><div class="legend"><span><i class="dot good"></i>정상 (0-39)</span><span><i class="dot warn"></i>주의 (40-79)</span><span><i class="dot bad"></i>위험 (80-100)</span></div><div class="cell-map">${cells.map((v,i)=>cellBox(i+1,v)).join('')}</div></div>
        <div>
          <div class="wide-card"><div class="card-title"><span class="mini-icon">☑</span>위험 Cell 목록 (3)<button class="secondary" style="margin-left:auto;height:36px">전체 Cell 보기 ›</button></div>${riskTable()}</div>
          <div class="wide-card"><div class="card-title"><span class="mini-icon">⌁</span>Module 점수 추이 <button class="secondary" style="margin-left:auto;height:36px">최근 7일⌄</button></div>${lineChart()}</div>
        </div>
      </div>
      <div class="two-col">
        <div class="wide-card"><div class="card-title"><span class="mini-icon">▤</span>Cell 상세 정보 <small class="state-badge bad">위험</small> <b>Cell 07 선택됨</b></div><dl class="detail-dl" style="display:grid;grid-template-columns:110px 1fr 110px 1fr 1.7fr;gap:12px;margin:0"><dt>이상 점수</dt><dd class="red"><b>92 /100</b></dd><dt>전압 편차</dt><dd><b>+128 mV</b></dd><dd rowspan="4">${miniTrend()}</dd><dt>상태</dt><dd>${badge('위험')}</dd><dt>내부 저항</dt><dd><b>1.85 mΩ</b></dd><dt>전압</dt><dd><b>3.042 V</b></dd><dt>용량</dt><dd><b>96.2 Ah</b></dd><dt>온도</dt><dd><b>48.7 ℃</b></dd><dt>SOC</dt><dd><b>78 %</b></dd></dl></div>
        <div class="wide-card"><div class="card-title"><span class="mini-icon">⊙</span>운영 권고</div><div class="recommend-item"><span class="red">⚠</span><div><b>Cell 07 (점수 92)는 과열 징후가 뚜렷합니다.</b><br><small>모듈 온도 모니터링 및 냉각 상태를 점검해 주세요.</small></div><button class="action-btn bad">즉시 점검</button></div><div class="recommend-item"><span class="orange">⚠</span><div><b>Cell 13, 19는 용량 저하 또는 내부 저항 상승이 의심됩니다.</b><br><small>정기 점검 시 전압/저항 측정을 권장합니다.</small></div><button class="action-btn warn">정기 점검</button></div><div class="recommend-item"><span class="blue">ⓘ</span><div><b>전체 Module 점수가 최근 7일간 상승 추세를 보입니다.</b><br><small>지속 모니터링으로 이상 징후를 조기 대응하세요.</small></div><button class="action-btn info">지속 모니터링</button></div></div>
      </div>
    </section>
    <aside class="right-drawer">
      <div class="drawer-head"><div><h2>Module 02 상세 정보 ${badge('비정상')}</h2><div class="breadcrumb" style="margin:0">Bank 01 <span>›</span> Rack 03 <span>›</span> String 02 <span>›</span> Module 02</div></div><div class="close">×</div></div>
      <div class="drawer-score"><div><b>종합 점수</b><strong class="red">54.2</strong><small>/100</small></div><div><b>위험 Cell 수</b><strong class="red">3</strong><small>/18</small></div><div><b>평균 Cell 점수</b><strong class="red">37.1</strong></div><div><b>상태</b><strong class="red" style="font-size:17px">비정상</strong></div></div>
      <div class="drawer-info"><div class="card-title">Module 기본 정보</div><dl><dt>전압</dt><dd>74.1 V</dd><dt>전류</dt><dd>38.2 A</dd><dt>온도</dt><dd>33.6 ℃</dd><dt>설치 위치</dt><dd>Rack 03 - String 02 - Module 02</dd><dt>제조사</dt><dd>삼성SDI</dd><dt>펌웨어</dt><dd>v1.3.2</dd></dl></div>
      <div class="mini-heatmap"><div class="card-title">Cell 수준 점수 (Heatmap)</div><div class="mini-cells">${smallCells.map((v,i)=>miniCell(i+1,v)).join('')}</div><div class="bar-legend"></div><div style="display:flex;justify-content:space-between;font-size:12px;color:#65748a;font-weight:800"><span>0~20</span><span>20~40</span><span>40~60</span><span>60~80</span><span>80~100</span></div></div>
      <div class="wide-card" style="box-shadow:none"><div class="card-title">운영 권고</div><div class="recommend-item"><span class="red">●</span><div><b>위험 Cell에 대한 정밀 점검 필요</b><br><small>- 셀 불균형 및 내부 저항 증가 가능성</small></div></div><div class="recommend-item"><span class="orange">▲</span><div><b>모듈 온도 주의 수준</b><br><small>- 냉각 시스템 상태 확인 및 환경 온도 관리 권장</small></div></div><div class="recommend-item"><span class="blue">●</span><div><b>정기 점검 주기 단축 권장</b><br><small>- 다음 점검을 3일 이내로 설정하세요.</small></div></div></div>
      <div class="drawer-actions"><button class="primary">모듈 상세 리포트 보기 ⎋</button><button class="secondary">닫기</button></div>
    </aside>
  </div>`;
}

function cellBox(i,v){
  const cls = v>=80?'bad':v>=40?'warn':'good';
  const label = v>=80?'위험':v>=40?'주의':'정상';
  return `<div class="cell ${cls}"><b>Cell ${String(i).padStart(2,'0')}</b><span class="badge ${cls}">${label}</span><strong class="${cls==='bad'?'red':cls==='warn'?'orange':'green'}">${v}</strong><small>/100</small></div>`;
}
function miniCell(i,v){
  const cls = v>=80?'bad':v>=40?'warn':'good';
  return `<div class="mini-cell cell ${cls}"><span>Cell ${String(i).padStart(2,'0')}</span><strong>${v}</strong></div>`;
}
function riskTable(){
  return `<table class="risk-table"><thead><tr><th>순위</th><th>Cell</th><th>이상 점수</th><th>상태</th><th>주요 이상 유형</th></tr></thead><tbody><tr><td>1</td><td><b>Cell 07</b></td><td><b class="red">92 /100</b></td><td>${badge('위험')}</td><td>과열 / 전압 편차</td></tr><tr><td>2</td><td><b>Cell 13</b></td><td><b class="orange">41 /100</b></td><td>${badge('주의')}</td><td>용량 저하 징후</td></tr><tr><td>3</td><td><b>Cell 19</b></td><td><b class="orange">48 /100</b></td><td>${badge('주의')}</td><td>내부 저항 상승</td></tr></tbody></table>`;
}
function lineChart(){
  return `<div class="line-chart"><svg viewBox="0 0 520 170" preserveAspectRatio="none"><defs><linearGradient id="g" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#0b6fea" stop-opacity=".16"/><stop offset="1" stop-color="#0b6fea" stop-opacity="0"/></linearGradient></defs><g stroke="#e4ebf4" stroke-width="1"><line x1="35" y1="25" x2="500" y2="25"/><line x1="35" y1="60" x2="500" y2="60"/><line x1="35" y1="95" x2="500" y2="95"/><line x1="35" y1="130" x2="500" y2="130"/></g><path d="M55 110 L125 105 L195 88 L265 75 L335 57 L405 46 L475 52 L475 140 L55 140 Z" fill="url(#g)"/><path d="M55 110 L125 105 L195 88 L265 75 L335 57 L405 46 L475 52" fill="none" stroke="#0b6fea" stroke-width="4" stroke-linecap="round"/><g fill="#fff" stroke="#0b6fea" stroke-width="3"><circle cx="55" cy="110" r="5"/><circle cx="125" cy="105" r="5"/><circle cx="195" cy="88" r="5"/><circle cx="265" cy="75" r="5"/><circle cx="335" cy="57" r="5"/><circle cx="405" cy="46" r="5"/><circle cx="475" cy="52" r="5"/></g><g fill="#556274" font-size="13" font-weight="700"><text x="24" y="28">100</text><text x="28" y="63">75</text><text x="28" y="98">50</text><text x="28" y="133">25</text><text x="54" y="160">05/15</text><text x="124" y="160">05/16</text><text x="194" y="160">05/17</text><text x="264" y="160">05/18</text><text x="334" y="160">05/19</text><text x="404" y="160">05/20</text><text x="474" y="160">05/21</text></g><g fill="#0b1b36" font-size="15" font-weight="800"><text x="52" y="96">32</text><text x="122" y="91">35</text><text x="192" y="74">41</text><text x="262" y="61">48</text><text x="332" y="43">55</text><text x="402" y="32">63</text><text x="472" y="38" fill="#f59e0b">58</text></g></svg></div>`;
}
function miniTrend(){
  return `<svg viewBox="0 0 260 100" style="width:100%;height:100px"><g stroke="#e4ebf4"><line x1="15" y1="20" x2="245" y2="20"/><line x1="15" y1="50" x2="245" y2="50"/><line x1="15" y1="80" x2="245" y2="80"/></g><path d="M20 75 L55 68 L90 55 L125 42 L160 61 L195 57 L235 49" fill="none" stroke="#0b6fea" stroke-width="3"/><path d="M20 70 L55 62 L90 49 L125 35 L160 30 L195 33 L235 24" fill="none" stroke="#ef4444" stroke-width="3"/><g fill="#667085" font-size="11"><text x="18" y="96">09:00</text><text x="80" y="96">15:00</text><text x="142" y="96">21:00</text><text x="202" y="96">09:00</text></g></svg>`;
}

function empty(title){
  content.innerHTML = `<div class="empty-page"><div class="empty-card"><h1>${title}</h1><p>대표 보고용 1차 시안에서는 대시보드, 사이트 목록, 사이트 상세 화면을 우선 구현했습니다.</p></div></div>`;
}
navItems.forEach(item=>item.addEventListener('click',()=>{
  const page = item.dataset.page;
  if(page==='dashboard') dashboard();
  else if(page==='sites') sitesPage();
  else if(page==='detail') detailPage();
  else { setActive(page); empty(item.innerText.trim()); }
}));
window.sitesPage = sitesPage;
window.detailPage = detailPage;
window.selectSite = selectSite;
dashboard();
