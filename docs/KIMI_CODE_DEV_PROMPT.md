# KIMI_CODE_DEV_PROMPT

## 프로젝트 개요
KDeepMatrixAI는 국방 빅데이터 분석모델 5개를 통합하여 웹 기반으로 실행하고 시각화하는 플랫폼이다.

## 개발 원칙
- 기존 af_ba_req_* 내 코드/데이터 절대 수정 금지
- 신규 코드만 작성 (app/, backend/, frontend/, outputs/, docs/)
- 확장 가능한 구조 유지

## 실행 방법
```bash
pip install -r requirements.txt
streamlit run app/app.py
```

## 모델 목록
| ID | 이름 | 상태 |
|---|---|---|
| af_ba_req_001 | 장비운용가용도분석 (RAM) | 구현 완료 |
| af_ba_req_002 | 장비수명예측 | 구조 등록 |
| af_ba_req_004 | 시험소작업량예측 | 구조 등록 |
| af_ba_req_005 | 기술검토자동처리 | 구조 등록 |
| af_ba_req_007 | IMQC인원수급분석 | 구조 등록 |
