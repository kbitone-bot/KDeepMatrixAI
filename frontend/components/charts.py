import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from pathlib import Path

def render_charts_from_result(result):
    charts = result.get("charts", [])
    if not charts:
        st.info("생성된 차트가 없습니다.")
        return
    
    for chart_path in charts:
        path = Path(chart_path)
        if not path.exists():
            continue
        if path.suffix == ".html":
            with open(path, "r", encoding="utf-8") as f:
                html = f.read()
            st.components.v1.html(html, height=450, scrolling=True)
        else:
            st.image(str(path))

def render_viz_dataframe(viz_csv: str):
    if not viz_csv:
        return
    path = Path(viz_csv)
    if not path.exists():
        return
    df = pd.read_csv(path)
    if df.empty:
        return
    
    st.subheader("시각화 데이터 미리보기")
    st.dataframe(df.head(20), use_container_width=True)
    
    # Plotly 인터랙티브 차트 렌더링
    pn_list = df["pn"].unique().tolist()[:3]  # 최대 3개 부품
    for pn in pn_list:
        d = df[df["pn"] == pn]
        fig = make_subplots(rows=1, cols=3, subplot_titles=("신뢰도", "보전도", "고장률"))
        fig.add_trace(go.Scatter(x=d["time"], y=d["reliability"], mode="lines", name="신뢰도", line=dict(color="green")), row=1, col=1)
        fig.add_trace(go.Scatter(x=d["time"], y=d["maintainability"], mode="lines", name="보전도", line=dict(color="blue")), row=1, col=2)
        fig.add_trace(go.Scatter(x=d["time"], y=d["hazard_rate"], mode="lines", name="고장률", line=dict(color="red")), row=1, col=3)
        fig.update_layout(height=400, template="plotly_white", title_text=f"RAM 곡선 - {pn}", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
