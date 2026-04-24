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

def render_recommend_inputs():
    st.sidebar.subheader("분석 조건 입력")
    part_no = st.sidebar.text_input("부품번호", value="75(0-6)KG-B")
    topn = st.sidebar.slider("추천 개수", min_value=1, max_value=20, value=5)
    return {
        "part_no": part_no,
        "topn": topn,
    }

def render_sim_inputs():
    st.sidebar.subheader("분석 조건 입력")
    stl_num = st.sidebar.selectbox("시험소", ["시험소008", "시험소010", "시험소012"])
    difficulty = st.sidebar.selectbox("난이도", ["A", "B", "C", "D", "missing"])
    tech_grade = st.sidebar.selectbox("기술등급", ["2C", "1C", "3C", "4C", "missing"])
    efficiency = st.sidebar.slider("효율(%)", 50, 100, 80)
    maint_cycle = st.sidebar.slider("정비주기", 1, 24, 12)
    cons_mh = st.sidebar.slider("소모인시", 20, 300, 100)
    return {
        "stl_num": stl_num,
        "difficulty": difficulty,
        "tech_grade": tech_grade,
        "efficiency": efficiency,
        "maint_cycle": maint_cycle,
        "cons_mh": cons_mh,
    }

def render_life_inputs():
    st.sidebar.subheader("분석 조건 입력")
    pn = st.sidebar.text_input("부품번호 (pn)", value="", help="비워두면 전체 부품번호 분석")
    return {
        "pn": pn if pn else None,
    }

def render_imqc_inputs():
    st.sidebar.subheader("분석 조건 입력")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        year = st.selectbox("년", [2021, 2022, 2023, 2024, 2025], index=4)
    with col2:
        month = st.selectbox("월", list(range(1, 13)), index=0)
    return {
        "year": year,
        "month": month,
    }

def render_placeholder_inputs(model_id: str):
    st.sidebar.info(f"{model_id} 분석 조건 입력 UI는 준비 중입니다.")
    return {}
