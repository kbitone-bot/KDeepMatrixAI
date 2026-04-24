import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
st.set_page_config(page_title="KDeepMatrixAI 데모", layout="wide")

from backend.model_registry import scan_models
from backend.services.ram_service import RAMAnalysisService
from backend.services.life_service import LifeAnalysisService
from backend.services.sim_service import SimAnalysisService
from backend.services.recommend_service import RecommendAnalysisService
from backend.services.imqc_service import IMQCAnalysisService

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

# 모델 메타데이터 (데모 설명용)
MODEL_META = {
    "af_ba_req_001": {
        "category": "📊 통계 분석 도구",
        "badge": "🟡 분석",
        "desc": "32만 행 가용도 데이터를 기반으로 MTBF/MTTR/가용도를 lifelines 분포 적합으로 산출",
        "data_source": "af_ba_req_001/data/가용도분석자료.xlsb (합성 데이터)",
        "core_tech": "lifelines (Weibull/LogNormal/Exponential)",
        "is_ai": False,
    },
    "af_ba_req_002": {
        "category": "📊 통계 분석 도구",
        "badge": "🟡 분석",
        "desc": "정밀측정 폐품 데이터를 기반으로 부품별 수명 분포를 적합하여 B10/B50 수명 예측",
        "data_source": "af_ba_req_002/data/정밀측정폐품현황.xlsb (합성 데이터)",
        "core_tech": "scipy.stats + Fitter (norm/expon/weibull_min)",
        "is_ai": False,
    },
    "af_ba_req_004": {
        "category": "🤖 실시간 AI Serving",
        "badge": "🔴 핵심",
        "desc": "시험소별 작업량을 실시간 예측. GradientBoostingRegressor 모델이 학습된 .joblib Binary를 로드하여 Inference",
        "data_source": "outputs/models_004/ — 합성 데이터 8,000샘플/시험소로 학습",
        "core_tech": "GradientBoostingRegressor + MinMaxScaler + Calibration",
        "is_ai": True,
    },
    "af_ba_req_005": {
        "category": "🤖 실시간 AI Serving",
        "badge": "🔴 핵심",
        "desc": "입력 부품과 유사한 부품을 KMeans 클러스터링 + TF-IDF 코사인 유사도로 실시간 추천",
        "data_source": "outputs/models_005/cluster_model_kmeans.joblib — 34만 행으로 학습",
        "core_tech": "KMeans + TF-IDF + NearestNeighbors (cosine)",
        "is_ai": True,
    },
    "af_ba_req_007": {
        "category": "📊 통계 분석 도구",
        "badge": "🟡 분석",
        "desc": "IMQC 등급 현황과 계획 수립 데이터를 병합하여 분야/등급별 현재 vs 필요 인원 산출",
        "data_source": "af_ba_req_007/datasets/ — 3개 Excel 파일 (합성 데이터)",
        "core_tech": "집계/병합 (pandas groupby + merge)",
        "is_ai": False,
    },
}

def render_demo_banner():
    """상단 데모 배너"""
    st.markdown(
        """
        <div style="background: linear-gradient(90deg, #ff6b6b 0%, #feca57 100%); padding: 12px 20px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="color: white; margin: 0; font-size: 18px;">🎯 데모 버전 (PoC / Proof of Concept)</h3>
            <p style="color: white; margin: 4px 0 0 0; font-size: 13px; opacity: 0.95;">
                이 시스템은 <b>입찰 제안용 데모</b>입니다. 모든 데이터는 <b>합성/시뮬레이션 데이터</b>이며, 
                실제 운용 환경과는 다를 수 있습니다. 고객사 데이터 연동 시 실제 분석이 가능합니다.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_model_info(selected_model: str):
    """선택한 모델의 상세 정보 표시"""
    meta = MODEL_META.get(selected_model, {})
    if not meta:
        return
    
    # 배지 색상
    badge_color = "#e74c3c" if meta["is_ai"] else "#f39c12"
    
    st.markdown(f"""
    <div style="background: #f8f9fa; padding: 16px 20px; border-radius: 8px; border-left: 4px solid {badge_color}; margin-bottom: 16px;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
            <span style="background: {badge_color}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;">{meta['badge']}</span>
            <span style="color: #666; font-size: 13px;">{meta['category']}</span>
        </div>
        <p style="margin: 0; color: #333; font-size: 14px;"><b>기능:</b> {meta['desc']}</p>
        <p style="margin: 6px 0 0 0; color: #666; font-size: 12px;">🔧 <b>핵심 기술:</b> {meta['core_tech']}</p>
        <p style="margin: 4px 0 0 0; color: #888; font-size: 12px;">📁 <b>데이터 출처:</b> {meta['data_source']}</p>
    </div>
    """, unsafe_allow_html=True)

def main():
    render_demo_banner()
    
    st.title("🔬 KDeepMatrixAI 빅데이터 분석·가시화 플랫폼")
    st.markdown("국방 빅데이터 AI 모델 통합 실행 및 실시간 Serving 시스템")
    
    with st.sidebar:
        st.header("모델 선택")
        
        # AI Serving 모델 구분 표시
        st.markdown("""
        <div style="font-size: 11px; color: #666; margin-bottom: 8px;">
            <span style="color: #e74c3c;">🔴 핵심</span> = AI Serving (실시간 예측)<br>
            <span style="color: #f39c12;">🟡 분석</span> = 통계 분석 도구
        </div>
        """, unsafe_allow_html=True)
        
        models = scan_models()
        
        # AI 모델을 상단에 표시
        ai_models = [m for m in models if MODEL_META.get(m.model_id, {}).get("is_ai", False)]
        analysis_models = [m for m in models if not MODEL_META.get(m.model_id, {}).get("is_ai", False)]
        
        model_options = {}
        for m in ai_models:
            model_options[m.model_id] = f"🔴 {m.model_id} - {m.name}"
        for m in analysis_models:
            model_options[m.model_id] = f"🟡 {m.model_id} - {m.name}"
        
        selected_model = st.selectbox(
            "분석 모델",
            list(model_options.keys()),
            format_func=lambda k: model_options[k],
        )
        
        st.divider()
        
        # 모델 상세 정보
        meta = MODEL_META.get(selected_model, {})
        if meta:
            st.caption(f"모델 상태: {next((m.status for m in models if m.model_id == selected_model), 'unknown')}")
            if meta.get("is_ai"):
                st.success("🤖 이 모델은 학습된 AI Binary를 실시간 Serving합니다")
            else:
                st.info("📊 이 모델은 통계 분석/집계 도구입니다")
    
    # 모델 정보 표시
    render_model_info(selected_model)
    
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
            
            # AI Serving 모델인 경우 강조
            if MODEL_META.get(selected_model, {}).get("is_ai"):
                st.balloons()
                st.markdown("""
                <div style="background: #d4edda; padding: 10px 16px; border-radius: 6px; margin-bottom: 12px;">
                    <span style="color: #155724; font-size: 13px;">🚀 이 결과는 <b>학습된 AI 모델 Binary</b>를 로드하여 실시간으로 산출된 예측값입니다</span>
                </div>
                """, unsafe_allow_html=True)
            
            # 지표 카드
            if result.metrics:
                if selected_model == "af_ba_req_001":
                    st.subheader("📊 RAM 핵심 지표")
                elif selected_model == "af_ba_req_002":
                    st.subheader("📊 수명 예측 핵심 지표")
                elif selected_model == "af_ba_req_004":
                    st.subheader("🤖 AI 예측 결과")
                elif selected_model == "af_ba_req_005":
                    st.subheader("🤖 AI 추천 결과")
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
                render_viz_dataframe(result.viz_csv, model_id=selected_model)
            
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
            
            # 데모 안내
            st.markdown("""
            <div style="background: #fff3cd; padding: 10px 16px; border-radius: 6px; margin-top: 16px;">
                <span style="color: #856404; font-size: 12px;">💡 <b>데모 안내:</b> 이 결과는 합성/시뮬레이션 데이터를 기반으로 생성되었습니다. 실제 고객사 데이터 연동 시 더 정확한 결과를 얻을 수 있습니다.</span>
            </div>
            """, unsafe_allow_html=True)
            
        elif result.status == "unavailable":
            st.warning(f"⏳ {result.message}")
        else:
            st.error(f"❌ 분석 실패: {result.message}")

if __name__ == "__main__":
    main()
