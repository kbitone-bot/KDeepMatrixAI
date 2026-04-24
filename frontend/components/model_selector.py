import streamlit as st
from backend.model_registry import scan_models

def render_model_selector():
    models = scan_models()
    options = {m.model_id: f"{m.model_id} - {m.name}" for m in models}
    selected = st.sidebar.selectbox("분석 모델 선택", list(options.keys()), format_func=lambda k: options[k])
    return selected, models
