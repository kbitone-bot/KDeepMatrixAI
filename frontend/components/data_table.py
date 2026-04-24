import streamlit as st
import pandas as pd
from pathlib import Path

def render_data_table(summary_csv: str, viz_csv: str = None, timeline_csv: str = None):
    tabs = []
    paths = {"요약": summary_csv, "시각화": viz_csv, "타임라인": timeline_csv}
    available = {k: v for k, v in paths.items() if v and Path(v).exists()}
    
    if not available:
        st.info("표시할 데이터 테이블이 없습니다.")
        return
    
    tabs = st.tabs(list(available.keys()))
    for tab, (name, path) in zip(tabs, available.items()):
        with tab:
            df = pd.read_csv(path)
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label=f"{name} CSV 다운로드",
                data=csv,
                file_name=f"{name}.csv",
                mime="text/csv",
            )
