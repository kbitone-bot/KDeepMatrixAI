import streamlit as st
from datetime import datetime, timedelta

def render_ram_inputs():
    st.sidebar.subheader("분석 조건 입력")
    mode = st.sidebar.radio("분석 모드", ["수리", "조절"], index=0)
    no_pn = st.sidebar.text_input("부품번호 (pn)", value="", help="비워두면 전체 부품번호")
    no_pclrt_idno = st.sidebar.text_input("고유식별번호 (pclrt_idno)", value="", help="비워두면 전체 식별번호")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("시작일", value=datetime(2021, 1, 1))
    with col2:
        end_date = st.date_input("종료일", value=datetime(2022, 2, 20))
    return {
        "mode": mode,
        "no_pn": no_pn if no_pn else None,
        "no_pclrt_idno": no_pclrt_idno if no_pclrt_idno else None,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
    }

def render_placeholder_inputs(model_id: str):
    st.sidebar.info(f"{model_id} 분석 조건 입력 UI는 준비 중입니다.")
    return {}
