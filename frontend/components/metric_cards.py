import streamlit as st

def render_metric_cards(metrics: dict):
    if not metrics:
        return
    
    # 001 RAM metrics
    summary = metrics.get("summary", [])
    if summary:
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
        return
    
    # 002 Lifetime metrics
    lifetime = metrics.get("lifetime")
    if lifetime:
        cols = st.columns(3)
        cols[0].metric(label="점 추정치 (년)", value=f"{lifetime.get('expected_lifetime', 'N/A'):.2f}")
        cols[1].metric(label="B10 수명 (년)", value=f"{lifetime.get('lifetime_10p', 'N/A'):.2f}")
        cols[2].metric(label="B50 수명 (년)", value=f"{lifetime.get('lifetime_50p', 'N/A'):.2f}")
        return
    
    # 007 IMQC metrics
    current_total = metrics.get("current_total")
    required_total = metrics.get("required_total")
    if current_total and required_total:
        cols = st.columns(3)
        total_cur = sum(sum(r.get(f"GRAD_{g}_COUNT", 0) for g in [1,2,3,4]) for r in current_total)
        total_req = sum(sum(r.get(f"GRAD_{g}_REQ_TOTAL", 0) for g in [1,2,3,4]) for r in required_total)
        cols[0].metric(label="총 현재 인원", value=f"{total_cur}")
        cols[1].metric(label="총 필요 인원", value=f"{total_req}")
        cols[2].metric(label="인력 차이", value=f"{total_cur - total_req}")
        return
