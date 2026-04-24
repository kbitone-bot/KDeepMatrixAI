import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from backend.core.exceptions import VisualizationError


def create_lifetime_pdf_plot(viz_df: pd.DataFrame, best_dist: str, expected_lifetime: float) -> go.Figure:
    """Create PDF plot with expected lifetime vertical line."""
    try:
        fig = go.Figure()
        if viz_df.empty:
            fig.update_layout(title="수명 분포 (데이터 없음)")
            return fig
        fig.add_trace(go.Scatter(x=viz_df['time'], y=viz_df['pdf'], mode='lines', name='PDF', line=dict(color='blue')))
        fig.add_vline(x=expected_lifetime, line=dict(color='red', dash='dash'), annotation_text=f'점 추정치: {expected_lifetime:.2f}년')
        fig.update_layout(title=f'{best_dist} 분포 - 점 추정치', xaxis_title='사용 연도', yaxis_title='확률 밀도', template='plotly_white', height=400)
        return fig
    except Exception as e:
        raise VisualizationError(f"Lifetime PDF plot failed: {e}")


def create_lifetime_cdf_plot(viz_df: pd.DataFrame, best_dist: str, lifetime_10p: float, lifetime_50p: float) -> go.Figure:
    """Create CDF plot with B10/B50 vertical lines."""
    try:
        fig = go.Figure()
        if viz_df.empty:
            fig.update_layout(title="수명 CDF (데이터 없음)")
            return fig
        fig.add_trace(go.Scatter(x=viz_df['time'], y=viz_df['cdf'], mode='lines', name='CDF', line=dict(color='blue')))
        fig.add_vline(x=lifetime_10p, line=dict(color='orange', dash='dash'), annotation_text=f'B10: {lifetime_10p:.2f}년')
        fig.add_vline(x=lifetime_50p, line=dict(color='green', dash='dash'), annotation_text=f'B50: {lifetime_50p:.2f}년')
        fig.update_layout(title=f'{best_dist} 분포 - B10/B50 수명', xaxis_title='사용 연도', yaxis_title='누적 고장 확률', template='plotly_white', height=400)
        return fig
    except Exception as e:
        raise VisualizationError(f"Lifetime CDF plot failed: {e}")


def create_imqc_charts(curr_df, req_df, merged_df, charts_dir: Path) -> List[str]:
    """Create IMQC personnel comparison charts."""
    try:
        chart_files = []
        if curr_df.empty or req_df.empty:
            return chart_files
        
        # 현재 인원 vs 필요 인원 (분야별 합계 막대그래프)
        fig = make_subplots(rows=1, cols=2, subplot_titles=("도량 분야", "전기/전자 분야"), horizontal_spacing=0.1)
        
        for idx, field in enumerate(["도량", "전기/전자"], 1):
            curr_field = curr_df[curr_df["FIELD"] == field]
            if not curr_field.empty:
                for g in [1, 2, 3, 4]:
                    fig.add_trace(go.Bar(x=curr_field["AFF"], y=curr_field[f"GRAD_{g}_COUNT"], name=f"등급{g} 현재", marker_color=f'rgba(0, 100, {g*50}, 0.7)'), row=1, col=idx)
        
        fig.update_layout(height=400, template="plotly_white", showlegend=False, title_text="IMQC 현재 인원 현황")
        curr_path = charts_dir / "imqc_current.html"
        fig.write_html(str(curr_path))
        chart_files.append(str(curr_path))
        
        # 현재 vs 필요 비교 (merged)
        if not merged_df.empty:
            fig2 = go.Figure()
            for _, row in merged_df.iterrows():
                field = row["FIELD"]
                fig2.add_trace(go.Bar(x=[f"{field}-1등급", f"{field}-2등급", f"{field}-3등급", f"{field}-4등급"],
                                       y=[row["GRAD_1_CUR_TOTAL"], row["GRAD_2_CUR_TOTAL"], row["GRAD_3_CUR_TOTAL"], row["GRAD_4_CUR_TOTAL"]],
                                       name=f"{field} 현재", marker_color='steelblue'))
                fig2.add_trace(go.Bar(x=[f"{field}-1등급", f"{field}-2등급", f"{field}-3등급", f"{field}-4등급"],
                                       y=[row["GRAD_1_REQ_TOTAL"], row["GRAD_2_REQ_TOTAL"], row["GRAD_3_REQ_TOTAL"], row["GRAD_4_REQ_TOTAL"]],
                                       name=f"{field} 필요", marker_color='coral'))
            fig2.update_layout(barmode='group', height=500, template="plotly_white", title_text="IMQC 현재 vs 필요 인원 비교")
            cmp_path = charts_dir / "imqc_comparison.html"
            fig2.write_html(str(cmp_path))
            chart_files.append(str(cmp_path))
        
        return chart_files
    except Exception as e:
        raise VisualizationError(f"IMQC charts failed: {e}")


def create_timeline_plot(timeline_df: pd.DataFrame, title: str = "가동/비가동 타임라인") -> go.Figure:
    """Create a step plot for operational timeline."""
    try:
        fig = go.Figure()
        if timeline_df.empty:
            fig.update_layout(title=f"{title} (데이터 없음)")
            return fig
        
        fig.add_trace(go.Scatter(
            x=timeline_df['date'],
            y=timeline_df['status'],
            mode='lines',
            line_shape='hv',
            name='상태',
            line=dict(color='royalblue', width=2),
            fill='tozeroy',
            fillcolor='rgba(65,105,225,0.2)'
        ))
        
        fig.update_layout(
            title=title,
            xaxis_title="날짜",
            yaxis_title="상태 (1=가동, 0=비가동)",
            yaxis=dict(range=[-0.1, 1.1], tickvals=[0, 1], ticktext=["비가동", "가동"]),
            template="plotly_white",
            height=400,
            hovermode="x unified"
        )
        return fig
    except Exception as e:
        raise VisualizationError(f"Timeline plot failed: {e}")


def create_ram_curves(viz_df: pd.DataFrame, title: str = "RAM 곡선") -> go.Figure:
    """Create reliability, maintainability, and hazard rate curves."""
    try:
        fig = make_subplots(
            rows=1, cols=3,
            subplot_titles=("신뢰도 R(t)", "보전도 M(t)", "고장률 h(t)"),
            horizontal_spacing=0.08
        )
        if viz_df.empty:
            fig.update_layout(title=f"{title} (데이터 없음)")
            return fig
        
        fig.add_trace(go.Scatter(x=viz_df['time'], y=viz_df['reliability'],
                                   mode='lines', name='신뢰도', line=dict(color='green')),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=viz_df['time'], y=viz_df['maintainability'],
                                   mode='lines', name='보전도', line=dict(color='blue')),
                      row=1, col=2)
        fig.add_trace(go.Scatter(x=viz_df['time'], y=viz_df['hazard_rate'],
                                   mode='lines', name='고장률', line=dict(color='red')),
                      row=1, col=3)
        
        fig.update_xaxes(title_text="시간 (일)", row=1, col=1)
        fig.update_xaxes(title_text="시간 (일)", row=1, col=2)
        fig.update_xaxes(title_text="시간 (일)", row=1, col=3)
        fig.update_yaxes(title_text="확률", range=[-0.05, 1.05], row=1, col=1)
        fig.update_yaxes(title_text="확률", range=[-0.05, 1.05], row=1, col=2)
        fig.update_yaxes(title_text="비율", row=1, col=3)
        fig.update_layout(template="plotly_white", height=400, showlegend=False,
                          title=title)
        return fig
    except Exception as e:
        raise VisualizationError(f"RAM curves failed: {e}")


def create_availability_bar(availability: float, title: str = "운용가용도") -> go.Figure:
    """Create a bar chart for availability."""
    try:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=["운용가용도"],
            y=[availability],
            text=[f"{availability:.4f}"],
            textposition='outside',
            marker_color='steelblue'
        ))
        fig.update_layout(
            title=title,
            yaxis=dict(range=[0, 1.1], title="가용도"),
            template="plotly_white",
            height=400
        )
        return fig
    except Exception as e:
        raise VisualizationError(f"Availability bar failed: {e}")


def create_metric_cards(metrics: Dict[str, float]) -> List[Dict]:
    """Create metric card specs for UI rendering."""
    cards = []
    labels = {
        "mtbf": "MTBF (평균고장간격)",
        "mttr": "MTTR (평균수리시간)",
        "failure_rate": "고장률",
        "repair_rate": "수리율",
        "availability": "운용가용도"
    }
    for key, label in labels.items():
        value = metrics.get(key)
        if value is not None:
            cards.append({
                "label": label,
                "key": key,
                "value": round(float(value), 4) if isinstance(value, (int, float, float)) else value
            })
    return cards
