import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
st.set_page_config(page_title="KDeepMatrixAI", layout="wide")

from backend.model_registry import scan_models
from backend.services.ram_service import RAMAnalysisService
from backend.services.life_service import LifeAnalysisService
from backend.services.sim_service import SimAnalysisService
from backend.services.recommend_service import RecommendAnalysisService
from backend.services.imqc_service import IMQCAnalysisService

from frontend.components.model_selector import render_model_selector
from frontend.components.input_forms import render_ram_inputs, render_recommend_inputs, render_sim_inputs, render_life_inputs, render_imqc_inputs, render_placeholder_inputs
from frontend.components.metric_cards import render_metric_cards
from frontend.components.charts import render_charts_from_result, render_viz_dataframe
from frontend.components.data_table import render_data_table

SERVICE_MAP = {
    "af_ba_req_001": RAMAnalysisService,
    "af_ba_req_002": LifeAnalysisService,
    "af_ba_req_004": SimAnalysisService,
    "af_ba_req_005": RecommendAnalysisService,
    "af_ba_req_007": IMQCAnalysisService,
}

def main():
    st.title("🔬 KDeepMatrixAI 빅데이터 분석·가시화 플랫폼")
    st.markdown("국방 빅데이터 분석모델 통합 실행 및 시각화 시스템")
    
    with st.sidebar:
        st.header("모델 선택")
        models = scan_models()
        model_options = {m.model_id: f"{m.name}" for m in models}
        selected_model = st.selectbox(
            "분석 모델",
            list(model_options.keys()),
            format_func=lambda k: f"{k} - {model_options[k]}",
        )
        
        st.divider()
        st.caption(f"모델 상태: {next((m.status for m in models if m.model_id == selected_model), 'unknown')}")
    
    # 입력 폼 렌더링
    if selected_model == "af_ba_req_001":
        params = render_ram_inputs()
    elif selected_model == "af_ba_req_002":
        params = render_life_inputs()
    elif selected_model == "af_ba_req_005":
        params = render_recommend_inputs()
    elif selected_model == "af_ba_req_004":
        params = render_sim_inputs()
    elif selected_model == "af_ba_req_007":
        params = render_imqc_inputs()
    else:
        params = render_placeholder_inputs(selected_model)
    
    st.divider()
    
    col_run, col_status = st.columns([1, 4])
    with col_run:
        run_btn = st.button("🚀 분석 실행", type="primary", use_container_width=True)
    
    if run_btn:
        service_cls = SERVICE_MAP.get(selected_model)
        if not service_cls:
            st.error("선택한 모델의 서비스를 찾을 수 없습니다.")
            return
        
        service = service_cls()
        with st.spinner("분석을 실행 중입니다..."):
            result = service.analyze(params)
        
        if result.status == "success":
            st.success(f"✅ 분석 완료: {result.message}")
            
            # 지표 카드
            if result.metrics:
                if selected_model == "af_ba_req_001":
                    st.subheader("📊 RAM 핵심 지표")
                elif selected_model == "af_ba_req_002":
                    st.subheader("📊 수명 예측 핵심 지표")
                elif selected_model == "af_ba_req_007":
                    st.subheader("📊 IMQC 인원 수급 핵심 지표")
                else:
                    st.subheader("📊 핵심 지표")
                render_metric_cards(result.metrics)
            
            # 차트
            st.subheader("📈 시각화")
            render_charts_from_result(result.model_dump())
            
            # 시각화 데이터프레임 차트
            if result.viz_csv:
                render_viz_dataframe(result.viz_csv)
            
            # 데이터 테이블 + 다운로드
            st.subheader("📋 결과 데이터")
            render_data_table(result.summary_csv, result.viz_csv, result.timeline_csv)
            
            # 보고서 다운로드
            if result.report_html:
                report_path = Path(result.report_html)
                if report_path.exists():
                    with open(report_path, "rb") as f:
                        st.download_button(
                            label="📄 HTML 보고서 다운로드",
                            data=f,
                            file_name="report.html",
                            mime="text/html",
                        )
            
            st.info(f"결과 저장 경로: `outputs/{result.analysis_id}/`")
        elif result.status == "unavailable":
            st.warning(f"⏳ {result.message}")
        else:
            st.error(f"❌ 분석 실패: {result.message}")

if __name__ == "__main__":
    main()
