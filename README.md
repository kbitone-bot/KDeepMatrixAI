# KDeepMatrixAI

국방 빅데이터 분석·가시화 통합 플랫폼

## 소개
기존 Python 분석모델 5개를 수정하지 않고, 신규 코드만 추가하여 웹 기반 통합 분석 환경을 구축합니다.

## 아키텍처
- **Backend**: FastAPI + Pydantic
- **Frontend**: Streamlit
- **시각화**: Plotly
- **분석 엔진**: lifelines, scipy, pandas

## 설치 및 실행
```bash
pip install -r requirements.txt
streamlit run app/app.py
```

## 지원 모델
1. **af_ba_req_001** 장비운용가용도분석 (RAM) - MTBF/MTTR/가용도
2. **af_ba_req_002** 장비수명예측 (구조 등록)
3. **af_ba_req_004** 시험소작업량예측 (구조 등록)
4. **af_ba_req_005** 기술검토자동처리 (구조 등록)
5. **af_ba_req_007** IMQC인원수급분석 (구조 등록)

## 결과 저장
```
outputs/{analysis_id}/
├─ summary.csv
├─ visualization.csv
├─ timeline.csv
├─ charts/
│   ├─ ram_curves_{pn}.html
│   └─ availability_{pn}.html
└─ report.html
```

## 주의사항
- 기존 `af_ba_req_*/` 폴 내 파일은 절대 수정하지 마세요.
