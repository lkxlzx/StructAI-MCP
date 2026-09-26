# MIDAS NX Open API — 端点总表

- 来源：`MIDAS-API-main/docs/manual`（27 章）+ `docs/plugin`
- 端点数：**392**（去重后）／505（含跨章重复）
- 生成方式：`merge_registry.py`，由 `part-*.json` 合并

> 本表字段名逐字取自 MIDAS 官方 JSON Manual，**不含实机观测结论**。

## 分类统计

| 维度 | 分布 |
| --- | --- |
| category | `db` 229 · `design` 135 · `doc` 11 · `ope` 20 · `post` 98 · `view` 12 |
| method | `DELETE` 297 · `GET` 312 · `POST` 461 · `PUT` 305 |
| resource | `design` 148 · `result` 96 · `load` 39 · `moving_load` 29 · `misc` 24 · `dynamic_load` 17 · `boundary` 14 · `material` 13 · `section` 13 · `analysis` 12 · `element` 12 · `project` 11 · `link` 11 · `load_combination` 11 · `load_case` 9 · `construction_stage` 7 · `bridge` 7 · `view` 7 · `tendon` 6 · `pushover` 6 · `spring` 5 · `structure_type` 2 · `thickness` 2 · `node` 2 · `unit` 1 · `group` 1 |

## 跨章重复端点

| 端点 | 出现章节 |
| --- | --- |
| `/DESIGN/RC/KDS-41-20-2022/TABLE` | 26, 26, 26 |
| `/DESIGN/SRC/AIK-SRC2K/TABLE` | 27, 27 |
| `/ope/GSBG` | 17, 15 |
| `/post/TABLE` | 18, 18, 18, 18, 18, 18, 18, 18, 18, 18, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 22, 22, 22, 22, 22, 22, 22, 22, 22, 23, 23, 23, 23, 23, 23, 23, 23 |
| `/post/TEXT` | 22, 22, 22, 22, 22, 22, 22, 22, 22, 22 |
| `/view/RESULTGRAPHIC` | 16, 22, 22, 22, 22, 22 |

## 端点明细


### 01. DOC （11 个）

来源：`docs/manual/01_DOC.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/doc/NEW` | POST | `project` | create | New Project — 새 프로젝트 생성 | 1 |
| `/doc/OPEN` | POST | `project` | create | Open Project — 기존 프로젝트 열기 | 1 |
| `/doc/CLOSE` | POST | `project` | create | Close Project — 현재 열린 프로젝트 닫기 | 1 |
| `/doc/SAVE` | POST | `project` | create | Save — 현재 프로젝트 저장 | 1 |
| `/doc/SAVEAS` | POST | `project` | create | Save As — 다른 경로에 다른 이름으로 저장 | 1 |
| `/doc/STAGAS` | POST | `construction_stage` | create | Save Current Stage As — 현재 시공 스테이지를 별도 파일로 저장 | 2 |
| `/doc/IMPORT` | POST | `project` | create | Import to JSON — JSON 파일을 현재 프로젝트로 불러오기 | 1 |
| `/doc/IMPORTMXT` | POST | `project` | create | Import to mct/mgt — MCT(Civil NX)/MGT(Gen NX) 파일 불러오기 | 1 |
| `/doc/EXPORT` | POST | `project` | create | Export to JSON — 현재 프로젝트를 JSON 파일로 내보내기 | 1 |
| `/doc/EXPORTMXT` | POST | `project` | create | Export to mct/mgt — MCT(Civil NX)/MGT(Gen NX) 파일로 내보내기 | 1 |
| `/doc/ANAL` | POST | `analysis` | execute | Perform Analysis — 해석 실행(일반 선형/비선형, Pushover) | 2 |

### 02. DB — Project / Structure （15 个）

来源：`docs/manual/02_DB_Project_Structure.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/PJCF` | POST, GET, PUT, DELETE | `project` | create, read, update, delete | Project Information — 프로젝트 정보(프로젝트명·리비전·담당자·검토자·승인자·코멘트) 설정/조회 | 20 |
| `/db/UNIT` | GET, PUT | `unit` | read, update | Unit System — 단위계(힘·길이·열·온도) 설정/조회 | 4 |
| `/db/STYP` | GET, PUT | `structure_type` | read, update | Structure Type — 구조 타입(3-D/평면/Constraint RZ)·질량 타입·자중 변환 설정/조회 | 10 |
| `/db/STYP-M1` | GET, PUT, DELETE | `structure_type` | read, update, delete | Structure Type (Hyper-S) — Hyper-S(MEC) 솔버용 구조 타입·질량 제어(MASS_CONTROL) 설정/조회/삭제 | 10 |
| `/db/GRUP` | POST, GET, PUT | `group` | create, read, update | Structure Group — 구조 그룹(그룹명·평면 타입·노드/요소 목록) 생성/조회/수정 | 4 |
| `/db/BNGR` | POST, GET, PUT | `boundary` | create, read, update | Boundary Group — 경계 그룹(합성단면 Creep/Shrinkage 자동 그룹 포함) 생성/조회/수정 | 2 |
| `/db/LDGR` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Load Group — 하중 그룹 생성/조회/수정/삭제 | 1 |
| `/db/TDGR` | POST, GET, PUT, DELETE | `tendon` | create, read, update, delete | Tendon Group — 텐던 그룹 생성/조회/수정/삭제 | 1 |
| `/db/NPLN` | POST, GET, PUT, DELETE | `misc` | create, read, update, delete | Named Plane — 명명 평면(3 Points / X-Y / X-Z / Y-Z) 생성/조회/수정/삭제 | 5 |
| `/db/CO_M` | GET, PUT | `material` | read, update | Material Color — 재료 ID별 표시 색상(Wire Frame / Hidden Fill / Hidden Edge / 투명도) 설정/조회 | 11 |
| `/db/CO_S` | GET, PUT | `section` | read, update | Section Color — 단면 ID별 표시 색상(Wire Frame / Hidden Fill / Hidden Edge / 투명도) 설정/조회 | 3 |
| `/db/CO_T` | GET, PUT | `thickness` | read, update | Thickness Color — 두께 ID별 표시 색상(Wire Frame / Hidden Fill / Hidden Edge / 투명도) 설정/조회 | 3 |
| `/db/CO_F` | GET, PUT | `load` | read, update | Floor Load Color — 바닥하중 타입별 표시 색상(Wire Frame / Hidden Fill / Hidden Edge / Blending) 설정/조회 | 12 |
| `/db/SPAN` | POST, GET, PUT, DELETE | `bridge` | create, read, update, delete | Span Information — 교량 스팬 정보(스팬명·Exact Span·방향·요소/지지점 목록) 설정/조회/수정/삭제 | 7 |
| `/db/STOR` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Story Data — 층 데이터(층명·표고·바닥 다이아프램·풍/지진 편심·비틀림 증폭계수) 설정/조회/수정/삭제 | 15 |

### 03. DB — Node / Element （6 个）

来源：`docs/manual/03_DB_Node_Element.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/NODE` | POST, GET, PUT, DELETE | `node` | create, read, update, delete | Node — 절점(노드)의 전체 좌표계(Global) 좌표 X/Y/Z 정의·조회·수정·삭제 | 3 |
| `/db/ELEM` | POST, GET, PUT, DELETE | `element` | create, read, update, delete | Element — 요소(BEAM/TRUSS/TENSTR/COMPTR/PLATE/WALL/PLSTRS/PLSTRN/AXISYM/SOLID) 생성·조회·수정·삭제 | 14 |
| `/db/SKEW` | POST, GET, PUT, DELETE | `node` | create, read, update, delete | Node Local Axis — 절점 국부 좌표계(Angle / 3 Points / Vector / Line Vector 4방식) 생성·조회·수정·삭제 | 31 |
| `/db/MADO` | POST, GET, PUT, DELETE | `misc` | create, read, update, delete | Define Domain — 메시 Main Domain(Plane Stress/Plate/Plane Strain/Axisymmetric) 정의·조회·수정·삭제 | 5 |
| `/db/SBDO` | POST, GET, PUT, DELETE | `misc` | create, read, update, delete | Define Sub-Domain — 도메인 내 Sub-Domain(철근 방향·부재 유형·기본 철근 배근) 정의·조회·수정·삭제 (GEN NX / CIVIL NX 파라미터 상이) | 22 |
| `/db/DOEL` | POST, GET, PUT, DELETE | `misc` | create, read, update, delete | Domain-Element — 특정 요소를 Main-Domain 또는 Sub-Domain에 할당·조회·수정·삭제 | 3 |

### 04. DB — Properties （32 个）

来源：`docs/manual/04_DB_Properties.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/MATL` | POST, GET, PUT, DELETE | `material` | create, read, update, delete | Material Properties — 재료 특성을 정의합니다. DB(표준), Isotropic(등방성), Orthotropic(직교이방성) 3가지 타입을 지원합니다. | 23 |
| `/db/MATL-M1` | POST, GET, PUT, DELETE | `material` | create, read, update, delete | Material Properties (Hyper-S) — Hyper-S 솔버 전용 재료 특성 정의. 동일한 /db/MATL 엔드포인트를 사용하나 Hyper-S 전용 파라미터를 추가 지원합니다. | 0 |
| `/db/IMFM` | POST, GET, PUT, DELETE | `material` | create, read, update, delete | Inelastic Material Properties for Fiber Model — 섬유 모델(Fiber Model) 비선형 재료 특성을 할당합니다. | 4 |
| `/db/IMFM-M1` | POST, GET, PUT, DELETE | `material` | create, read, update, delete | Inelastic Material Link for Auto Generation (Hyper-S) — Hyper-S 전용 비선형 재료 자동 생성 링크. | 0 |
| `/db/TDMF` | POST, GET, PUT, DELETE | `material` | create, read, update, delete | Time Dependent Material – User Defined — 크리프/건조수축/이완 사용자 정의 함수를 정의합니다. | 9 |
| `/db/TDMT` | POST, GET, PUT, DELETE | `material` | create, read, update, delete | Time Dependent Material – Creep/Shrinkage — 코드 기반 크리프/건조수축 재료 특성을 정의합니다. CEB-FIP(2010/1990/1978), ACI, KDS … | 10 |
| `/db/TDME` | POST, GET, PUT, DELETE | `material` | create, read, update, delete | Time Dependent Material – Compressive Strength — 콘크리트 압축강도의 시간 의존성을 정의합니다. | 23 |
| `/db/EDMP` | POST, GET, PUT, DELETE | `element` | create, read, update, delete | Change Property — 요소별 시간 의존 재료 특성(공칭 크기 또는 체적/표면적 비)를 변경합니다. | 2 |
| `/db/TMAT` | POST, GET, PUT, DELETE | `material` | create, read, update, delete | Time Dependent Material Link — 재료에 시간 의존 특성(크리프/건조수축 + 압축강도)을 링크합니다. | 2 |
| `/db/EPMT` | POST, GET, PUT, DELETE | `material` | create, read, update, delete | Plastic Material — 소성 재료 모델을 정의합니다. Tresca, Von-Mises, Mohr-Coulomb, Drucker-Prager, Masonry, Concrete Dama… | 34 |
| `/db/EPMT-M1` | POST, GET, PUT, DELETE | `material` | create, read, update, delete | Plastic Material (Hyper-S) — Hyper-S 전용 소성 재료 모델. | 0 |
| `/db/SECT` | POST, GET, PUT, DELETE | `section` | create, read, update, delete | Section Properties — 단면 특성을 정의합니다. SECTTYPE 값에 따라 DB/User, Value, SRC, Combined, PSC, Tapered, Composite, S… | 33 |
| `/db/THIK` | POST, GET, PUT, DELETE | `thickness` | create, read, update, delete | Thickness — 판(Plate/Wall) 요소의 두께를 정의합니다. Value와 Stiffened(보강판) 4가지 서브타입을 지원합니다. | 16 |
| `/db/TSGR` | POST, GET, PUT, DELETE | `section` | create, read, update, delete | Tapered Group — 변단면 그룹을 정의합니다. 선형(Linear) 또는 다항식(Polynomial) 단면 변화를 설정합니다. | 10 |
| `/db/SECF` | POST, GET, PUT, DELETE | `section` | create, read, update, delete | Section Manager – Stiffness — 단면 강성 수정 계수를 할당합니다. 건설 단계, 지진, 설계 등 각 그룹별 강성 배율을 설정합니다. | 21 |
| `/db/RPSC` | POST, GET, PUT, DELETE | `section` | create, read, update, delete | Section Manager – Reinforcements — PSC/RC 단면 철근 배근 데이터를 설정합니다. | 34 |
| `/db/STRPSSM` | POST, GET, PUT, DELETE | `section` | create, read, update, delete | Section Manager – Stress Points — 단면 추가 응력 계산 점을 정의합니다. | 7 |
| `/db/PSSF` | POST, GET, PUT, DELETE | `section` | create, read, update, delete | Section Manager – Plate Stiffness Scale Factor — 판 요소 강성 수정 계수를 설정합니다. | 11 |
| `/db/VBEM` | POST, GET, PUT, DELETE | `section` | create, read, update, delete | Virtual Beam — 결과력 계산을 위한 가상 보 단면을 정의합니다. 가상 단면 2개로 구성됩니다. | 2 |
| `/db/VSEC` | POST, GET, PUT, DELETE | `section` | create, read, update, delete | Virtual Section — 결과력 계산용 가상 단면을 정의합니다. 절점 목록과 법선 벡터를 사용합니다. | 10 |
| `/db/EWSF` | POST, GET, PUT, DELETE | `section` | create, read, update, delete | Effective Width Scale Factor — 유효 폭 축소 계수를 단면에 할당합니다. | 10 |
| `/db/IEHC` | POST, GET, PUT, DELETE | `misc` | create, read, update, delete | Inelastic Hinge Control Data — 비선형 힌지 제어 데이터(섬유 분할 수 등)를 설정합니다. | 17 |
| `/db/IEHG` | POST, GET, PUT, DELETE | `element` | create, read, update, delete | Assign Inelastic Hinge Properties — 비선형 힌지 속성(Inelastic Hinge Property + Fiber Division)을 요소에 할당합니다. | 2 |
| `/db/IEHG-BEAM-M1` | POST, GET, PUT, DELETE | `element` | create, read, update, delete | Assign Inelastic Hinges – Beam (Hyper-S) — Hyper-S 전용 보 요소 비선형 힌지 할당. | 0 |
| `/db/IEHG-TRUSS-M1` | POST, GET, PUT, DELETE | `element` | create, read, update, delete | Assign Inelastic Hinges – Truss (Hyper-S) — Hyper-S 전용 트러스 요소 비선형 힌지 할당. | 0 |
| `/db/IEHG-GL-M1` | POST, GET, PUT, DELETE | `element` | create, read, update, delete | Assign Inelastic Hinges – General Link (Hyper-S) — Hyper-S 전용 일반 링크 비선형 힌지 할당. | 0 |
| `/db/IEHG-PSS-M1` | POST, GET, PUT, DELETE | `element` | create, read, update, delete | Assign Inelastic Hinges – Point Spring Support (Hyper-S) — Hyper-S 전용 점 스프링 지지 비선형 힌지 할당. | 0 |
| `/db/FIMP` | POST, GET, PUT, DELETE | `material` | create, read, update, delete | Inelastic Material Properties — 섬유 모델 비선형 재료를 정의합니다. 콘크리트(Kent&Park, Mander 등)와 강재(Bilinear, Menegotto-Pint… | 14 |
| `/db/FIBR` | POST, GET, PUT, DELETE | `section` | create, read, update, delete | Fiber Division of Section — 단면을 섬유(Fiber)로 분할하고 비선형 재료를 할당합니다. | 21 |
| `/db/GRDP` | POST, GET, PUT, DELETE | `misc` | create, read, update, delete | Group Damping — 재료 그룹, 구조 그룹, 경계 그룹별 감쇠비를 설정합니다. | 37 |
| `/db/ESSF` | POST, GET, PUT, DELETE | `element` | create, read, update, delete | Element Stiffness Scale Factor — 요소별 단면 강성 수정 계수를 직접 할당합니다. | 11 |
| `/db/MATD` | GET, PUT | `material` | read, update | Modify Concrete Materials — 기존 콘크리트 재료(TYPE:"CONC")의 설계값(강도)·철근 등급을 조회·수정합니다. /db/MATL과 달리 GET/PUT만 지원합니다. | 20 |

### 05. DB — Boundary （24 个）

来源：`docs/manual/05_DB_Boundary.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/CONS` | POST, GET, PUT, DELETE | `boundary` | create, read, update, delete | Constraint Support — 절점에 지지조건(고정·핀·롤러 등)을 배정 | 4 |
| `/db/NSPR` | POST, GET, PUT, DELETE | `spring` | create, read, update, delete | Point Spring — 절점에 점 스프링 배정 (Linear / Compression-Only / Tension-Only / Multi-Linear) | 15 |
| `/db/GSTP` | POST, GET, PUT, DELETE | `spring` | create, read, update, delete | Define General Spring Type — 전체 6×6 강성·질량·감쇠 행렬을 사용자 정의하는 일반 스프링 타입 정의 | 7 |
| `/db/GSPR` | POST, GET, PUT, DELETE | `spring` | create, read, update, delete | Assign General Spring Supports — GSTP에서 정의한 일반 스프링 타입을 절점에 배정 | 4 |
| `/db/SSPS` | POST, GET, PUT, DELETE | `spring` | create, read, update, delete | Surface Spring — 요소(프레임·판·솔리드)의 면 또는 모서리에 지반반력계수 기반 스프링 배정 | 8 |
| `/db/ELNK` | POST, GET, PUT, DELETE | `link` | create, read, update, delete | Elastic Link — 두 절점 사이에 탄성 링크 배정 (LINK 타입 7가지) | 12 |
| `/db/RIGD` | POST, GET, PUT, DELETE | `link` | create, read, update, delete | Rigid Link — 마스터 절점과 다수의 슬레이브 절점 사이에 강체 링크 배정 | 5 |
| `/db/NLLP` | POST, GET, PUT, DELETE | `link` | create, read, update, delete | General Link Properties — 일반 링크(General Link)에 사용할 비선형 속성 정의 | 13 |
| `/db/NLNK` | POST, GET, PUT, DELETE | `link` | create, read, update, delete | General Link — NLLP에서 정의한 일반 링크 속성을 두 절점 사이에 배정 (요소계/전역계 3가지 방향 지정) | 11 |
| `/db/NLNK-M1` | POST, GET, PUT, DELETE | `link` | create, read, update, delete | General Link (Hyper-S) — Hyper-S 솔버 전용 일반 링크 배정 | 10 |
| `/db/CGLP` | POST, GET, PUT, DELETE | `link` | create, read, update, delete | Change General Link Property — 특정 일반 링크 요소의 속성을 다른 NLLP 속성으로 변경 | 3 |
| `/db/FRLS` | POST, GET, PUT, DELETE | `boundary` | create, read, update, delete | Beam End Release — 보 요소의 단부 자유도를 해제 | 8 |
| `/db/OFFS` | POST, GET, PUT, DELETE | `boundary` | create, read, update, delete | Beam End Offsets — 보 요소 단부에 편심(오프셋) 적용 (전역/요소 좌표계) | 10 |
| `/db/PRLS` | POST, GET, PUT, DELETE | `boundary` | create, read, update, delete | Plate End Release — 판 요소 각 절점 위치의 자유도를 해제 | 7 |
| `/db/MLFC` | POST, GET, PUT, DELETE | `misc` | create, read, update, delete | Force-Deformation Function — Elastic Link(MULTILINEAR) 또는 General Link(FORCE 타입)에서 참조하는 비선형 힘-변위 함수 정의 | 7 |
| `/db/SDVI` | POST, GET, PUT, DELETE | `link` | create, read, update, delete | Seismic Device – Viscous/Oil Damper — 내진용 점성 댐퍼·오일 댐퍼 물성 정의 | 25 |
| `/db/SDVE` | POST, GET, PUT, DELETE | `link` | create, read, update, delete | Seismic Device – Viscoelastic Damper — 점탄성 댐퍼 물성 정의 | 17 |
| `/db/SDST` | POST, GET, PUT, DELETE | `link` | create, read, update, delete | Seismic Device – Steel Damper — 강재 댐퍼 물성 정의 | 11 |
| `/db/SDHY` | POST, GET, PUT, DELETE | `link` | create, read, update, delete | Seismic Device – Hysteretic Isolator (MSS) — 이력형 지진격리장치(다중 전단 스프링 모델) 물성 정의 | 11 |
| `/db/SDIS` | POST, GET, PUT, DELETE | `link` | create, read, update, delete | Seismic Device – Isolator (MSS) — MSS 기반 지진격리장치(납고무 LRB / 천연고무 NRB / 미끄럼 SLD) 물성 정의 | 25 |
| `/db/MCON` | POST, GET, PUT, DELETE | `boundary` | create, read, update, delete | Linear Constraints — 절점 간 선형 종속 구속조건(등변위·가중 변위) 설정 | 10 |
| `/db/PZEF` | POST, GET, PUT | `boundary` | create, read, update | Panel Zone Effects — 보-기둥 접합부의 패널 존(Panel Zone) 변형 효과 설정 | 3 |
| `/db/CLDR` | POST, GET, PUT | `boundary` | create, read, update | Define Constraints Label Direction — 구속조건 레이블의 표시 방향을 절점별로 지정 | 1 |
| `/db/DRLS` | POST, GET, PUT, DELETE | `boundary` | create, read, update, delete | Diaphragm Disconnect — 다이어프램에서 특정 절점을 제외(해제) | 1 |

### 17. DB — Bridge Specialization （5 个）

来源：`docs/manual/17_DB_Bridge.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/GSBG` | POST, GET, PUT, DELETE | `bridge` | create, read, update, delete | Bridge Girder Diagrams — 교량 거더(Bridge Girder) 요소 그룹에 대한 결과 다이어그램(보 응력 또는 보 부재력/모멘트) 정의 | 10 |
| `/db/GCMB` | POST, GET, PUT, DELETE | `bridge` | create, read, update, delete | General Camber Control — 시공단계 그룹별 캠버(Camber) 기준(방향·시작점 0 옵션) 정의 | 4 |
| `/db/CAMB` | POST, GET, PUT, DELETE | `bridge` | create, read, update, delete | FCM Camber Control — FCM(Free Cantilever Method) 교량의 캠버 제어(거더 요소 그룹·지점 노드 그룹·키 세그먼트 요소 그룹) 설정 | 3 |
| `/db/ULFC` | POST, GET, PUT, DELETE | `bridge` | create, read, update, delete | Cable Control – Unknown Load Factor Constraints — 케이블 교량 미지하중계수(Unknown Load Factor) 해석용 제약조건 정의 (반력·변위·트러스… | 13 |
| `/ope/GSBG` | POST | `bridge` | execute | Bridge Girder Diagram Image Generation — /db/GSBG로 정의한 거더 다이어그램(응력 또는 부재력)을 지정 시공단계 구간에 대해 이미지 파일(bmp/jpg/e… | 16 |

### 06. DB — Static Loads （21 个）

来源：`docs/manual/06_DB_Static_Loads.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/STLD` | POST, GET, PUT, DELETE | `load_case` | create, read, update, delete | Static Load Cases — 정적 하중 케이스(Load Case)를 정의합니다. 이후 모든 하중 데이터는 여기서 정의된 `NAME`(load case name)을 참조합니다. | 4 |
| `/db/BODF` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Self-Weight — 자중(Self-Weight)을 지정된 하중 케이스에 적용합니다. | 3 |
| `/db/CNLD` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Nodal Loads — 노드에 집중 힘/모멘트를 직접 부가합니다. 키(key)는 노드 번호입니다. | 10 |
| `/db/BMLD` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Beam Loads — 보 요소에 분포하중·집중하중·압력하중 등을 부가합니다. 키(key)는 요소 번호입니다. | 20 |
| `/db/SDSP` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Specified Displacements of Support — 지점 강제 변위(Settlement/Prescribed displacement)를 정의합니다. 키(key)는 노드 번호입니다. | 7 |
| `/db/NMAS` | POST, GET, PUT, DELETE | `dynamic_load` | create, read, update, delete | Nodal Masses — 노드에 집중 질량을 정의합니다. 키(key)는 노드 번호입니다. | 6 |
| `/db/LTOM` | POST, GET, PUT, DELETE | `dynamic_load` | create, read, update, delete | Loads to Masses — 기존 하중 케이스의 하중을 질량으로 변환하는 설정입니다. | 9 |
| `/db/NBOF` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Nodal Body Force — 노드 집중 질량·하중→질량·구조 질량으로부터 관성력(체적력)을 산정·부가합니다. | 10 |
| `/db/PSLT` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Define Pressure Load Type — 요소 면/엣지에 가해지는 압력 하중 타입을 정의합니다. 이후 `/db/PRES`로 요소에 할당합니다. | 10 |
| `/db/PRES` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Assign Pressure Loads — `/db/PSLT`에서 정의한 압력 하중 타입을 실제 요소에 할당합니다. 키(key)는 요소 번호입니다. | 13 |
| `/db/PNLD` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Define Plane Load Type — 평면 하중 타입(점·선·면)을 정의합니다. 이후 `/db/PNLA`로 요소에 할당합니다. | 21 |
| `/db/PNLA` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Assign Plane Loads — `/db/PNLD`에서 정의한 평면 하중 타입을 실제 요소에 좌표계로 할당합니다. | 16 |
| `/db/FBLD` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Define Floor Load Type — 바닥 하중 타입(Floor Load Type)을 정의합니다. 하중 케이스별 면하중 값을 담습니다. | 6 |
| `/db/FBLA` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Assign Floor Loads — `/db/FBLD`에서 정의한 바닥 하중 타입을 노드로 구성된 영역에 할당합니다. | 13 |
| `/db/FMLD` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Finishing Material Loads — 기둥/보 요소 주변 마감재 하중(Finishing Material Load)을 정의합니다. 키(key)는 요소 번호입니다. | 10 |
| `/db/POSP` | POST, GET, PUT, DELETE | `misc` | create, read, update, delete | Parameter of Soil Properties — 토압 계산에 사용되는 지반 특성 파라미터를 정의합니다. | 13 |
| `/db/EPST` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Static Earth Pressure — 정적 토압을 산정하여 벽체 요소에 부가합니다. | 18 |
| `/db/EPSE` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Seismic Earth Pressure — 지진 시 동적 토압을 산정하여 벽체 요소에 부가합니다. | 21 |
| `/db/POSL` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Parameter of Seismic Loads — 정적 지진 하중 계산에 필요한 지진 하중 파라미터를 정의합니다 (KDS 41-17-00:2019 기반). | 13 |
| `/db/SWIND` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Static Wind Load — KDS 41-12:2022 기반 정적 풍하중을 정의합니다. `INPUT_METHOD`에 따라 Simplified / General / Vortex Sheddi… | 54 |
| `/db/SSEIS` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Static Seismic Load — KDS 41-17-00:2019 기반 등가정적 지진하중을 정의합니다. `SEIS_CODE`를 `"USER TYPE"`으로 지정하면 층별 지진력을 직접 입… | 33 |

### 07. DB — Temperature / Prestress （12 个）

来源：`docs/manual/07_DB_Temperature_Prestress.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/ETMP` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Element Temperature — 요소(Element)에 균일 온도 하중을 적용합니다. 키(key)는 요소 번호이며, `ITEMS` 배열로 여러 하중 케이스를 동시에 입력할 수 있습니다. | 5 |
| `/db/GTMP` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Temperature Gradient — 보(Beam) 또는 판(Plate) 요소에 온도 구배 하중을 적용합니다. 보 요소는 z방향과 y방향 구배를 모두 지정할 수 있습니다. | 11 |
| `/db/BTMP` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Beam Section Temperature — 보 단면의 온도 분포를 구간별로 정의합니다. 일반 단면(General)과 PSC/합성 단면(PSC/Composite) 두 가지 모드를 지원합니다. | 21 |
| `/db/STMP` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | System Temperature — 전체 구조물(시스템)에 균일한 온도 변화를 적용합니다. 키(key)는 순번이며, 하나의 항목에 하중 케이스와 온도값을 직접 기입합니다. | 3 |
| `/db/NTMP` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Nodal Temperature — 노드(Node)에 온도 하중을 직접 적용합니다. 키(key)는 노드 번호이며, `ITEMS` 배열로 여러 하중 케이스를 동시에 입력할 수 있습니다. | 5 |
| `/db/TDNT` | POST, GET, PUT, DELETE | `tendon` | create, read, update, delete | Tendon Property — 텐던의 물성(재료 번호, 단면적, 이완 특성, 마찰 계수 등)을 정의합니다. 텐던 타입(INTERNAL/EXTERNAL)과 인장 방식(PRE/POST)에 따라 … | 25 |
| `/db/TDNA` | POST, GET, PUT, DELETE | `tendon` | create, read, update, delete | Tendon Profile — 텐던의 배치 경로(프로파일)를 정의합니다. 2D/3D 및 Spline/Round 조합, 기준축 타입(Element/Straight/Curve)에 따라 입력 구조가… | 44 |
| `/db/TDCS` | POST, GET, PUT, DELETE | `tendon` | create, read, update, delete | Tendon Location for Composite Section — 합성 단면(Construction Stage)에서 텐던 프로파일이 속하는 파트 번호를 지정합니다. | 3 |
| `/db/TDPL` | POST, GET, PUT, DELETE | `tendon` | create, read, update, delete | Tendon Prestress — 텐던 프로파일에 프리스트레스 하중을 적용합니다. 키(key)는 텐던 프로파일 번호(TDNA)이며, 인장력 또는 응력값으로 입력합니다. | 10 |
| `/db/PRST` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Prestress Beam Loads — 보 요소에 직접 프리스트레스 하중을 적용합니다 (텐던 프로파일 불필요). 키(key)는 요소 번호입니다. | 9 |
| `/db/PTNS` | POST, GET, PUT, DELETE | `tendon` | create, read, update, delete | Pretension Loads — 트러스/케이블 요소에 프리텐션(초기 인장력)을 부가합니다. 키(key)는 요소 번호입니다. | 5 |
| `/db/EXLD` | POST, GET, PUT, DELETE | `load_case` | create, read, update, delete | External Type Load Case for Pretension — 프리텐션 하중에 사용할 하중 케이스를 External Type으로 지정합니다. PTNS에서 참조하는 하중 케이스명을 이… | 1 |

### 08. DB — Moving Loads （28 个）

来源：`docs/manual/08_DB_Moving_Loads.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/MVCD` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Moving Load Code — 이동하중 해석에 사용할 설계 기준 코드를 설정합니다. | 1 |
| `/db/LLAN` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Traffic Line Lanes — 교량 거더 요소(Beam Element) 기반의 차선 이동 경로를 정의합니다. | 16 |
| `/db/LLANch` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Traffic Line Lanes – China — China 기준 차선 이동 경로. 중국 도시교량·고속도로교 충격계수를 별도 지정합니다. | 5 |
| `/db/LLANid` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Traffic Line Lanes – India — India (IRC) 기준 차선. IF/CDA 또는 경간 길이 방식으로 충격계수를 지정합니다. | 5 |
| `/db/LLANtr` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Traffic Line Lanes – Transverse — Transverse 이동하중 코드용 차선. 요소별 하중 계수만 정의합니다. | 4 |
| `/db/LLANop` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Traffic Line Lanes – Moving Load Optimization — 이동하중 최적화(Moving Load Optimization) 전용 차선 정의. 차선 폭 내 최적 위치를 … | 14 |
| `/db/SLAN` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Traffic Surface Lanes — 판요소(Plate Element) 기반 면 차선 이동 경로. 노드 기준으로 차선 경로를 정의합니다. | 19 |
| `/db/SLANch` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Traffic Surface Lanes – China — China 기준 면 차선. 각 노드에 경간 길이(`SPAN_LENGTH`)를 추가 지정합니다. | 3 |
| `/db/SLANop` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Traffic Surface Lanes – Moving Load Optimization — 이동하중 최적화 전용 면 차선. 차선 폭 내 최적 위치를 탐색합니다. | 17 |
| `/db/MVHL` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Vehicles — 이동하중 차량을 정의합니다. `STANDARD_CODE` 필드로 설계 기준을 구분하며, 사전 정의 차량(`VEHICLE_TYPE_NAME`)과 사용자 정의 차량(`USER_… | 153 |
| `/db/MVHLtr` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Vehicles – Transverse — Transverse 이동하중 코드용 차량. 횡방향 배치 파라미터를 정의합니다. | 12 |
| `/db/MVLD` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Moving Load Cases — 이동하중 하중 케이스를 정의합니다. General Load, Permit Vehicle, Moving Load Optimization의 세 가지 타입을 지원… | 44 |
| `/db/MVLDch` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Moving Load Cases – China — China 이동하중 하중 케이스. 교량 타입별 차선 계수를 별도 지정합니다. | 23 |
| `/db/MVLDid` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Moving Load Cases – India — India (IRC) 이동하중 하중 케이스. Auto Live Load Combinations 및 Permit Vehicle을 지원합니다. | 21 |
| `/db/MVLDbs` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Moving Load Cases – BS — BS (British Standard) 이동하중 하중 케이스. | 32 |
| `/db/MVLDeu` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Moving Load Cases – Eurocode — Eurocode (EN 1991-2) 이동하중 하중 케이스. 5가지 Load Model 타입(`TYPE_LOADMODEL`)과 각 타입별… | 33 |
| `/db/MVLDpl` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Moving Load Cases – Poland — Poland 이동하중 하중 케이스. 3가지 Load Model (Vehicle S, Vehicle K, Military)을 지원합니다. | 34 |
| `/db/MVLDtr` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Moving Load Cases – Transverse — Transverse 이동하중 코드 전용 하중 케이스. | 7 |
| `/db/CRGR` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Concurrent Reaction Group — 이동하중 해석 시 반력을 동시에 추출할 구조 그룹들을 정의합니다. | 1 |
| `/db/CJFG` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Concurrent Joint Force Group — 이동하중 해석 시 절점 힘을 동시에 추출할 구조 그룹들을 정의합니다. | 1 |
| `/db/MVHC` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Vehicle Classes — 여러 차량을 하나의 클래스로 묶어 Moving Load Case에서 그룹으로 사용합니다. | 2 |
| `/db/SINF` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Plate Element for Influence Surface — 영향면(Influence Surface) 해석에 사용할 판 요소 목록을 지정합니다. | 1 |
| `/db/MLSP` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Lane Support – Negative Moments at Interior Piers — 연속교 내측 지점부 부(-) 모멘트 차선 지지 위치를 지정합니다. | 5 |
| `/db/MLSR` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Lane Support – Reactions at Interior Piers — 연속교 내측 지점부 반력 차선 지지 절점을 지정합니다. | 1 |
| `/db/DYLA` | POST, GET, PUT, DELETE | `dynamic_load` | create, read, update, delete | Dynamic Load Allowance — 구조 그룹별로 충격 계수(Dynamic Load Allowance, IM)를 설정합니다. | 2 |
| `/db/IMPF` | POST, GET, PUT, DELETE | `dynamic_load` | create, read, update, delete | Additional Impact Factor — 차선별, 요소 타입별로 추가 충격 계수 또는 유효 경간 길이를 설정합니다. | 9 |
| `/db/DYFG` | POST, GET, PUT, DELETE | `dynamic_load` | create, read, update, delete | Railway Dynamic Factor — Eurocode 기반 철도 동적 계수(φ)를 전체 모델에 적용합니다. | 6 |
| `/db/DYNF` | POST, GET, PUT, DELETE | `dynamic_load` | create, read, update, delete | Railway Dynamic Factor by Element — Eurocode 기반 철도 동적 계수(φ)를 요소 단위로 적용합니다. DYFG와 동일한 구조이나 `Assign` 키 값이 요소 … | 6 |

### 11. DB — Settlement / Miscellaneous Loads （9 个）

来源：`docs/manual/11_DB_Settlement_Misc_Loads.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/SMPT` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Settlement Group — 지점 침하 그룹을 정의합니다. 침하 변위를 적용할 노드 목록과 침하량을 저장합니다. | 3 |
| `/db/SMLC` | POST, GET, PUT, DELETE | `load_case` | create, read, update, delete | Settlement Load Cases — 침하 하중 케이스(Settlement Load Cases)를 정의합니다. 침하 그룹을 참조하여 최솟값/최댓값 그룹 수와 스케일 팩터를 설정합니다. | 7 |
| `/db/PLCB` | POST, GET, PUT, DELETE | `load_case` | create, read, update, delete | Pre-composite Section — 합성 이전(Pre-composite) 단계에 적용되는 정적 하중 케이스 목록을 지정합니다. 합성 구조 해석 시 슬래브 타설 전 거더만으로 지지되는 하… | 1 |
| `/db/LDSQ` | POST, GET, PUT, DELETE | `load_case` | create, read, update, delete | Load Sequence for Nonlinear — 비선형 해석에 적용되는 하중 순서(Load Sequence)를 정의합니다. 비선형 해석에서 하중이 적용되는 순서를 제어합니다. | 1 |
| `/db/WVLD` | POST, GET, PUT, DELETE | `load` | create, read, update, delete | Wave Loads — 해양 구조물에 적용되는 파랑 하중(Wave Loads)을 정의합니다. Morison 방정식 기반으로 항력·관성력 계수, 파랑 특성, 조류 프로파일, 해양 성장 등을 포함… | 64 |
| `/db/IELC` | POST, GET, PUT, DELETE | `load_case` | create, read, update, delete | Ignore Elements for Load Cases — 특정 요소를 지정된 하중 케이스에서 무시하도록 설정합니다. 비선형 해석 등에서 특정 요소가 하중 전달에 참여하지 않도록 제어합니다. | 3 |
| `/db/IFGS` | POST, GET, PUT, DELETE | `misc` | create, read, update, delete | Large Displacement – Initial Forces for Geometric Stiffness — 대변위(Large Displacement) 해석에서 기하학적 강성 행렬 계산에 사… | 2 |
| `/db/EFCT` | POST, GET, PUT, DELETE | `misc` | create, read, update, delete | Small Displacement – Initial Force Control Data — 소변위(Small Displacement) 해석에서의 초기 힘 제어 데이터를 정의합니다. 하중 케이스 … | 7 |
| `/db/INMF` | POST, GET, PUT, DELETE | `misc` | create, read, update, delete | Small Displacement – Initial Element Force — 소변위 해석에서 요소별 초기 힘(Initial Element Force)을 직접 지정합니다. 요소 타입에 따라 … | 3 |

### 09. DB – Dynamic Loads （12 个）

来源：`MIDAS-API-main/docs/manual/09_DB_Dynamic_Loads.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/SPFC` | GET, POST, PUT, DELETE | `dynamic_load` | create, read, update, delete | Response Spectrum Functions — 응답 스펙트럼 함수 (STR.SPEC_CODE로 User/한국/미국/Eurocode/중국/일본/대만/인도/기타 설계 기준 지원) | 55 |
| `/db/SPLC` | GET, POST, PUT, DELETE | `load_case` | create, read, update, delete | Response Spectrum Load Cases — 응답 스펙트럼 하중 케이스 | 43 |
| `/db/THGC` | GET, POST, PUT, DELETE | `dynamic_load` | create, read, update, delete | Time History Global Control — 시간이력 해석 전역 제어 파라미터 | 28 |
| `/db/THGC-M1` | GET, PUT, DELETE | `dynamic_load` | read, update, delete | Time History Global Control (Hyper-S) — Hyper-S 비선형 시간이력 전역 제어 | 34 |
| `/db/THOO-M1` | GET, PUT, DELETE | `dynamic_load` | read, update, delete | Time History Output Option (Hyper-S) — Hyper-S 비선형 시간이력 출력 옵션 | 11 |
| `/db/THIS` | GET, POST, PUT, DELETE | `load_case` | create, read, update, delete | Time History Load Cases — 시간이력 하중 케이스 (COMMON.iATYPE × COMMON.iAMETHOD 조합에 따라 추가 파라미터가 달라짐) | 60 |
| `/db/THIS-M1` | GET, POST, PUT, DELETE | `load_case` | create, read, update, delete | Time History Load Cases (Hyper-S) — Hyper-S 비선형 시간이력 하중 케이스 (ANAL_CASE / DAMPING / NONL_CTRL_PARAM 중첩 오브젝트 구조) | 63 |
| `/db/THFC` | GET, POST, PUT, DELETE | `dynamic_load` | create, read, update, delete | Time History Functions — 시간이력 함수(시간-값 쌍 또는 사인파 함수) | 16 |
| `/db/THGA` | GET, POST, PUT, DELETE | `dynamic_load` | create, read, update, delete | Ground Acceleration — 시간이력 하중 케이스에 적용되는 지반 가속도 | 11 |
| `/db/THNL` | GET, POST, PUT, DELETE | `load` | create, read, update, delete | Dynamic Nodal Loads — 시간이력 하중 케이스에 적용되는 동적 절점 하중 | 7 |
| `/db/THSL` | GET, POST, PUT, DELETE | `load` | create, read, update, delete | Time Varying Static Loads — 시간이력 하중 케이스에 적용되는 시변 정적 하중 | 5 |
| `/db/THMS` | GET, POST, PUT, DELETE | `dynamic_load` | create, read, update, delete | Multiple Support Excitation — 다중 지점 가진 | 13 |

### 10. DB – Construction Stage / Hydration （14 个）

来源：`MIDAS-API-main/docs/manual/10_DB_Construction_Stage.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/STAG` | GET, POST, PUT, DELETE | `construction_stage` | create, read, update, delete | Define Construction Stage — 시공단계 정의 (구조 그룹·경계 그룹·하중 그룹의 활성화/비활성화를 단계별로 설정) | 20 |
| `/db/CSCS` | GET, POST, PUT, DELETE | `section` | create, read, update, delete | Composite Section for Construction Stage — 시공단계별 합성 단면 (각 파트의 재료·나이·강성 정보 설정) | 45 |
| `/db/TMLD` | GET, POST, PUT, DELETE | `load` | create, read, update, delete | Time Loads for Construction Stage — 시공단계에서의 시간 하중 (특정 시공단계 ID에 하중 그룹과 적용 일을 지정) | 4 |
| `/db/STBK` | GET, POST, PUT, DELETE | `load` | create, read, update, delete | Set-Back Loads for Nonlinear Construction Stage — 비선형 시공단계 해석의 Set-Back 하중(절점 변위 기반) | 7 |
| `/db/CMCS` | GET, POST, PUT, DELETE | `construction_stage` | create, read, update, delete | Camber for Construction Stage — 시공단계별 절점 캠버(초기 변형) | 2 |
| `/db/CRPC` | GET, POST, PUT, DELETE | `construction_stage` | create, read, update, delete | Creep Coefficient for Construction Stage — 시공단계별 크리프 계수 | 4 |
| `/db/ETFC` | GET, POST, PUT, DELETE | `load` | create, read, update, delete | Ambient Temperature Functions — 수화열 해석에 사용되는 외기 온도 함수 | 10 |
| `/db/CCFC` | GET, POST, PUT, DELETE | `load` | create, read, update, delete | Convection Coefficient Functions — 수화열 해석에 사용되는 대류 계수 함수 | 7 |
| `/db/HECB` | GET, POST, PUT, DELETE | `boundary` | create, read, update, delete | Element Convection Boundary — 수화열 해석에서 요소의 대류 경계 조건 | 6 |
| `/db/HSPT` | GET, POST, PUT, DELETE | `boundary` | create, read, update, delete | Prescribed Temperature — 수화열 해석에서 절점의 지정 온도 | 4 |
| `/db/HSFC` | GET, POST, PUT, DELETE | `load` | create, read, update, delete | Heat Source Functions — 수화열 해석에 사용되는 열원 함수 (Constant / Code(함수) / User 타입 지원) | 14 |
| `/db/HAHS` | GET, POST, PUT, DELETE | `load` | create, read, update, delete | Assign Heat Source — 요소에 열원 함수를 지정 | 1 |
| `/db/HPCE` | GET, POST, PUT, DELETE | `load` | create, read, update, delete | Pipe Cooling — 수화열 해석에서 파이프 쿨링 시스템 정의 | 10 |
| `/db/HSTG` | GET, POST, PUT, DELETE | `construction_stage` | create, read, update, delete | Define Construction Stage for Hydration — 수화열 해석 전용 시공단계 정의 | 11 |

### 12. DB — Analysis Control （21 个）

来源：`MIDAS-API-main/docs/manual/12_DB_Analysis_Control.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/ACTL` | POST, GET, PUT, DELETE | `analysis` | create, read, update, delete | Main Control Data — 해석의 기본 제어 데이터를 정의합니다. 자동 구속, 반복 횟수, 수렴 허용오차 등을 설정합니다. | 9 |
| `/db/ACTL-M1` | GET, PUT, DELETE | `analysis` | read, update, delete | Main Control Data (Hyper-S) — Hyper-S(MEC) 솔버용 메인 제어 데이터. 인장/압축 트러스 요소(Tension/Compression Truss) 고급 비선형 파라… | 16 |
| `/db/PDEL` | POST, GET, PUT, DELETE | `analysis` | create, read, update, delete | P-Delta Analysis Control — P-Delta(2차 효과) 해석 제어 데이터를 정의합니다. 반복 횟수, 수렴 허용오차, 대상 하중 케이스를 설정합니다. | 5 |
| `/db/BUCK` | POST, GET, PUT, DELETE | `analysis` | create, read, update, delete | Buckling Analysis Control — 좌굴(Buckling) 해석 제어 데이터를 정의합니다. 모드 수, 하중계수 범위, Sturm Sequence 체크, 좌굴 조합을 설정합니다. | 10 |
| `/db/EIGV` | POST, GET, PUT, DELETE | `analysis` | create, read, update, delete | Eigenvalue Analysis Control — 고유치(Eigenvalue) 해석 제어 데이터를 정의합니다. 해석 타입(`TYPE`)에 따라 파라미터가 달라집니다: Subspace Ite… | 16 |
| `/db/EIGV-M1` | GET, PUT, DELETE | `analysis` | read, update, delete | Eigenvalue Analysis Control (Hyper-S) — Hyper-S(MEC) 솔버용 고유치 해석 제어. UI의 Subspace Iteration이 MEC에서 Lanczos로 … | 14 |
| `/db/HHCT` | POST, GET, PUT, DELETE | `analysis` | create, read, update, delete | Heat of Hydration Analysis Control — 수화열(Heat of Hydration) 해석 제어 데이터를 정의합니다. 적분계수, 초기온도, 응력 평가 위치, 크리프·건조수… | 20 |
| `/db/HHCT-M1` | GET, PUT, DELETE | `analysis` | read, update, delete | Heat of Hydration Analysis Control (Hyper-S) — Hyper-S(MEC) 솔버용 수화열 해석 제어. 반복 횟수(`ITER`)와 수렴 기준(`CONVERGENC… | 23 |
| `/db/MVCT` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Moving Load Analysis Control — 이동하중(Moving Load) 해석 제어 데이터를 정의합니다. 해석 방법, 영향선 생성점, 판/프레임/링크별 결과 옵션, 계산 필터(반… | 31 |
| `/db/MVCTch` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Moving Load Analysis Control – China — 중국 코드(JTG 등) 전용 이동하중 해석 제어. 충격계수(`bIF`), 코드 타입, 고유진동수 방법, 주파수 데이터(`F… | 114 |
| `/db/MVCTid` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Moving Load Analysis Control – India — 인도 코드(IRC/IRS) 전용 이동하중 해석 제어. 충격/CDA 계산용 교량 타입, 철도교 정보(트랙, 침목 폭, 성토 … | 25 |
| `/db/MVCTbs` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Moving Load Analysis Control – BS — 영국 코드(BS 5400 / BD 37/01 / CS 454) 전용 이동하중 해석 제어. 표준 차로(Notional Lanes)… | 21 |
| `/db/MVCTtr` | POST, GET, PUT, DELETE | `moving_load` | create, read, update, delete | Moving Load Analysis Control – Transverse — 횡방향(Transverse) 이동하중 해석 제어. 단위 하중 수, 해석 결과 타입, 결과 옵션(조합응력/반력/변위… | 9 |
| `/db/SMCT` | POST, GET, PUT, DELETE | `analysis` | create, read, update, delete | Settlement Analysis Control Data — 침하(Settlement) 해석 제어 데이터를 정의합니다. 판/링크 요소의 동시력(Concurrent Force) 계산 활성화 여… | 2 |
| `/db/NLCT` | POST, GET, PUT, DELETE | `analysis` | create, read, update, delete | Nonlinear Analysis Control Data — 비선형(Nonlinear) 해석 제어 데이터를 정의합니다. 비선형 타입, 반복법(Newton-Raphson/Arc-Length/Di… | 35 |
| `/db/NLCT-M1` | GET, PUT, DELETE | `analysis` | read, update, delete | Nonlinear Analysis Control (Hyper-S) — Hyper-S(MEC) 솔버용 비선형 해석 제어. `LC_SCOPE`로 적용 범위를 지정하고, `LOAD_STEPS`(스텝… | 32 |
| `/db/STCT` | POST, GET, PUT, DELETE | `construction_stage` | create, read, update, delete | Construction Stage Analysis Control Data — 시공단계(Construction Stage) 해석 제어 데이터를 정의합니다. 해석 타입(`iINC_NLA`: 선형/… | 66 |
| `/db/STCT-M1` | GET, PUT, DELETE | `construction_stage` | read, update, delete | Construction Stage Analysis Control Data (Hyper-S) — Hyper-S(MEC) 솔버용 시공단계 해석 제어. 기능별로 중첩 객체(`ANAL_TYPE`, `… | 57 |
| `/db/BCCT` | POST, GET, PUT, DELETE | `boundary` | create, read, update, delete | Boundary Change Assignment — 경계 변경(Boundary Change) 할당 데이터를 정의합니다. 어떤 경계 데이터 종류(지점/스프링/링크/강성계수/단부해제 등)를 변경 … | 16 |
| `/db/BCGD-M1` | POST, GET, PUT, DELETE | `boundary` | create, read, update, delete | Define Boundary Combination (Hyper-S) — Hyper-S(MEC) 솔버용 경계 그룹 조합(Boundary Group Combination)을 정의합니다. 조합 이름… | 2 |
| `/db/BCGA-M1` | POST, GET, PUT, DELETE | `boundary` | create, read, update, delete | Assign Boundary Combination (Hyper-S) — Hyper-S(MEC) 솔버용 경계 조합 할당 데이터. 해석 타입·하중케이스에 경계 조합(BCGD)을 할당하고(`BC_A… | 5 |

### 13. DB — Load Combinations / Results （8 个）

来源：`MIDAS-API-main/docs/manual/13_DB_Load_Combinations.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/LCOM-GEN` | POST, GET, PUT, DELETE | `load_combination` | create, read, update, delete | Load Combinations – General — 일반 하중조합 정의. 정적·이동·응답스펙트럼·시간이력·시공단계·침하 케이스를 조합하여 구조해석 결과용 하중조합을 생성합니다. | 10 |
| `/db/LCOM-CONC` | POST, GET, PUT, DELETE | `load_combination` | create, read, update, delete | Load Combinations – Concrete Design — 콘크리트 설계용 하중조합 정의. 강도설계(Strength) / 사용성 설계(Service) 구분이 가능하며, 콘크리트 설계 … | 11 |
| `/db/LCOM-STEEL` | POST, GET, PUT, DELETE | `load_combination` | create, read, update, delete | Load Combinations – Steel Design — 강재 설계용 하중조합 정의. LCOM-GEN과 구조가 동일하나 ACTIVE 타입이 STRENGTH / SERVICE로 구분되며 A… | 10 |
| `/db/LCOM-SRC` | POST, GET, PUT, DELETE | `load_combination` | create, read, update, delete | Load Combinations – SRC Design — SRC(철골 콘크리트 합성) 설계용 하중조합. 구조는 LCOM-STEEL과 동일합니다. | 10 |
| `/db/LCOM-STLCOMP` | POST, GET, PUT, DELETE | `load_combination` | create, read, update, delete | Load Combinations – Composite Steel Girder Design — 강합성 거더(Composite Steel Girder) 설계용 하중조합. 구조는 LCOM-STEEL… | 10 |
| `/db/LCOM-SEISMIC` | POST, GET, PUT, DELETE | `load_combination` | create, read, update, delete | Load Combinations – Seismic Design — 내진 설계용 하중조합 정의. ACTIVE 타입은 LCOM-GEN과 동일(INACTIVE/ACTIVE)하며, ABS 합산 방식은… | 10 |
| `/db/CUTL` | POST, GET, PUT, DELETE | `result` | create, read, update, delete | Cutting Line — 구조 모델의 단면력(Sectional Force) 결과를 추출하기 위한 절단선(Cutting Line)을 정의합니다. 두 점(PT1, PT2)을 지정하여 절단 방향과… | 12 |
| `/db/CLWP` | POST, GET, PUT, DELETE | `result` | create, read, update, delete | Plate Cutting Line Diagram — 판(Plate) 요소에 대한 절단선 다이어그램을 정의합니다. CUTL(1D 절단선)과 달리 세 점(PT1, PT2, PT3)으로 면(Plan… | 14 |

### 14. DB — Pushover （6 个）

来源：`MIDAS-API-main/docs/manual/14_DB_Pushover.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/POGD` | POST, GET, PUT, DELETE | `pushover` | create, read, update, delete | Pushover Analysis Control Data — 푸시오버(정적 비선형) 해석의 전역 제어 데이터를 정의합니다. 기하비선형 옵션, 초기하중 방법, 비선형 해석 옵션(수렴 조건·해석 정… | 73 |
| `/db/POGD-M1` | GET, PUT, DELETE | `pushover` | read, update, delete | Pushover Global Control (Hyper-S) — Hyper-S(MEC) 솔버 전용 Pushover(정적 비선형 내진성능평가) 해석의 전역 제어 옵션을 정의합니다. 기하비선형 유… | 65 |
| `/db/IEPI` | POST, GET, PUT, DELETE | `pushover` | create, read, update, delete | Ignore Elements for Pushover Initial Load — 비선형(푸시오버) 해석의 초기하중 계산 시 무시할 요소를 지정합니다. Assign Key는 요소 ID입니다. | 1 |
| `/db/PHGE` | POST, GET, PUT, DELETE | `pushover` | create, read, update, delete | Assign Pushover Hinge Properties — 요소에 푸시오버 힌지 속성을 배정합니다. Assign Key는 배정 순번이며, 요소 ID(`ID`)와 요소 타입(`TYPE`)을 … | 4 |
| `/db/POLC` | POST, GET, PUT, DELETE | `pushover` | create, read, update, delete | Pushover Load Cases — 푸시오버(정적 비선형) 하중케이스를 정의합니다. 증분 방법(하중 제어/변위 제어), 해석 정지 조건, 하중 패턴(정적 하중/균등 가속도/모드 형상/정규화… | 26 |
| `/db/POLC-M1` | GET, PUT, DELETE | `pushover` | read, update, delete | Pushover Load Case (Hyper-S) — Hyper-S(MEC) 솔버 전용 Pushover(정적 비선형) 해석에 사용되는 하중케이스(제어 방식, 증분 단계, 하중 패턴 등)를 정… | 22 |

### 16. VIEW （7 个）

来源：`MIDAS-API-main/docs/manual/16_VIEW.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/view/SELECT` | GET | `view` | read | Select — 현재 모델 뷰에서 사용자가 선택한 노드(Node)와 요소(Element)의 ID 목록을 조회합니다. 응답 전용(GET) 엔드포인트입니다. | 2 |
| `/view/CAPTURE` | POST | `view` | create | Capture — 현재 모델 뷰를 이미지 파일로 캡처하여 저장합니다. 시점(`ANGLE`), 활성화(`ACTIVE`), 표시(`DISPLAY`), 결과 그래픽(`RESULT_GRAPHIC`) … | 21 |
| `/view/PRECAPTURE` | POST | `view` | create | Dialog Capture — 특정 다이얼로그(사전처리 미리보기) 화면을 이미지 파일로 캡처합니다. 현재 섬유 단면(Fiber Division of Section) 미리보기를 지원합니다. | 4 |
| `/view/ANGLE` | POST | `view` | create | Viewpoint — 모델 뷰의 시점(Viewpoint)을 수평/수직 각도로 설정합니다. | 2 |
| `/view/ACTIVE` | POST | `view` | create | Active — 모델 뷰에서 활성화(Active)할 대상을 지정합니다. 전체(All), 노드/요소 지정(Active), 아이덴티티 그룹 지정(Identity)의 3가지 모드를 지원합니다. | 6 |
| `/view/DISPLAY` | POST | `view` | create | Display — 모델 창에 표시되는 절점(Node)·요소(Element)·특성(Property)·경계조건(Boundary)·하중(Load)·기타(Misc)·뷰(View) 항목의 표시 여부와 … | 129 |
| `/view/RESULTGRAPHIC` | POST | `view` | create | Result Graphic — 반력/변위/보 다이어그램/평면·판 응력/솔리드 응력 등 해석 결과를 모델 창에 그래픽으로 표시하는 방식을 제어합니다. 현재 결과 모드(`CURRENT_MODE`)… | 88 |

### 15. OPE （19 个）

来源：`MIDAS-API-main/docs/manual/15_OPE.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/ope/PROJECTSTATUS` | GET | `project` | read | Project Status — 현재 프로젝트의 각종 데이터 개수(노드·요소·재료·하중케이스 등) 현황을 조회합니다. DB 저장 없이 실시간 집계 결과만 반환합니다. | 4 |
| `/ope/DIVIDEELEM` | POST | `element` | create | Divide Elements — 지정한 요소(선·평면·솔리드)를 등분할·비등분할·비율분할·평행 브레이싱·노드기준 분할 등 다양한 방식으로 세분화합니다. | 27 |
| `/ope/SECTPROP` | GET | `section` | read | Section Properties Calculation Results — 등록된 단면의 계산된 단면 특성값(면적·관성모멘트·단면계수 등)을 조회합니다. | 2 |
| `/ope/USLC` | POST | `load_combination` | create | Using Load Combinations — 정의된 하중조합을 설계용 프리픽스와 함께 강재/콘크리트/SRC 설계에 사용하도록 지정하고, 각 하중조합에 포함할 하중 종류를 선택합니다. | 23 |
| `/ope/LINEBMLD` | POST | `load` | create | Line Beam Load — 하중이 작용하는 선(Line)을 절점 2개 또는 선택된 요소로 정의하여, 그 선을 지나는 부재들에 자동으로 집중/등분포/사다리꼴/곡선 하중을 생성·분배합니다. | 32 |
| `/ope/AUTOMESH` | POST | `element` | create | Auto-Mesh Planar Area — 노드·선요소·평면요소로 둘러싸인 영역을 자동으로 사각형/삼각형 메시로 분할하여 판(Plate)·평면응력·평면변형률·축대칭 요소를 생성합니다. | 29 |
| `/ope/SSPS` | POST | `spring` | create | Surface Spring — 면 스프링(Surface Spring) 경계조건을 점스프링(Point Spring) 또는 탄성링크(Elastic Link)로 변환하여 생성합니다. 프레임/평면/솔… | 17 |
| `/ope/EDMP` | POST | `element` | create | Change Property — 수축·크리프 계산에 필요한 부재의 명목크기(Notional Size of Member) 또는 체적표면비(Volume Surface Ratio)를 지정 또는 자동… | 7 |
| `/ope/STOR` | POST | `misc` | create | Story Calculation — 층(Story) 계산 시 지진/풍하중 우발편심(Accidental Eccentricity) 고려 여부와 값을 설정하고, 층별 계산 결과를 반환합니다. | 6 |
| `/ope/STORY_PARAM` | GET, POST | `misc` | read, create | Story Check Parameter — 층간변위비·비틀림 등 층 검토에 사용할 국가별 기준코드(Country Code)를 설정하거나 조회합니다. | 1 |
| `/ope/STORY_IRR_PARAM` | GET, POST | `misc` | read, create | Story Irregularity Check Parameter — 층 불규칙성(비틀림·강성·강도) 검토를 위한 국가 기준코드, 층간변위 산정방법, 층강성 산정방법, 지진거동계수를 설정 또는 조… | 4 |
| `/ope/STORYPROP` | POST | `result` | create | Story Properties — 층별 중량, 표고, 재하높이, 재하폭(Bx/By) 등 층 속성 계산 결과를 지정한 단위·형식으로 조회합니다. | 4 |
| `/ope/MEMB` | POST | `element` | create | Member Assignment — 여러 요소를 하나의 부재(Member)로 자동/수동 배정합니다. 설계 검토 시 부재 단위 검토를 위해 사용됩니다. | 4 |
| `/ope/GUSTFACTOR` | POST | `load` | create | Gust Factor Calculator — KDS 41 12:2022 풍하중 기준에 따라 강성/유연 구조물의 거스트영향계수(Gust Effect Factor)를 계산합니다. | 26 |
| `/ope/LCOM-GEN` | POST | `load_combination` | create | Load Combination (General) – KDS:2022 / AIK-SRC2K — 설계기준(콘크리트/강재/SRC)에 따라 응답스펙트럼 축계수, 풍하중 조합, 직교효과, 특별지진하중·… | 53 |
| `/ope/LCOM-CONC` | POST | `load_combination` | create | Load Combination (Concrete) – KDS 41 20:2022 — KDS 41 20:2022 콘크리트 구조 설계기준에 따라 응답스펙트럼 축계수, 풍하중 조합, 직교효과, 특별… | 49 |
| `/ope/LCOM-STEEL` | POST | `load_combination` | create | Load Combination (Steel) – KDS 41 30:2022 — KDS 41 30:2022 강구조 설계기준에 따라 응답스펙트럼 축계수, 풍하중 조합, 직교효과, 특별지진하중·수직… | 47 |
| `/ope/LCOM-SRC` | POST | `load_combination` | create | Load Combination (SRC) – KDS 41 SRC:2022 / AIK-SRC2K — KDS 41 SRC:2022 합성구조(강관콘크리트/매입형강 등) 설계기준에 따라 응답스펙트럼 … | 47 |
| `/ope/GSBG` | POST | `bridge` | create | Bridge Girder Diagram Image Generation — 교량 거더(Bridge Girder)의 응력(Stress)/부재력(Force) 다이어그램 이미지를 생성해 파일로 저장합… | 16 |

### 18. POST — Pre-Process Tables （10 个）

来源：`MIDAS-API-main/docs/manual/18_POST_PreProcess.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/post/TABLE` | POST | `misc` | execute | Element Weight Table — 요소별 중량(단위중량·총중량 등)을 추출합니다. `NODE_ELEMS`로 대상 요소를 3가지 방식 중 하나로 지정할 수 있으며, 생략 시 전체 요소가 … | 7 |
| `/post/TABLE` | POST | `misc` | execute | Nodal Body Force Table — 하중케이스별 절점 체적력(Nodal Body Force, FX/FY/FZ)을 추출합니다. | 3 |
| `/post/TABLE` | POST | `misc` | execute | Mass Summary Table — 절점별 질량 요약(절점질량·하중질량·구조질량·합계)을 X/Y/Z 방향별로 추출합니다. | 3 |
| `/post/TABLE` | POST | `misc` | execute | Load Summary Table — 하중케이스별 하중 요약(집중·보·바닥·압력·자중·합계)을 X/Y/Z 방향별로 추출합니다. | 3 |
| `/post/TABLE` | POST | `misc` | execute | Material Table — 재료 특성 테이블(탄성계수·포아송비·열팽창계수·밀도·질량밀도 등)을 추출합니다. | 3 |
| `/post/TABLE` | POST | `misc` | execute | Section Table — 단면 특성 테이블(면적·전단면적·관성모멘트·단면계수·둘레 등)을 추출합니다. `TABLE_TYPE`으로 단면 종류를 선택합니다. | 3 |
| `/post/TABLE` | POST | `misc` | execute | Restraint Supports Table — 지점 구속 조건 테이블(Dx/Dy/Dz/Rx/Ry/Rz/Rw 구속 여부, 경계 그룹)을 추출합니다. | 3 |
| `/post/TABLE` | POST | `misc` | execute | Story Mass Summary Table — 층별 질량 요약을 추출합니다. `STORY_MASS`(방향 합산) 또는 `STORY_MASS_X/Y/Z`(방향별)를 선택하며, `UNIT`·`S… | 12 |
| `/post/TABLE` | POST | `misc` | execute | Story Load Summary Table — 층별 하중 요약(집중·보·바닥·압력·자중·합계)을 X/Y/Z 방향별로 추출합니다. | 3 |
| `/post/TABLE` | POST | `misc` | execute | Story Weight Table — 층별 중량을 요소 종류별(트러스·보·멤브레인·판·벽체·솔리드·합계)로 추출합니다. | 12 |

### 19. POST — Analysis Result Tables Part 1 （13 个）

来源：`MIDAS-API-main/docs/manual/19_POST_AnalysisResult_1.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/post/TABLE` | POST | `result` | execute | Reaction — 지점 반력(전역/국부/면스프링 국부)을 추출합니다. | 19 |
| `/post/TABLE` | POST | `result` | execute | Displacements — 절점 변위(전역/국부)를 추출합니다. | 20 |
| `/post/TABLE` | POST | `result` | execute | Truss Force — 트러스 요소의 부재력(I단·J단 축력)을 추출합니다. | 19 |
| `/post/TABLE` | POST | `result` | execute | Truss Stress — 트러스 요소의 응력(I단·J단)을 추출합니다. | 19 |
| `/post/TABLE` | POST | `result` | execute | Cable Force — 케이블 요소의 장력(Tension)과 성분력(FX/FY/FZ)을 I단·J단별로 추출합니다. 시공단계 스텝(`Step`)별로 조회됩니다. | 19 |
| `/post/TABLE` | POST | `result` | execute | Cable Configuration — 케이블 요소의 형상 정보(전체 길이·신장량·무변형 길이·처짐·수평/수직 거리·경사·스큐각 등)를 추출합니다. | 19 |
| `/post/TABLE` | POST | `result` | execute | Cable Efficiency — 케이블 요소의 효율(Efficiency, 등가 강성 저감 지표) 관련 값(현 길이·ExA·중량·장력·수정 ExA·효율)을 추출합니다. | 19 |
| `/post/TABLE` | POST | `result` | execute | Beam Force — 보 요소의 부재력/모멘트(축력·전단력·비틀림·모멘트·바이모멘트 등)를 부재 위치(Part)별로 추출합니다. | 21 |
| `/post/TABLE` | POST | `result` | execute | Beam Force (Static Prestress) — 정적 프리스트레스(Static Prestress) 하중에 대한 보 부재력을 추출합니다. | 20 |
| `/post/TABLE` | POST | `result` | execute | Beam Stress — 보 요소의 응력(축응력·전단응력·휨응력·조합응력)을 추출합니다. 7th DOF(뒴, Warping) 포함 옵션을 지원합니다. | 22 |
| `/post/TABLE` | POST | `result` | execute | Beam Stress (Equivalent) — 보 요소의 등가 응력(Equivalent, 단면 위치별 상세 응력 – 수직·전단·Von-Mises·최대전단·주응력)을 추출합니다. | 21 |
| `/post/TABLE` | POST | `result` | execute | Beam Stress (PSC) — PSC(프리스트레스 콘크리트) 보 요소의 응력을 성분별(축력·모멘트·텐던·합계·전단·비틀림·주응력 등)로 상세 추출합니다. 7th DOF 포함 옵션을 지원합니다. | 21 |
| `/post/TABLE` | POST | `result` | execute | Concurrent Joint Force — 지정한 반력 절점(`NODE_KEY`)의 반력 성분이 극값(max/min)을 이루는 시점에 대해, 지정된 하중케이스 목록의 절점력을 동시(concu… | 5 |

### 20. POST — Analysis Result Tables Part 2 （39 个）

来源：`docs/manual/20_POST_AnalysisResult_2.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/post/TABLE` | POST | `result` | execute | 판(Plate) 요소의 부재력/모멘트를 요소 국부 좌표계(Local) 기준으로 절점별 추출합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 판(Plate) 요소의 부재력/모멘트를 전역 좌표계(Global) 기준으로 절점별 추출합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 판(Plate) 요소의 단위 길이당 부재력/모멘트(막력 Fxx·Fyy·Fxy, 휨 Mxx·Myy·Mxy, 주값 Fmax/Fmin·Mmax/Mmin, 전단 Vxx·Vyy)를 추출합니다. 국부/전… | 0 |
| `/post/TABLE` | POST | `result` | execute | 판(Plate) 요소의 응력을 요소 국부 좌표계(Local) 기준으로 상·하면(Top/Bot)별로 추출합니다. 성분 응력(Sig-xx·yy·xy), 주응력(Sig-Max/Min), 유효응력(S… | 0 |
| `/post/TABLE` | POST | `result` | execute | 판(Plate) 요소의 응력을 전역 좌표계(Global) 기준으로 상·하면(Top/Bot)별로 추출합니다. 6성분 응력(Sig-XX·YY·ZZ·XY·YZ·XZ)과 주응력·유효응력·최대전단을 포… | 0 |
| `/post/TABLE` | POST | `result` | execute | 판(Plate) 요소의 변형률을 요소 국부 좌표계(Local) 기준으로 상·하면(Top/Bot)별로 추출합니다. 소성 변형률(Plastic)/전체 변형률(Total)을 선택할 수 있으며, 비선… | 0 |
| `/post/TABLE` | POST | `result` | execute | 판(Plate) 요소의 변형률을 전역 좌표계(Global) 기준으로 상·하면(Top/Bot)별로 추출합니다. 소성/전체 변형률을 선택할 수 있으며 6성분(Strain-XX·YY·ZZ·XY·YZ… | 0 |
| `/post/TABLE` | POST | `result` | execute | 평면응력(Plane Stress) 요소의 절점 부재력을 요소 국부 좌표계(Local) 기준으로 추출합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 평면응력(Plane Stress) 요소의 절점 부재력을 전역 좌표계(Global) 기준으로 추출합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 평면응력(Plane Stress) 요소의 응력을 요소 국부 좌표계(Local) 기준으로 추출합니다. 성분 응력·주응력·유효응력(Sig-EFF)·최대전단을 포함합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 평면응력(Plane Stress) 요소의 응력을 전역 좌표계(Global) 기준으로 추출합니다. 6성분 응력(Sig-XX·YY·ZZ·XY·YZ·XZ)과 주응력·유효응력·최대전단을 포함합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 평면변형률(Plane Strain) 요소의 절점 부재력을 요소 국부 좌표계(Local) 기준으로 추출합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 평면변형률(Plane Strain) 요소의 절점 부재력을 전역 좌표계(Global) 기준으로 추출합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 평면변형률(Plane Strain) 요소의 응력을 요소 국부 좌표계(Local) 기준으로 추출합니다. 성분 응력·주응력(Sig-P1/P2/P3)·최대전단·유효응력(Sig-EFF)·팔면체 응력(… | 0 |
| `/post/TABLE` | POST | `result` | execute | 평면변형률(Plane Strain) 요소의 응력을 전역 좌표계(Global) 기준으로 추출합니다. 성분 응력·주응력·최대전단·유효응력·팔면체 응력을 포함합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 축대칭(Axisymmetric) 요소의 절점 부재력을 요소 국부 좌표계(Local) 기준으로 추출합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 축대칭(Axisymmetric) 요소의 절점 부재력을 전역 좌표계(Global) 기준으로 추출합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 축대칭(Axisymmetric) 요소의 응력을 요소 국부 좌표계(Local) 기준으로 추출합니다. 성분 응력·주응력·최대전단·유효응력·팔면체 응력을 포함합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 축대칭(Axisymmetric) 요소의 응력을 전역 좌표계(Global) 기준으로 추출합니다. 성분 응력·주응력·최대전단·유효응력·팔면체 응력을 포함합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 솔리드(Solid) 요소의 절점 부재력을 요소 국부 좌표계(Local) 기준으로 추출합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 솔리드(Solid) 요소의 절점 부재력을 전역 좌표계(Global) 기준으로 추출합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 솔리드(Solid) 요소의 응력을 요소 국부 좌표계(Local) 기준으로 추출합니다. 6성분 응력·주응력(Sig-P1/P2/P3)과 각 주응력의 방향 코사인(P1/ux·uy·uz 등)·최대전단… | 0 |
| `/post/TABLE` | POST | `result` | execute | 솔리드(Solid) 요소의 응력을 전역 좌표계(Global) 기준으로 추출합니다. 6성분 응력·주응력·방향 코사인·최대전단·유효응력·팔면체 응력을 포함합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 솔리드(Solid) 요소의 변형률을 요소 국부 좌표계(Local) 기준으로 추출합니다. 소성/전체 변형률을 선택할 수 있으며, 비선형·시공단계의 `Step`별로 조회됩니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 솔리드(Solid) 요소의 변형률을 전역 좌표계(Global) 기준으로 추출합니다. 소성/전체 변형률을 선택할 수 있으며, 비선형·시공단계의 `Step`별로 조회됩니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 탄성 링크(Elastic Link) 요소의 부재력(축력·전단·비틀림·모멘트)을 절점별로 추출합니다. 일반/최댓값 기준(by-max)을 선택할 수 있습니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 일반 링크(General Link) 요소의 부재력(축력·전단·비틀림·모멘트) 또는 변형(Deform)을 추출합니다. 부재력은 일반/최댓값 기준(by-max)을 선택할 수 있습니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 고유치 해석(Eigenvalue) 진동 모드형상 또는 참여벡터(Participation Vector) 모드형상을 절점별·모드별로 추출합니다(병진 UX·UY·UZ, 회전 RX·RY·RZ). | 0 |
| `/post/TABLE` | POST | `result` | execute | 좌굴 해석(Buckling)의 모드형상을 절점별·모드별로 추출합니다(병진 UX·UY·UZ, 회전 RX·RY·RZ). | 0 |
| `/post/TABLE` | POST | `result` | execute | 텐던(Tendon)의 프로파일 좌표(x·y·z)를 텐던별·구간(No)별로 추출합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 텐던(Tendon)의 신장량(Elongation)을 시공단계(Stage)·스텝(Step)별로 추출합니다. 텐던 자체 신장·요소 신장·합계를 시작단(Begin)/종단(End)으로 구분합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 텐던(Tendon)의 요소 내 배치 정보(단면 위치 Yp·Zp, 평균 방향 sin/cos, 평균 응력·평균 힘)를 요소·위치(Part)·텐던 번호별로 추출합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 텐던(Tendon)의 손실(Loss)을 요소·위치(Part)별로 추출합니다. 즉시 손실 후 응력, 탄성변형 손실, 크리프/건조수축 손실, 릴랙세이션 손실, 전체 손실 후/즉시 손실 후 응력비,… | 0 |
| `/post/TABLE` | POST | `result` | execute | 텐던(Tendon)의 물량(Weight)을 그룹별/형상별/특성별로 추출합니다. 텐던 개수·단면적·길이·단위 길이당 중량·중량·총중량을 포함합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 텐던(Tendon)의 응력 한계 검토 결과를 추출합니다. 텐던 응력(f_p1·f_p2·f_pe)과 정착부/정착부 이격/사용상태 응력 한계를 비교합니다. `ADDITIONAL.REDUCTION_… | 0 |
| `/post/TABLE` | POST | `result` | execute | 텐던(Tendon)의 근사 손실(Approximate Loss)을 요소·위치(Part)별로 추출합니다. 즉시 손실, 크리프/건조수축/릴랙세이션 손실, 전체 손실과 즉시/전체 손실 후 응력 및 … | 0 |
| `/post/TABLE` | POST | `result` | execute | 시공단계 합성단면(Composite Section for Construction Stage)의 부재력/응력을 단면 파트(SectionPart)·부재 위치(Part)별로 추출합니다. 축력·모멘트… | 0 |
| `/post/TABLE` | POST | `result` | execute | 시공단계 합성단면의 자기구속(Self-Constraint) 부재력/응력을 단면 파트(SectionPart)·부재 위치(Part)별로 추출합니다. 온도구배(TG) 등 자기평형 하중에 대한 축력·… | 0 |
| `/post/TABLE` | POST | `result` | execute | 벽체(Wall) 요소의 부재력/모멘트를 층(Story)·레벨(top/bot)별로 추출합니다. 일반 Plate Force와 달리 `STORY_NAMES`로 층을 지정할 수 있고, 응답에 상/하단… | 0 |

### 21. POST — Analysis Story Tables （17 个）

来源：`docs/manual/21_POST_StoryTables.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/post/TABLE` | POST | `result` | execute | 각 층의 층간변위(Story Drift)와 층간변위비(Story Drift Ratio)를 추출합니다. X/Y 각 방향과 조합(Combined)에 대해 허용 층간변위비 초과 여부(OK/NG)를 … | 0 |
| `/post/TABLE` | POST | `result` | execute | 각 층 절점의 최대변위·평균변위 및 그 비(Maximum/Average)를 추출합니다. 비틀림 거동 및 층 변위 분포 확인에 사용합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 응답스펙트럼(R.S.) 해석 결과로부터 각 층의 관성력(Inertia Force), 스프링 반력 포함/미포함 전단력, 편심(Eccentricity), 층력(Story Force), 편심모멘트를… | 0 |
| `/post/TABLE` | POST | `result` | execute | 응답스펙트럼 해석의 층별 전단력과 누적 중량합(Weight Sum)으로부터 층전단력계수(Story Shear Force Coefficient)를 X/Y방향으로 산정합니다. **`(RS)` 하중… | 0 |
| `/post/TABLE` | POST | `result` | execute | 각 층 대표 절점의 모드별 변위 형상(UX, UY, UZ, RX, RY, RZ)을 추출합니다. 층 단위 모드 형상 확인 및 동적 거동 평가에 사용합니다. **모드 해석(R.S.) 결과가 필요합… | 0 |
| `/post/TABLE` | POST | `result` | execute | 각 층에 대해 부재 유형(Frame/Wall 등)별 전단력과 전체 층전단력에 대한 분담률(Ratio)을 두 방향(Angle1/Angle2)으로 추출합니다. 부재별 전단력 분담 검토에 사용합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 각 층의 무게중심(Weight Center)·강성중심(Stiffness Center) 좌표, 편심거리(Ecc. Dist.), 비틀림 강성, 탄성반경(El. Radius), 편심비(Ecc. Ra… | 0 |
| `/post/TABLE` | POST | `result` | execute | 각 층의 전도모멘트(Overturning Moment)를 부재 유형(Frame/Wall)별 분담값·분담비와 함께 두 방향(Angle1/Angle2)에 대해 추출합니다. 전도 안정성 및 벽체/골… | 0 |
| `/post/TABLE` | POST | `result` | execute | 각 층 수직부재(기둥·벽체)의 축력 합(Axial Force Sum)과 축력 중심(Center of Axial Forces) 좌표를 추출합니다. 층 수직하중 분포 및 축력 중심 확인에 사용합니다. | 0 |
| `/post/TABLE` | POST | `result` | execute | 각 층의 안정계수(Stability Coefficient, θ)를 수직하중·층전단력·수정 층간변위로부터 산정하고 허용한계(Allowable Limit) 초과 여부(OK/NG)와 P-Delta … | 0 |
| `/post/TABLE` | POST | `result` | execute | 비틀림 불규칙(Torsional Irregularity) 검토 테이블입니다. 극단부 층간변위의 평균 및 1.2배 값과 최대값(Maximum Value)을 비교하여 비틀림 불규칙 여부(Regul… | 0 |
| `/post/TABLE` | POST | `result` | execute | 비틀림 증폭계수(Torsional Amplification Factor, Ax)를 산정합니다. 극단부 평균변위와 최대변위(Maximum Displacement)의 비를 이용하여 우발 비틀림모멘… | 0 |
| `/post/TABLE` | POST | `result` | execute | 강성 불규칙(연층, Soft Story) 검토 테이블입니다. 각 층 강성(Story Stiffness)을 상부층 강성의 0.7배(0.7Ku1)·0.8배 평균(0.8Ku123)과 비교하고 층강성… | 0 |
| `/post/TABLE` | POST | `result` | execute | 강도 불규칙(약층, Weak Story) 검토 테이블입니다. 각 층의 전단강도(Story Shear Strength)를 상부층 전단강도와 비교하여 전단강도비(Story Shear Strengt… | 0 |
| `/post/TABLE` | POST | `result` | execute | 평면 정형성(Regularity in Plan) 판정 기준 테이블입니다. 병진질량(Translational Mass)·회전질량(Rotational Mass), 회전반경비(Rx), r²/Is² … | 0 |
| `/post/TABLE` | POST | `result` | execute | 설계 층전단력 검토(Ultimate Story Shear Force Check) 테이블입니다. 작용 전단력(Applied Shear Force, Ve)과 시계방향/반시계방향 극한전단력(Ulti… | 0 |
| `/post/TABLE` | POST | `result` | execute | 중량 불규칙(Weight Irregularity) 검토 테이블입니다. 각 층 중량(Story Weight)을 인접(하부) 층 중량의 1.25배·0.75배와 비교하여 중량비(Story Weigh… | 0 |

### 22. POST – TH / HY / Pushover Result Tables （28 个）

来源：`MIDAS-API-main/docs/manual/22_POST_TH_HY_Pushover.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/post/TEXT` | POST | `result` | execute | A-1 Time History Text – Node Results — 시간이력 해석에서 절점(Node)의 변위·속도·가속도를 시간 스텝별로 추출합니다(TEXT_TYPE: TH_DISP / TH… | 0 |
| `/post/TEXT` | POST | `result` | execute | A-2 Time History Text – Element Result(Truss, Beam, Plane Stress/Strain, Solid) — 시간이력 해석의 트러스·보·평면응력·평면변형·… | 0 |
| `/post/TEXT` | POST | `result` | execute | A-3 Time History Text – Element Result(Plate) — 시간이력 해석의 평판(Plate) 요소 부재력·단위 부재력·응력을 추출합니다(TEXT_TYPE: TH_PL… | 0 |
| `/post/TEXT` | POST | `result` | execute | A-4 Time History Text – Element Result(Wall) — 시간이력 해석의 벽체(Wall) 요소 부재력을 추출합니다(TEXT_TYPE: TH_WALLFORCE). | 0 |
| `/post/TEXT` | POST | `result` | execute | A-5 Time History Text – General Link Result — 시간이력 해석의 일반 링크(General Link) 부재력과 변형을 추출합니다(TEXT_TYPE: TH_GLI… | 0 |
| `/post/TEXT` | POST | `result` | execute | A-6 Pushover Text – Displacement — 푸시오버(Pushover) 해석에서 절점의 변위를 스텝별로 추출합니다(하중케이스는 PO_CASE_NAME으로 지정, TEXT_TY… | 0 |
| `/post/TEXT` | POST | `result` | execute | A-7 Pushover Text – Element Result(Beam, Truss) — 푸시오버 해석의 보·트러스 요소 부재력/응력을 스텝별로 추출합니다(TEXT_TYPE: PO_BEAMFO… | 0 |
| `/post/TEXT` | POST | `result` | execute | A-8 Pushover Text – Element Result(Wall) — 푸시오버 해석의 벽체(Wall) 요소 부재력을 스텝별로 추출합니다(TEXT_TYPE: PO_WALLFORCE). | 0 |
| `/post/TEXT` | POST | `result` | execute | A-9 Pushover Text – General Link — 푸시오버 해석의 일반 링크(General Link) 부재력·변형을 스텝별로 추출합니다(TEXT_TYPE: PO_GLINKFORCE… | 0 |
| `/post/TEXT` | POST | `result` | execute | A-10 Pushover Text – Elastic Link — 푸시오버 해석의 탄성 링크(Elastic Link) 부재력·변형을 스텝별로 추출합니다(TEXT_TYPE: PO_ELINKFORC… | 0 |
| `/post/TABLE` | POST | `result` | execute | B-1 Inelastic Hinge Event Time — 비탄성 힌지의 1차/2차/3차 항복 발생 시각(Event Time)을 6개 성분(Dx~Rz)별로 추출합니다(TABLE_TYPE 접미사… | 0 |
| `/post/TABLE` | POST | `result` | execute | B-2 Inelastic Hinge Beam Summary — 비탄성 보(Beam) 힌지의 성분별(Dx/Dy/Dz/Ry/Rz) 요약을 추출합니다(변형·부재력·연성도 max(D/D1)·max(D… | 0 |
| `/post/TABLE` | POST | `result` | execute | B-3 Inelastic Hinge Truss Summary — 비탄성 트러스(Truss) 힌지의 요약(Dx)을 추출합니다(TABLE_TYPE: IEHG_TRUSS_SUM_DX). | 0 |
| `/post/TABLE` | POST | `result` | execute | B-4 Inelastic Hinge General Link Summary — 비탄성 일반링크(General Link) 힌지의 성분별(Dx/Dy/Dz/Rx/Ry/Rz) 요약을 추출합니다(TABL… | 0 |
| `/post/TABLE` | POST | `result` | execute | B-5 Inelastic Hinge Force — 비탄성 힌지의 최대 부재력(Force)과 발생 시각(Time)을 6개 성분(Fx~Mz)별로 추출합니다(접미사 LUMPED/DIST/SPRING… | 0 |
| `/post/TABLE` | POST | `result` | execute | B-6 Inelastic Hinge Deformation — 비탄성 힌지의 최대 변형(Deform)과 발생 시각(Time)을 6개 성분(Dx~Rz)별로 추출합니다(접미사 LUMPED/DIST/… | 0 |
| `/post/TABLE` | POST | `result` | execute | B-7 Inelastic Hinge Element Rotation — 비탄성 힌지 요소의 회전(Rotation)과 발생 시각(Time)을 Ry·Rz 성분으로 추출합니다(TABLE_TYPE: I… | 0 |
| `/post/TABLE` | POST | `result` | execute | B-8 Inelastic Hinge Ductility Factor(D/D1) — 비탄성 힌지의 연성도 계수 D/D1(1차 항복 대비) 최댓값과 발생 시각을 6개 성분별로 추출합니다(접미사 LU… | 0 |
| `/post/TABLE` | POST | `result` | execute | B-9 Inelastic Hinge Ductility Factor(D/D2) — 비탄성 힌지의 연성도 계수 D/D2(2차 항복 대비) 최댓값과 발생 시각을 6개 성분별로 추출합니다(접미사 LU… | 0 |
| `/view/RESULTGRAPHIC` | POST | `result` | execute | C-1 Stress – Heat of Hydration — 수화열 해석의 응력(Stress) 결과를 지정 스텝에서 컨투어/벡터로 표시합니다(CURRENT_MODE: HY_STRESS). | 0 |
| `/view/RESULTGRAPHIC` | POST | `result` | execute | C-2 Temperature – Heat of Hydration — 수화열 해석의 온도(Temperature) 분포를 지정 스텝에서 컨투어로 표시합니다(CURRENT_MODE: HY_TEMPE… | 0 |
| `/view/RESULTGRAPHIC` | POST | `result` | execute | C-3 Displacements – Heat of Hydration — 수화열 해석의 변위(Displacements)를 성분별로 지정 스텝에서 표시합니다(CURRENT_MODE: HY_DISP… | 0 |
| `/view/RESULTGRAPHIC` | POST | `result` | execute | C-4 Allowable Tensile Stress – Heat of Hydration — 수화열 해석의 허용 인장응력(Allowable Tensile Stress)을 지정 스텝에서 컨투어로 … | 0 |
| `/view/RESULTGRAPHIC` | POST | `result` | execute | C-5 Crack Ratio – Heat of Hydration — 수화열 해석의 균열 지수(Crack Ratio)를 지정 스텝에서 컨투어로 표시합니다(온도응력에 의한 균열 발생 위험 평가용,… | 0 |
| `/db/THRE` | POST, GET, PUT, DELETE | `dynamic_load` | create, read, update, delete | D-1 Element Force Smart Graph – db/THRE — 요소 부재력(Element Force)을 시간이력 스마트 그래프로 추출하기 위한 정의 레코드를 생성/조회/수정/삭제합니다. | 0 |
| `/db/THRG` | POST, GET, PUT, DELETE | `dynamic_load` | create, read, update, delete | D-2 General Link Smart Graph – db/THRG — 일반 링크(General Link) 결과를 시간이력 스마트 그래프로 추출하기 위한 정의 레코드를 생성/조회/수정/삭제합니다. | 0 |
| `/db/THRI` | POST, GET, PUT, DELETE | `dynamic_load` | create, read, update, delete | D-3 Inelastic Hinge Smart Graph – db/THRI — 비탄성 힌지(Inelastic Hinge) 결과를 시간이력 스마트 그래프로 추출하기 위한 정의 레코드를 생성/조회… | 0 |
| `/db/THRS` | POST, GET, PUT, DELETE | `dynamic_load` | create, read, update, delete | D-4 Seismic Devices Smart Graph – db/THRS — 지진 보호 장치(Seismic Devices, 감쇠기/면진장치 등)의 결과를 시간이력 스마트 그래프로 추출하기 위… | 0 |

### 23. POST – Design Tables （10 个）

来源：`MIDAS-API-main/docs/manual/23_POST_Design.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/post/PM` | POST | `design` | execute | P-M Interaction Diagram — RC/SRC 기둥·부재의 P-M 상관도(축력–모멘트 상관곡선) 데이터를 별도 인자 없이(빈 Argument) 현재 모델의 설계 결과 전체에 대해 … | 0 |
| `/post/STEELCODECHECK` | POST | `design` | execute | Steel Code Check — 강재 부재의 설계 코드 체크 결과(단면·요소별 조합 강도비 RAT, 세장비 SLN, 처짐 DEF, 허용처짐 DEFA)를 별도 인자 없이(빈 Argument) … | 0 |
| `/post/TABLE` | POST | `design` | execute | Concrete Design – Beam Design Forces — RC 설계용 보(Beam) 부재 설계력을 추출합니다(휨설계 기준의 축력·비틀림·정/부 모멘트, TABLE_TYPE: BEA… | 0 |
| `/post/TABLE` | POST | `design` | execute | Concrete Design – Column Design Forces — RC 설계용 기둥(Column) 부재 설계력(3축 힘·모멘트)을 추출합니다(TABLE_TYPE: COLUMNDESIGN… | 0 |
| `/post/TABLE` | POST | `design` | execute | Concrete Design – Brace Design Forces — RC 설계용 가새(Brace) 부재 설계력(3축 힘·모멘트)을 추출합니다(응답 구조는 기둥과 동일, TABLE_TYPE:… | 0 |
| `/post/TABLE` | POST | `design` | execute | Concrete Design – Wall Design Forces — RC 설계용 벽체(Wall) 부재 설계력을 추출합니다(벽체 ID `WID`와 층 `Story` 정보가 추가되며, `STOR… | 0 |
| `/post/TABLE` | POST | `design` | execute | Steel Design – Steel Member Design Forces — 강재 설계용 부재 설계력(3축 힘·모멘트)을 추출합니다(TABLE_TYPE: STEELMEMBERDESIGNFOR… | 0 |
| `/post/TABLE` | POST | `design` | execute | SRC Design – SRC Beam Design Forces — SRC(철골 철근콘크리트 합성) 설계용 보 부재 설계력을 추출합니다(RC 보와 유사하나 정/부 모멘트 열 순서가 `My(+)… | 0 |
| `/post/TABLE` | POST | `design` | execute | SRC Design – SRC Column Design Forces — SRC 설계용 기둥 부재 설계력(3축 힘·모멘트)을 추출합니다(TABLE_TYPE: SRCCOLUMNDESIGNFORCES). | 0 |
| `/post/TABLE` | POST | `design` | execute | Cold Formed Design – Cold Formed Steel Member Design Forces — 냉간성형강(Cold Formed Steel) 설계용 부재 설계력(3축 힘·모멘트)… | 0 |

### 24. DB — Design （13 个）

来源：`docs/manual/24_DB_Design.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/db/DCON` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | RC Design Code — RC(철근콘크리트) 부재 설계에 사용할 설계 기준(Design Code)을 `DGNCODE` 문자열로 지정/조회한다. KDS·KCI·ACI·Eurocode·AAS… | 0 |
| `/db/DSTL` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Design Steel Code — 강재(Steel) 부재 설계에 사용할 설계 기준을 `DGNCODE` 문자열로 지정/조회한다. KDS·KSSC·AISC·Eurocode3·AASHTO 등을 지… | 0 |
| `/db/RCHK` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Rebar Input for Checking - Beam/Column — 설계 검토(Checking) 시 사용할 실제 배근 정보를 부재(요소)별로 입력한다. `MEMBTYPE`에 따라 **BE… | 0 |
| `/db/LENG` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Unbraced Length — 부재의 좌굴 검토에 사용할 비지지 길이(Unbraced Length)를 요소별로 입력한다. 강축/약축(Ly, Lz)과 횡비틀림 좌굴 길이(Lb, Lt)를 지정하… | 0 |
| `/db/MEMB` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Member Assignment — 여러 요소를 하나의 설계 부재(Design Member)로 묶어 배정한다. `AELEM`에 요소 번호 배열을 넣고, 필요 시 국부좌표 방향을 반전(`bREV… | 0 |
| `/db/DCTL` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Definition of Frame — 설계 시 프레임의 좌굴 거동(횡구속/비횡구속) 및 유효좌굴길이계수(K) 자동 계산 여부, 설계 평면(Design Type)을 정의한다. | 0 |
| `/db/LTSR` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Limiting Slenderness Ratio — 부재의 압축/인장 한계 세장비(Limiting Slenderness Ratio)를 요소별로 지정하거나 검토를 생략(`bNOTCHECK`)한다. | 0 |
| `/db/MBTP` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Modify Member Type — 요소의 설계 부재 타입(Column / Beam / Brace)을 지정·변경한다. | 0 |
| `/db/WMAK` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Modify Wall Mark Design — 설계용 벽체 마크(Wall Mark)를 정의한다. 마크 이름(`MARKNAME`)과 해당 마크에 속하는 벽체 ID 목록(`WID_LIST`)을 지… | 0 |
| `/db/REBB` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Modify Beam Rebar Data — 단면(section) 번호별로 콘크리트 보의 철근 데이터를 수정한다. 각 `ITEMS` 항목은 I·M·J 세 구간(`BAR_SECTOR_I/M/J`… | 0 |
| `/db/REBC` | POST | `design` | create | Modify Column Rebar Data — 단면 번호별로 콘크리트 기둥의 철근 데이터를 수정한다. 주철근(`MAIN_BAR`), 단부/중앙부 전단철근(`SHEAR_BAR_END`/`SHE… | 0 |
| `/db/REBW` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Modify Wall Rebar Data — 벽체 ID별로 철근 데이터를 수정한다. 수직/수평 철근, 단부 철근(End Rebar), 경계요소(Boundary Element) 수평 철근, 피복… | 0 |
| `/db/REBR` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Modify Brace Rebar Data — 단면 번호별로 콘크리트 가새(Brace)의 철근 데이터를 수정한다. 구조는 기둥(REBC)과 유사하나 `USE_CORNER`/`HOOK_TYPE`… | 0 |

### 25. Design Code — STEEL KDS 41 30:2022 （28 个）

来源：`docs/manual/25_Design_Steel_KDS41302022.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/DESIGN/STEEL/DSTL` | GET, PUT, DELETE | `design` | read, update, delete | Design Code — 현재 프로젝트에 적용할 **강재 설계 코드**를 선택한다. `DGNCODE`는 `"KDS 41 30 : 2022"` 1개 값만 지원하며, 이 장의 나머지 27개(`KD… | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/DCO` | GET, PUT, DELETE | `design` | read, update, delete | Design Code Option — 강재 설계 기준(KDS 41 30:2022) 및 횡지지 가정·처짐검토·내진 특별규정·원형단면 조합비 방법 등 전역 설계 옵션을 설정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/DCTL` | GET, PUT, DELETE | `design` | read, update, delete | Definition of Frame — 설계 프레임의 X/Y 방향 횡지지 여부(Sway/Non-sway), 유효좌굴길이계수 자동계산, 설계 타입(3D/평면)을 정의한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/LLRF` | GET, PUT, DELETE | `design` | read, update, delete | Live Load Reduction Factor — 층·평면 범위(XMIN~XMAX, YMIN~YMAX)별 활하중 저감계수 테이블(`REDUCTION_DATA`)과 적용 성분(축력/모멘트/전단… | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/LCTB` | GET, DELETE | `design` | read, delete | Load Contribution for Nonlinear Load Case — 비선형 해석 하중케이스에 대한 하중 기여(Load Contribution) 정의를 조회/삭제한다. 각 레코드는 `… | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/SRDF` | GET, DELETE, PUT | `design` | read, delete, update | Strength Reduction Factors — 인장/압축/휨/전단에 대한 강도감소계수(φ) 값을 설정한다. φ_t2(순단면 파단)는 0.75 고정(read-only)이다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/SERV` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Serviceability Parameters — 부재별 처짐 제어값(Deflection Control, span/n)과 처짐 증폭계수(DAF)를 설정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/EQCT` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Seismic Load Combination Type — 부재별로 특별 지진하중(Special Seismic Loads) 또는 수직 지진력(Vertical Seismic Forces) 적용 타… | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/ULCT` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Underground Load Combination Type — 부재별로 지하 하중조합(Underground Loads) 적용 여부를 배정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/SUEQ` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Scale up Factor for Earthquake — 부재별로 하중케이스/하중조합의 축력·모멘트·전단 지진 증폭계수를 설정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/CRCM` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Combined Ratio Calculation Method for Circular Section — 원형(관형) 단면의 조합강도 계산 방법(SRSS / Linear Sum)을 부재별로 설정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/HCBM` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Haunched Beam Assignment — 요소를 Part A/B/C로 그룹화하여 헌치 보(Haunched Beam) 설계 부재를 정의한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/LENG` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Unbraced Length — 부재별 비지지 길이(Ly, Lz), 횡비지지 길이(Lb), 비틀림 비지지 길이(Lt)를 설정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/KFAC` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Effective Length Factor — 부재별 유효좌굴길이계수 Ky, Kz, Kt를 설정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/LTSR` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Limiting Slenderness Ratio — 부재별 압축/인장 세장비 제한값을 설정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/CMFT` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Equivalent Moment Correction Factor — 부재별 등가모멘트 보정계수 CMy, CMz를 자동계산 또는 사용자값으로 설정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/FMAG` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Moment Magnifier — 부재별 1차/2차 모멘트 증폭계수(B1y·B1z, B2y·B2z)를 설정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/CBFT` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Bending Coefficient — 부재별 횡좌굴 휨계수 Cb를 자동계산 또는 사용자값으로 설정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/MBTP` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Modify Member Type — 요소의 설계 부재 타입(Column/Beam/Brace)을 변경한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/SLRS` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Seismic Load Resisting System by Member — 부재별 내진 저항 골조 타입(가새골조/편심가새/좌굴방지가새/특수전단벽)과 검토 옵션을 설정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/MLLR` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Modify Live Load Reduction Factor — 부재별 활하중 저감계수(0.3~1.0)와 적용 성분(축력/모멘트/전단)을 개별 수정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/MEMB` | GET, PUT, DELETE | `design` | read, update, delete | Member Assignment — 설계 부재 ID에 요소 리스트(`AELEM`)를 배정하고 로컬 방향 반전(`bREVERSE`) 여부를 지정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/SMODI` | GET, PUT, DELETE | `design` | read, update, delete | Modify Steel Material — 재질 ID별로 강재 재질을 표준코드(KS22(S)) 기반 또는 사용자정의(None)로 수정한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/CODE-ANAL` | POST | `design` | execute | Steel Code Check Perform — 전체(`ALL`)/요소별(`ELEMS`)/단면별(`SECTIONS`) 대상에 대해 강재 코드 검토(설계 계산)를 실행한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/CODE-TABLE` | POST | `design` | execute | Steel Code Check Table — 강재 코드 검토 결과를 표(부재기준 MEMB / 단면기준 PROP) 형태로 반환한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/CODE-REPORT` | POST | `design` | execute | Steel Code Check Report — 강재 코드 검토 보고서를 Graphic(JPG)/Detail(DOC)/Summary(TXT) 형식으로 파일에 출력한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/DREULT` | POST | `design` | execute | Steel Design Result — 강재 설계 결과를 화면에 표시하고 이미지(JPG)로 캡처·저장한다. | 0 |
| `/DESIGN/STEEL/KDS-41-30-2022/TABLE` | POST | `design` | execute | Steel Member Design Forces — 강재 설계 부재력 표(`STEELMEMBERDESIGNFORCES`)를 반환하거나 파일로 저장한다. | 0 |

### 26. Design Code — RC KDS 41 20:2022 （70 个）

来源：`docs/manual/26_Design_RC_KDS41202022.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/DESIGN/RC/DRC` | GET, PUT, DELETE | `design` | read, update, delete | 현재 프로젝트에 적용할 **RC 설계 코드**를 선택합니다. 이 챕터의 나머지 69개 엔드포인트(`KDS-41-20-2022/<CODE>`)와 달리 URI가 `KDS-41-20-2022` 접두… | 0 |
| `/DESIGN/RC/KDS-41-20-2022/DCO` | GET, PUT, DELETE | `design` | read, update, delete | 콘크리트 설계 기준(KDS 41 20:2022) 및 내진 특별규정·비틀림·모멘트 재분배·노출조건·P-M 곡선 산정법 등 전역 설계 옵션을 설정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/DCTL` | GET, PUT, DELETE | `design` | read, update, delete | 설계 프레임의 X/Y 방향 횡지지 여부(Sway/Non-sway), 유효좌굴길이계수 자동계산, 설계 타입(3D/평면)을 정의합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/LLRF` | GET, PUT, DELETE | `design` | read, update, delete | 층별·범위별 활하중 저감계수 표를 정의합니다. 적용 성분(축력/모멘트/전단), 계산 규칙, 대상 활하중 케이스를 지정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/LCTB` | GET, DELETE | `design` | read, delete | 비선형 해석 하중케이스의 하중기여(Load Contribution) 항목을 조회·삭제합니다. 각 항목은 계수와 하중케이스명으로 구성됩니다. (읽기 전용 파생 정보 — GET/DELETE만 지원) | 0 |
| `/DESIGN/RC/KDS-41-20-2022/SRDF` | GET, PUT, DELETE | `design` | read, update, delete | 인장지배·나선철근·기타철근 부재·전단/비틀림에 대한 강도감소계수 φ 값을 설정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/EQCT` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 부재별로 특수 지진하중(Special Seismic Loads) 또는 수직 지진력(Vertical Seismic Forces) 적용 타입을 배정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/ULCT` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 부재별로 지하(Underground) 하중조합 적용 여부를 배정합니다. true=지하하중용, false=비지하하중용. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/SUEQ` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 부재별로 하중케이스(LC) 및 하중조합(LCOM)의 축력·모멘트·전단 각각에 대한 지진 스케일업(증폭) 계수를 지정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/SDGN` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 부재별 내진설계 타입을 배정합니다. 내진(Seismic)/비내진(Non-Seismic)/비내진 저항시스템(Non-Seismic-Force-Resisting) 중 선택합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/SCOL` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 부재(기둥)별 층 타입을 배정합니다. 필로티(PILOTI) 또는 연약층(SOFT_STORY)으로 분류합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/MBTP` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 요소별 설계 부재 타입을 기둥(COLUMN)/보(BEAM)/가새(BRACE)로 수정 배정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/MEMB` | GET, PUT, DELETE | `design` | read, update, delete | 여러 요소를 하나의 설계 부재로 묶어 배정합니다. 요소 리스트와 국부좌표 방향 반전 여부를 지정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/MATD` | GET, PUT, DELETE | `design` | read, update, delete | 재질 ID별 콘크리트·철근 재료를 수정합니다. 표준코드(Standard) 또는 사용자정의(None)로 등급/강도/경량 계수를 지정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/LENG` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 부재별 비지지 길이 Ly·Lz, 횡좌굴 비지지 길이 Lb, 비틀림 비지지 길이 Lt를 지정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/KFAC` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 부재별 유효좌굴길이계수 Ky·Kz·Kt를 지정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/CMFT` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 부재별 등가모멘트 보정계수 CMy·CMz를 지정하거나 자동계산(OPT_AUTO)을 선택합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/FMAG` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 부재별 모멘트 확대계수를 지정합니다. B1(δb)은 1차(비횡변위) 모멘트, B2(δs)는 2차(횡변위) 모멘트에 대한 계수입니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/MLLR` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 부재별 활하중 저감계수와 적용 성분(축력/모멘트/전단)을 개별 수정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/HCBM` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 헌치보(Haunched Beam)를 Part A/B/C 요소 구성으로 배정합니다. 각 파트는 요소 ID 목록(KEYS) 또는 ID 범위(TO)로 지정하며, 설계 위치 타입(Part 1/2 또는… | 0 |
| `/DESIGN/RC/KDS-41-20-2022/MRFT` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 보 부재별 모멘트 재분배 계수를 지정합니다. 보(Beam) 부재 타입에만 적용됩니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/TRFT` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 보 부재별 비틀림 감소계수를 지정합니다. 보(Beam) 부재 타입에만 적용됩니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/MCMB` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 보 부재별 모멘트 산정 방법을 지정합니다. Each(각 경간별) 또는 Equivalent Frame(등가 골조) 중 선택합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/DFBA` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 부재로 배정된 보의 설계력 타입을 지정합니다. Subdivided Forces(세분화 부재력) 또는 Member Forces(부재력) 중 선택합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/PMDM` | POST, GET, DELETE, PUT | `design` | create, read, update, delete | 부재별 P-M 상관도(interaction) 설계 산정 방법을 지정합니다. P(축력 고정) 또는 M/P(모멘트/축력비 고정) 중 선택합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/WMAK` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 벽체 마크(Wall Mark)를 정의합니다. 마크 이름과 대상 벽체 ID 목록을 지정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/BEMW` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 벽체별 경계요소법(Boundary Element Method) 사용 여부와 방식(변위/응력 기반), 최하층 지정 여부 및 층 이름을 설정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/REXC` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 부재별 철근 노출 조건(Rebar Exposure Condition)을 지정합니다. Dry(건조) 또는 Etc(기타) 중 선택합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/LMRR` | GET, PUT, DELETE | `design` | read, update, delete | 설계별 최대 철근비 상한을 설정합니다. 전단벽(Rhow)·기둥(Rhoc)·가새(Rhor) 각각의 최대 철근비를 지정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/DCRM-BEAM` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 보(Beam) **부재 ID별**로 철근 설계기준(주철근·스터럽·다리 수·측면철근·피복·복철근·간격제한·이음)을 개별 지정합니다. 전역 기준(`DCRE`)을 특정 부재에 덮어쓸 때 사용합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/DCRM-COLUMN` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 기둥(Column) **부재 ID별**로 철근 설계기준(주철근·띠철근/나선철근·Y/Z 방향 다리 수·피복·간격제한·이음)을 개별 지정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/DCRM-BRACE` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 가새(Brace) **부재 ID별**로 철근 설계기준을 지정합니다. 필드 구성은 기둥(`DCRM-COLUMN`)과 동일합니다(주철근·띠철근·Y/Z 다리 수·피복·간격제한·이음). | 0 |
| `/DESIGN/RC/KDS-41-20-2022/DCRM-WALL` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 벽체(Wall) **ID별**로, 그리고 각 ID 내에서 **층(Story)별**로 철근 설계기준(수직·수평·단부 철근, 경계요소 수평철근, 경계요소 수평/수직 간격, 피복 de/dw)을 개별… | 0 |
| `/DESIGN/RC/KDS-41-20-2022/DCRE` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 모델 **전역**의 RC 철근 설계기준을 부재 종류별(`BEAM`·`COLUMN`·`BRACE`·`WALL`)로 한 번에 설정합니다. 보/기둥/가새는 `DCRM-*` 와 유사한 필드를 가지되 … | 0 |
| `/DESIGN/RC/KDS-41-20-2022/DCREM` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 접합부(절점)에서 만나는 보들의 철근을 **동일하게** 처리하기 위한 설정입니다. 전체 부재에 적용하거나(`SELECT_ALL`), 특정 절점(node)별로 그 절점을 사이에 두는 **정확히 … | 0 |
| `/DESIGN/RC/KDS-41-20-2022/REBB` | POST, GET, DELETE, PUT | `design` | create, read, update, delete | 단면(section) 번호별로 콘크리트 보의 철근 데이터를 수정합니다. 각 `ITEMS` 항목은 I·M·J 세 구간(`BAR_SECTOR_I/M/J`)의 상·하단 주철근(레이어별), 스터럽(전… | 0 |
| `/DESIGN/RC/KDS-41-20-2022/REBC` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 단면 번호별로 콘크리트 기둥의 철근 데이터를 수정합니다. 주철근(`MAIN_BAR`), 단부/중앙부 전단철근(`SHEAR_BAR_END`/`SHEAR_BAR_CEN`), 피복 거리(`DO`),… | 0 |
| `/DESIGN/RC/KDS-41-20-2022/REBW` | POST, PUT, DELETE, GET | `design` | create, read, update, delete | 벽체 ID별로 철근 데이터를 수정합니다. 수직/수평 철근, 단부 철근(End Rebar), 경계요소(Boundary Element) 수평 철근, 피복 거리(dw, de), 두께 및 서브 벽체 … | 0 |
| `/DESIGN/RC/KDS-41-20-2022/REBR` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | 단면 번호별로 콘크리트 가새(Brace)의 철근 데이터를 수정합니다. 구조는 기둥(`REBC`)과 유사하나 `MAIN_BAR` 에 `USE_CORNER` 가 없고 후크 타입(`HOOK_TYPE… | 0 |
| `/DESIGN/RC/KDS-41-20-2022/BD-ANAL` | POST | `design` | execute | 지정한 요소 · 단면(또는 전체)에 대해 RC 보 설계 계산을 수행합니다. 결과는 모델에 저장되며 이후 `BD-TABLE` / `BD-REPORT` 로 조회합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/BD-TABLE` | POST | `design` | execute | 수행된 RC 보 설계 결과를 표(HEAD/DATA) 형태로 반환합니다. 부재별(MEMB) 또는 단면 속성별(PROP)로 조회할 수 있습니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/BD-REPORT` | POST | `design` | execute | RC 보 설계 결과를 Graphic(JPG) · Detail(DOC) · Summary(TXT) 형식의 파일로 출력합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/CD-ANAL` | POST | `design` | execute | 지정한 요소 · 단면(또는 전체)에 대해 RC 기둥 설계 계산을 수행합니다. 결과는 이후 `CD-TABLE` / `CD-REPORT` 로 조회합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/CD-TABLE` | POST | `design` | execute | 수행된 RC 기둥 설계 결과를 표(HEAD/DATA) 형태로 반환합니다. P-M 상관 및 전단 검토 결과를 포함합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/CD-REPORT` | POST | `design` | execute | RC 기둥 설계 결과를 Graphic(JPG) · Detail(DOC) · Summary(TXT) · PM Curve(JPG) 형식의 파일로 출력합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/BRD-ANAL` | POST | `design` | execute | 지정한 요소 · 단면(또는 전체)에 대해 RC 가새(Brace) 설계 계산을 수행합니다. 결과는 이후 `BRD-TABLE` / `BRD-REPORT` 로 조회합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/BRD-TABLE` | POST | `design` | execute | 수행된 RC 가새 설계 결과를 표(HEAD/DATA) 형태로 반환합니다. 축력-휨(P-M) 및 전단 검토 결과를 포함합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/BRD-REPORT` | POST | `design` | execute | RC 가새 설계 결과를 Graphic(JPG) · Detail(DOC) · Summary(TXT) · PM Curve(JPG) 형식의 파일로 출력합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/WD-ANAL` | POST | `design` | execute | 지정한 벽체 ID · 층(Story) 조합에 대해 RC 벽체(Wall) 설계 계산을 수행합니다. 벽체는 요소가 아니라 `WALL_IDS` + `STORY` 조합으로 지정합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/WD-TABLE` | POST | `design` | execute | 수행된 RC 벽체 설계 결과를 표 형태로 반환합니다. 응답은 `data` 객체 안에 `COMPONENTS`(열 정의)와 `ROWS`(행 객체 배열)를 담는 구조입니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/WD-REPORT` | POST | `design` | execute | RC 벽체 설계 결과를 Graphic(JPG) · Detail(DOC) · Summary(TXT) · PM Curve(JPG) 형식의 파일로 출력합니다. 벽체는 `SELECTIONS`(벽체 I… | 0 |
| `/DESIGN/RC/KDS-41-20-2022/HCD-ANAL` | POST | `design` | execute | 지정한 헌치보(Haunched Beam) 요소에 대해 RC 설계 계산을 수행합니다. 결과는 이후 `HCD-TABLE` / `HCD-REPORT` 로 조회합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/HCD-TABLE` | POST | `design` | execute | 수행된 RC 헌치보 설계 결과를 표(HEAD/DATA) 형태로 반환합니다. 헌치 구간(T/N 구간)별 위치(`POS`)에 따라 휨·전단 검토 결과를 제공합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/HCD-REPORT` | POST | `design` | execute | RC 헌치보 설계 결과를 Graphic(JPG) 형식의 파일로 출력합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/BC-ANAL` | POST | `design` | execute | 기존 배근(rebar)이 배정된 RC 보 부재에 대해 **코드 검토(Checking)** 계산을 수행합니다. 전체(`ALL`)·요소별(`ELEMS`)·단면별(`SECTIONS`) 대상 선택을 … | 0 |
| `/DESIGN/RC/KDS-41-20-2022/BC-TABLE` | POST | `design` | execute | RC 보 검토 결과를 표(HEAD/DATA) 형식으로 반환합니다. 강도 검토(휨 정/부모멘트·전단)와 배근 상세(주근·스터럽 최소/최대 조건)가 함께 출력됩니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/BC-REPORT` | POST | `design` | execute | RC 보 검토 결과를 파일(그래픽 JPG / Detail DOC / Summary TXT)로 내보냅니다. 여러 요소를 지정하면 인덱스·요소번호가 접두된 파일명으로 각각 저장됩니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/CC-ANAL` | POST | `design` | execute | 배근이 배정된 RC 기둥 부재에 대해 **P-M 상관·전단 코드 검토**를 수행합니다. 전체/요소별/단면별 대상 선택을 지원합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/CC-TABLE` | POST | `design` | execute | RC 기둥 검토 결과를 표로 반환합니다. P-M 상관(축력/모멘트 강도비), 단·중앙부 전단, 주근·후프(Hoop) 배근 상세를 포함합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/CC-REPORT` | POST | `design` | execute | RC 기둥 검토 결과를 파일(Graphic/Detail/Summary)로 내보냅니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/BRC-ANAL` | POST | `design` | execute | 배근이 배정된 RC 가새(Brace) 부재에 대해 P-M 상관·전단 코드 검토를 수행합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/BRC-TABLE` | POST | `design` | execute | RC 가새 검토 결과를 표로 반환합니다. 구성은 기둥 검토와 유사하나 단부 구분이 없는 단일 위치 값(축력/모멘트 강도비, 전단, 후프 배근)을 제공합니다. 응답 최상위 키는 `TABLE_NA… | 0 |
| `/DESIGN/RC/KDS-41-20-2022/BRC-REPORT` | POST | `design` | execute | RC 가새 검토 결과를 파일(Graphic/Detail/Summary)로 내보냅니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/WC-ANAL` | POST | `design` | execute | RC 벽체(Shear Wall) 부재에 대해 코드 검토를 수행합니다. 벽체는 요소번호가 아니라 **벽 ID(WALL_IDS)와 층(STORY)** 조합(`SELECTIONS`)으로 대상을 지정… | 0 |
| `/DESIGN/RC/KDS-41-20-2022/WC-TABLE` | POST | `design` | execute | RC 벽체 검토 결과를 표로 반환합니다. 벽체는 `TABLE_TYPE`으로 출력 단위를 선택하며(`"WID+STORY"`=벽ID+층, `"WID"`=벽ID), 대상은 `SELECTIONS`(W… | 0 |
| `/DESIGN/RC/KDS-41-20-2022/WC-REPORT` | POST | `design` | execute | RC 벽체 검토 결과를 파일로 내보냅니다. 벽체는 `REPORT_TYPE`으로 출력 단위(`"WID+STORY"`/`"WID"`)를 정하고 각각 `CURRENT_MODE_WID_STORY`/`… | 0 |
| `/DESIGN/RC/KDS-41-20-2022/CDESIGN` | POST | `design` | execute | RC 콘크리트 설계(보·기둥·가새·벽체 통합) 결과를 화면에 표시하고 **이미지 파일로 캡처**합니다. 표시 하중조합, 강도비 성분(축력/전단/휨/조합), 배근 표시, 부재 종류 필터, 값/범… | 0 |
| `/DESIGN/RC/KDS-41-20-2022/TABLE` | POST | `design` | execute | RC 설계용 **기둥(Column) 부재 설계력**(3축 힘·모멘트)을 하중조합별로 추출합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/TABLE` | POST | `design` | execute | RC 설계용 **가새(Brace) 부재 설계력**(3축 힘·모멘트)을 추출합니다. 응답 컬럼 구조는 기둥과 동일합니다. | 0 |
| `/DESIGN/RC/KDS-41-20-2022/TABLE` | POST | `design` | execute | RC 설계용 **보(Beam) 부재 설계력**을 추출합니다. 휨설계 기준의 전단력·비틀림·정/부 모멘트를 제공합니다. | 0 |

### 27. Design Code — SRC AIK-SRC2K （27 个）

来源：`docs/manual/27_Design_SRC_AIKSRC2K.md`

| 端点 | 方法 | 资源 | 操作 | 说明 | 字段数 |
| --- | --- | --- | --- | --- | --- |
| `/DESIGN/SRC/AIK-SRC2K/DSRC` | PUT, DELETE | `design` | update, delete | SRC Design Code — SRC 설계 코드(AIK-SRC2K)를 설정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/DCO` | PUT, GET, DELETE | `design` | update, read, delete | Design Code Option — SRC 설계 코드 옵션(내진 적용 등 전역 설계 옵션)을 설정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/DCTL` | GET, PUT, DELETE | `design` | read, update, delete | Definition of Frame — 설계용 프레임(무/유측 이동, 자동 K 산정 등)을 정의합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/LLRF` | GET, PUT, DELETE | `design` | read, update, delete | Live Load Reduction Factor — 활하중 저감계수(부재 지지 층수/영향면적 기반)를 설정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/LCTB` | GET, DELETE | `design` | read, delete | Load Contribution for Nonlinear Load Case — 비선형 하중케이스에 대한 하중 기여(Load Contribution)를 설정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/LENG` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Unbraced Length (L, Lb) — 부재별 비지지 길이(Ly, Lz, Lb)를 설정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/KFAC` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Effective Length Factor (K) — 부재별 유효좌굴길이계수(Ky, Kz)를 설정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/LTSR` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Limiting Slenderness Ratio — 부재별 압축/인장 세장비 제한값을 설정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/CMFT` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Equivalent Moment Correction Factor(Cm) — 부재별 등가모멘트 보정계수(Cm)를 설정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/FMAG` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Moment Magnifier(B1/Delta_b, B2/Delta_s) — 부재별 모멘트 확대계수(B1/δb, B2/δs)를 설정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/MLLR` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Modify Live Load Reduction Factor — 부재별 활하중 저감계수를 수정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/SUEQ` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Scale up Factor for Earthquake — 지진하중에 대한 스케일업 계수를 설정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/MBTP` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Modify Member Type — 부재의 설계 타입(보/기둥 등)을 수정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/EQCT` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Seismic Load Combination Type — 지진 하중조합 타입을 설정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/BC-ANAL` | POST | `design` | create | SRC Beam Checking Perform — SRC 보 검토(설계 계산)를 수행합니다. POST 전용 액션입니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/BC-TABLE` | POST | `design` | create | SRC Beam Checking Table — SRC 보 검토 결과 테이블(HEAD/DATA)을 조회합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/BC-REPORT` | POST | `design` | create | SRC Beam Checking Report — SRC 보 검토 리포트를 생성/조회합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/CC-ANAL` | POST | `design` | create | SRC Column Checking Perform — SRC 기둥 검토(설계 계산)를 수행합니다. POST 전용 액션입니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/CC-TABLE` | POST | `design` | create | SRC Column Checking Table — SRC 기둥 검토 결과 테이블(HEAD/DATA)을 조회합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/CC-REPORT` | POST | `design` | create | SRC Column Checking Report — SRC 기둥 검토 리포트를 생성/조회합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/OCHECK` | POST | `design` | create | SRC Optimal Design — SRC 최적 설계(Optimal Design)를 수행합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/TABLE` | POST | `design` | create | SRC Beam Design Forces — SRC 보 설계력(Design Forces) 테이블을 조회합니다. URI는 TABLE 공용이며 TABLE_TYPE=SRCBEAMDESIGNFORCE… | 0 |
| `/DESIGN/SRC/AIK-SRC2K/TABLE` | POST | `design` | create | SRC Column Design Forces — SRC 기둥 설계력(Design Forces) 테이블을 조회합니다. URI는 TABLE 공용이며 TABLE_TYPE=SRCCOLUMNDESIGN… | 0 |
| `/DESIGN/SRC/AIK-SRC2K/MATD` | GET, PUT, DELETE | `design` | read, update, delete | Modify SRC Material — SRC 재료(콘크리트/강재 등급)를 수정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/MCRD` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Modify SRC Column Section Data — SRC 기둥 단면 데이터(매입형강 배치 등)를 수정합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/MEMB` | GET, PUT, DELETE | `design` | read, update, delete | Member Assignment — 설계 부재(요소→부재) 배정을 관리합니다. | 0 |
| `/DESIGN/SRC/AIK-SRC2K/MRBD` | POST, GET, PUT, DELETE | `design` | create, read, update, delete | Modify SRC Beam Section Data — SRC 보 단면 데이터(매입형강/철근 배치 등)를 수정합니다. | 0 |
