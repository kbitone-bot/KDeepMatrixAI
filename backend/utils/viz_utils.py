import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import List, Dict, Optional
from backend.core.exceptions import VisualizationError


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
