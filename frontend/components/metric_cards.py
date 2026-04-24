import streamlit as st

def render_metric_cards(metrics: dict):
    if not metrics:
        return
    summary = metrics.get("summary", [])
    if not summary:
        return
    
    # 첫 번째 summary 기준으로 카드 생성
    first = summary[0]
    cols = st.columns(5)
    labels = {
        "mtbf": "MTBF (일)",
        "mttr": "MTTR (일)",
        "failure_rate": "고장률",
        "repair_rate": "수리율",
        "availability": "가용도",
    }
    keys = ["mtbf", "mttr", "failure_rate", "repair_rate", "availability"]
    for col, key in zip(cols, keys):
        val = first.get(key, "N/A")
        col.metric(label=labels[key], value=val)
