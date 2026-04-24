# KDeepMatrixAI 시스템 아키텍처 상세 설계서

## 1. 설계 원칙

### 1.1 기존 코드 보존 원칙
- `af_ba_req_*/` 내 모든 파일은 **Read-Only**로 취급
- 기존 `.py`, `.xlsb`, `.xlsx`, `.png` 등 절대 수정 금지
- 신규 코드만으로 기능 구현

### 1.2 확장 가능한 구조
- Adapter 패턴으로 새로운 분석모델 추가 시 기존 코드 변경 최소화
- Service 레이어에서 분석 로직 캡슐화
- Schema 기반 API 계약으로 프론트-백엔드 독립 개발

---

## 2. 핵심 클래스 설계

### 2.1 모델 레지스트리

```python
class ModelRegistry:
    """프로젝트 루트를 스캔하여 af_ba_req_* 디렉터리를 자동 인식"""
    
    def scan_models() -> List[ModelInfo]
    def get_model(model_id: str) -> ModelInfo
```

**동작 방식:**
1. `PROJECT_ROOT` 하위에서 `af_ba_req_*` 패턴 매칭
2. 각 디렉터리 내 Python 파일, data/ 파일, result/ 파일 메타데이터 추출
3. `MODEL_NAMES` 매핑으로 사용자 친화적 이름 부여
4. 파일 존재 여부로 status 결정 (ready / partial / unavailable)

### 2.2 분석 서비스 계층

```python
class BaseAnalysisService(ABC):
    model_id: str
    model_name: str
    def analyze(params: Dict[str, Any]) -> AnalysisResult

class RAMAnalysisService(BaseAnalysisService):
    """af_ba_req_001 장비운용가용도분석"""
    
    def _preprocess(...) -> pd.DataFrame
    def _create_timeline(...) -> pd.DataFrame
    def _calculate_durations(...) -> Tuple[...]
    def _find_best_distribution(...) -> Optional[Fitter]
    def _calculate_ram_metrics(...) -> Dict[str, float]
    def _create_viz_data(...) -> pd.DataFrame
    def _generate_report(...) -> Path
```

### 2.3 분석 결과 스키마

```python
class AnalysisResult(BaseModel):
    analysis_id: str          # UUID v4
    model_id: str
    status: str               # success | partial | failed | unavailable
    message: str
    metrics: Optional[Dict]   # 모델별 지표 딕셔너리
    summary_csv: Optional[str]
    viz_csv: Optional[str]
    timeline_csv: Optional[str]
    charts: List[str]         # 생성된 차트 파일 경로 목록
    report_html: Optional[str]
    created_at: datetime
```

---

## 3. 데이터 흐름 상세

### 3.1 af_ba_req_001 RAM 분석 흐름

```
[HTTP Request]
  POST /api/v1/analyze/ram
  Body: { mode, no_pn, no_pclrt_idno, start_date, end_date }
        │
        ▼
[FastAPI Router]
  analysis.py::analyze_ram()
        │
        ▼
[RAMAnalysisService.analyze()]
        │
        ├─► [load_ram_data()]
        │     ├─ pyxlsb 엔진으로 xlsb 로드
        │     ├─ Excel serial date → datetime 변환
        │     └─ 327,699행 x 5컬럼 DataFrame 반환
        │
        ├─► [_preprocess()]
        │     ├─ CODE_MAP 적용: {'C':'J', 'H':'J', 'S':'J', 'L':'K'}
        │     ├─ VALID_CODES 필터: ['F','G','J','K']
        │     ├─ 날짜 범위 필터링
        │     ├─ pn / pclrt_idno 필터링
        │     └─ event_status 할당 (mode에 따라 가동/비가동)
        │
        ├─► [_create_timeline()]  (pn → pclrt_idno 별 반복)
        │     ├─ Rule 1: start_date ~ 첫 의뢰일 → 가동
        │     ├─ Rule 2: 의뢰일~출고일 → event_status
        │     └─ Rule 3: 출고일~다음 의뢰일 → 가동
        │
        ├─► [_create_daily_log()]  (단일 pclrt_idno 선택 시)
        │     └─ 일별 0/1 상태 로그 생성
        │
        ├─► [_calculate_durations()]
        │     ├─ 가동 구간 → TBF durations
        │     ├─ 비가동 구간 → TTR durations
        │     └─ 마지막 구간 end_date 도달 시 right-censored (observed=0)
        │
        ├─► [_find_best_distribution()]
        │     ├─ WeibullFitter.fit(tbf_durations, event_observed=tbf_events)
        │     ├─ LogNormalFitter.fit(...)
        │     ├─ ExponentialFitter.fit(...)
        │     └─ AIC_ 최소값인 모델 선택
        │
        ├─► [_calculate_ram_metrics()]
        │     ├─ MTBF = get_model_mean(tbf_model)
        │     ├─ MTTR = get_model_mean(ttr_model)
        │     ├─ failure_rate = 1/MTBF
        │     ├─ repair_rate = 1/MTTR
        │     └─ availability = MTBF/(MTBF+MTTR)
        │
        ├─► [_create_viz_data()]
        │     ├─ reliability = tbf_model.survival_function_at_times(t)
        │     ├─ maintainability = 1 - ttr_model.survival_function_at_times(t)
        │     ├─ hazard_rate = tbf_model.hazard_at_times(t)
        │     └─ availability = 상수
        │
        ├─► [Plotly 차트 생성]
        │     ├─ ram_curves_{pn}.html
        │     └─ availability_{pn}.html
        │
        └─► [_generate_report()]
              └─ report.html
```

### 3.2 분포 평균 계산 공식

| 분포 | 평균 공식 | lifelines 파라미터 |
|---|---|---|
| LogNormal | exp(μ + σ²/2) | `mu_`, `sigma_` |
| Exponential | λ (lambda) | `lambda_` |
| Weibull | λ · Γ(1 + 1/ρ) | `lambda_`, `rho_` |

---

## 4. 확장 가이드

### 4.1 새로운 분석모델 추가 방법

예: `af_ba_req_003`이 추가된 경우

**Step 1: 서비스 구현**
```python
# backend/services/new_service.py
class NewAnalysisService(BaseAnalysisService):
    model_id = "af_ba_req_003"
    model_name = "새로울 분석"
    
    def analyze(self, params: Dict[str, Any]) -> AnalysisResult:
        # 분석 로직 구현
        return AnalysisResult(...)
```

**Step 2: API 라우터 등록**
```python
# backend/api/v1/analysis.py
SERVICE_MAP = {
    "af_ba_req_001": RAMAnalysisService(),
    ...
    "af_ba_req_003": NewAnalysisService(),  # 추가
}
```

**Step 3: 프론트엔드 입력 폼 추가**
```python
# frontend/components/input_forms.py
def render_new_inputs():
    st.sidebar.text_input("새로운 파라미터")
    return {...}
```

**Step 4: app.py에서 모델 매핑**
```python
# app/app.py
SERVICE_MAP = {
    "af_ba_req_001": RAMAnalysisService,
    ...
    "af_ba_req_003": NewAnalysisService,  # 추가
}
```

**Step 5: config.py에 이름 등록**
```python
# backend/core/config.py
MODEL_NAMES = {
    ...
    "af_ba_req_003": "새로울 분석",
}
```

### 4.2 새로운 시각화 추가

`backend/utils/viz_utils.py`에 Plotly 차트 함수를 추가하면,
`frontend/components/charts.py`에서 해당 함수를 호출하여 Streamlit에 렌더링합니다.

---

## 5. 보안 및 예외 처리

### 5.1 입력 검증
- Pydantic 스키마로 요청 데이터 타입/필수값 검증
- 날짜 문자열은 `pd.to_datetime(errors='coerce')`로 안전 파싱
- 파일 경로는 `Path.resolve()`로 정규화

### 5.2 취약점 방어
- **Path Traversal**: `analysis_id`는 UUID이므로 외부 입력으로 디렉터리 이동 불가
- **Command Injection**: 사용자 입력이 쉘 명령어로 전달되지 않음
- **XSS**: Streamlit가 내부적으로 HTML 이스케이프 처리
- **CORS**: 개발 환경에서는 `allow_origins=["*"]`, 운영 환경에서는 특정 도메인 제한 필요

### 5.3 에러 핸들링 계층
```
try:
    result = service.analyze(params)
except (DataLoadError, ColumnNotFoundError, EmptyDataError) as e:
    # 400 Bad Request
    return AnalysisResult(status="failed", message=str(e))
except DistributionFitError as e:
    # 분포 실패 시 fallback + partial 상태
    return AnalysisResult(status="partial", message=str(e))
except Exception as e:
    # 500 Internal Server Error
    return AnalysisResult(status="failed", message=f"Unexpected: {e}")
```

---

## 6. 성능 고려사항

| 항목 | 현재 상태 | 개선 방안 |
|---|---|---|
| 데이터 로딩 | 32만행 xlsb 전체 메모리 로드 | 필요 시 Chunked read 고려 |
| 분포 적합 | pn별 순차 처리 | 멀티프로세싱(parallel) 적용 가능 |
| 차트 생성 | Plotly HTML 파일 쓰기 | 메모리 내 JSON + Streamlit 직접 렌더링 |
| 결과 저장 | 로컬 파일 시스템 | S3/MinIO 연동 가능 |

---

## 7. 환경 변수 (선택)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `PROJECT_ROOT` | 자동 감지 | 프로젝트 루트 경로 |
| `OUTPUT_DIR` | `PROJECT_ROOT/outputs` | 분석 결과 저장 경로 |
| `DEFAULT_START_DATE` | `2021-01-01` | RAM 분석 기본 시작일 |
| `DEFAULT_END_DATE` | 현재 날짜 | RAM 분석 기본 종료일 |
