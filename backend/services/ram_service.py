import os
import uuid
import warnings
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

import pandas as pd
import numpy as np
from scipy.special import gamma
from lifelines import WeibullFitter, ExponentialFitter, LogNormalFitter

from backend.services.base import BaseAnalysisService
from backend.models.schemas import AnalysisResult, RAMMetrics
from backend.core.config import PROJECT_ROOT, VALID_CODES, CODE_MAP
from backend.core.exceptions import DataLoadError, EmptyDataError, DistributionFitError
from backend.utils.data_loader import load_ram_data, validate_columns
from backend.utils.date_utils import ensure_datetime
from backend.utils.viz_utils import (
    create_timeline_plot,
    create_ram_curves,
    create_availability_bar,
    create_metric_cards,
)


class RAMAnalysisService(BaseAnalysisService):
    model_id = "af_ba_req_001"
    model_name = "장비운용가용도분석 (RAM)"
    
    REQUIRED_COLS = ["pn", "pclrt_idno", "mntnc_reqstdt", "rels_dhm", "mntnc_rslt_actn_cd"]
    DATE_COLS = ["mntnc_reqstdt", "rels_dhm"]
    
    def analyze(self, params: Dict[str, Any]) -> AnalysisResult:
        analysis_id = str(uuid.uuid4())
        output_dir = PROJECT_ROOT / "outputs" / analysis_id
        output_dir.mkdir(parents=True, exist_ok=True)
        charts_dir = output_dir / "charts"
        charts_dir.mkdir(exist_ok=True)
        
        try:
            model_dir = PROJECT_ROOT / self.model_id
            df_raw = load_ram_data(model_dir, date_cols=self.DATE_COLS)
            validate_columns(df_raw, self.REQUIRED_COLS)
            
            mode = params.get("mode", "수리")
            no_pn = params.get("no_pn") or None
            no_pclrt_idno = params.get("no_pclrt_idno") or None
            start_date = pd.to_datetime(params.get("start_date", "2021-01-01"))
            end_date = pd.to_datetime(params.get("end_date", datetime.now().strftime("%Y-%m-%d")))
            
            df_processed = self._preprocess(df_raw, no_pn, no_pclrt_idno, mode, start_date, end_date)
            if df_processed.empty:
                raise EmptyDataError("필터링 후 분석 대상 데이터가 없습니다.")
            
            summaries = []
            visualizations = []
            timeline_logs = []
            chart_files = []
            
            pn_list = df_processed["pn"].unique().tolist()
            
            for pn in pn_list:
                df_pn = df_processed[df_processed["pn"] == pn]
                pclrt_list = df_pn["pclrt_idno"].unique().tolist()
                
                tbf_durations_all, tbf_events_all = [], []
                ttr_durations_all, ttr_events_all = [], []
                df_daily_log_pn = None
                
                for pclrt in pclrt_list:
                    df_unit = df_pn[df_pn["pclrt_idno"] == pclrt].copy()
                    df_timeline = self._create_timeline(df_unit, start_date, end_date)
                    
                    if df_timeline.empty:
                        continue
                    
                    # 일별 로그 (단일 장비 선택 시에만)
                    if no_pclrt_idno and len(pn_list) == 1 and len(pclrt_list) == 1:
                        df_daily_log_pn = self._create_daily_log(df_timeline, start_date, end_date)
                        df_daily_log_pn["analysis_id"] = analysis_id
                        df_daily_log_pn["pn"] = pn
                        df_daily_log_pn["pclrt_idno"] = pclrt
                        timeline_logs.append(df_daily_log_pn)
                    
                    (tbf_d, tbf_e), (ttr_d, ttr_e) = self._calculate_durations(df_timeline, end_date)
                    tbf_durations_all.extend(tbf_d)
                    tbf_events_all.extend(tbf_e)
                    ttr_durations_all.extend(ttr_d)
                    ttr_events_all.extend(ttr_e)
                
                if not tbf_durations_all and not ttr_durations_all:
                    continue
                
                tbf_model = self._find_best_distribution(tbf_durations_all, tbf_events_all)
                ttr_model = self._find_best_distribution(ttr_durations_all, ttr_events_all)
                
                ram_metrics = self._calculate_ram_metrics(tbf_model, ttr_model)
                
                summary_row = {
                    "analysis_id": analysis_id,
                    "pn": pn,
                    "pclrt_idno": no_pclrt_idno if no_pclrt_idno else "ALL",
                    **ram_metrics,
                    "best_tbf_dist": self._dist_name(tbf_model),
                    "best_ttr_dist": self._dist_name(ttr_model),
                }
                summaries.append(summary_row)
                
                viz_df = self._create_viz_data(tbf_model, ttr_model, tbf_durations_all, ttr_durations_all, ram_metrics)
                viz_df["analysis_id"] = analysis_id
                viz_df["pn"] = pn
                viz_df["pclrt_idno"] = no_pclrt_idno if no_pclrt_idno else "ALL"
                visualizations.append(viz_df)
                
                # 차트 생성 (HTML)
                if not viz_df.empty:
                    ram_fig = create_ram_curves(viz_df, title=f"RAM 곡선 - {pn}")
                    ram_path = charts_dir / f"ram_curves_{pn}.html"
                    ram_fig.write_html(str(ram_path))
                    chart_files.append(str(ram_path))
                    
                    avail_fig = create_availability_bar(ram_metrics["availability"], title=f"운용가용도 - {pn}")
                    avail_path = charts_dir / f"availability_{pn}.html"
                    avail_fig.write_html(str(avail_path))
                    chart_files.append(str(avail_path))
            
            if not summaries:
                raise EmptyDataError("분석 결과가 생성되지 않았습니다.")
            
            df_summary = pd.DataFrame(summaries)
            df_viz = pd.concat(visualizations, ignore_index=True) if visualizations else pd.DataFrame()
            df_timeline = pd.concat(timeline_logs, ignore_index=True) if timeline_logs else pd.DataFrame()
            
            summary_csv = output_dir / "summary.csv"
            viz_csv = output_dir / "visualization.csv"
            timeline_csv = output_dir / "timeline.csv"
            
            df_summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
            if not df_viz.empty:
                df_viz.to_csv(viz_csv, index=False, encoding="utf-8-sig")
            if not df_timeline.empty:
                df_timeline.to_csv(timeline_csv, index=False, encoding="utf-8-sig")
            
            # Report HTML 생성
            report_html = self._generate_report(df_summary, chart_files, output_dir)
            
            return AnalysisResult(
                analysis_id=analysis_id,
                model_id=self.model_id,
                status="success",
                message=f"분석 완료: {len(summaries)}개 부품 번호",
                metrics={"summary": summaries},
                summary_csv=str(summary_csv),
                viz_csv=str(viz_csv) if not df_viz.empty else None,
                timeline_csv=str(timeline_csv) if not df_timeline.empty else None,
                charts=chart_files,
                report_html=str(report_html),
            )
            
        except Exception as e:
            return AnalysisResult(
                analysis_id=analysis_id,
                model_id=self.model_id,
                status="failed",
                message=str(e),
            )
    
    def _preprocess(self, df, no_pn, no_pclrt_idno, mode, start_date, end_date) -> pd.DataFrame:
        df = df.copy()
        df["mntnc_rslt_actn_cd"] = df["mntnc_rslt_actn_cd"].astype(str).replace(CODE_MAP)
        df = df[df["mntnc_rslt_actn_cd"].isin(VALID_CODES)]
        df["mntnc_reqstdt"] = pd.to_datetime(df["mntnc_reqstdt"], errors="coerce")
        df["rels_dhm"] = pd.to_datetime(df["rels_dhm"], errors="coerce")
        
        if no_pn:
            df = df[df["pn"] == no_pn]
        if no_pclrt_idno:
            df = df[df["pclrt_idno"] == no_pclrt_idno]
        
        df = df[
            (df["mntnc_reqstdt"] < end_date) &
            ((df["rels_dhm"] > start_date) | (pd.isna(df["rels_dhm"])))
        ]
        
        def assign_status(row):
            if mode == "수리":
                return "가동" if row["mntnc_rslt_actn_cd"] == "J" else "비가동"
            return "비가동"
        
        df["event_status"] = df.apply(assign_status, axis=1)
        df = df.sort_values(by=["pn", "pclrt_idno", "mntnc_reqstdt"]).reset_index(drop=True)
        return df
    
    def _create_timeline(self, df, start_date, end_date) -> pd.DataFrame:
        timeline_events = []
        if df.empty:
            return pd.DataFrame(columns=["start_time", "end_time", "status"])
        
        first_event_start = df.iloc[0]["mntnc_reqstdt"]
        if start_date < first_event_start:
            timeline_events.append({"start_time": start_date, "end_time": first_event_start, "status": "가동"})
        
        df = df.copy()
        df["next_mntnc_reqstdt"] = df["mntnc_reqstdt"].shift(-1)
        
        for _, row in df.iterrows():
            event_start = row["mntnc_reqstdt"]
            event_end = row["rels_dhm"]
            next_event_start = row["next_mntnc_reqstdt"]
            event_status = row["event_status"]
            
            actual_start = max(event_start, start_date)
            actual_end = min(event_end if pd.notna(event_end) else end_date, end_date)
            
            if actual_start < actual_end:
                timeline_events.append({"start_time": actual_start, "end_time": actual_end, "status": event_status})
            
            if pd.notna(event_end) and event_end < end_date:
                gap_start = max(event_end, start_date)
                gap_end = min(next_event_start if pd.notna(next_event_start) else end_date, end_date)
                if gap_start < gap_end:
                    timeline_events.append({"start_time": gap_start, "end_time": gap_end, "status": "가동"})
        
        if not timeline_events:
            return pd.DataFrame(columns=["start_time", "end_time", "status"])
        
        df_tl = pd.DataFrame(timeline_events)
        df_tl = df_tl[df_tl["start_time"] < df_tl["end_time"]]
        df_tl = df_tl.sort_values(by="start_time").reset_index(drop=True)
        df_tl["start_time"] = df_tl["start_time"].dt.strftime("%Y-%m-%d")
        df_tl["end_time"] = df_tl["end_time"].dt.strftime("%Y-%m-%d")
        return df_tl
    
    def _create_daily_log(self, df_timeline, start_date, end_date) -> pd.DataFrame:
        if df_timeline.empty:
            return pd.DataFrame(columns=["date", "status_code"])
        
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        df_log = pd.DataFrame(date_range, columns=["date"])
        df_log["status_code"] = 0
        
        for _, row in df_timeline.iterrows():
            if row["status"] == "가동":
                row_start = pd.to_datetime(row["start_time"])
                row_end = pd.to_datetime(row["end_time"])
                mask = (df_log["date"] >= row_start) & (df_log["date"] < row_end)
                if row_end == end_date:
                    mask = mask | (df_log["date"] == end_date)
                df_log.loc[mask, "status_code"] = 1
        
        df_log["date"] = df_log["date"].dt.strftime("%Y-%m-%d")
        return df_log
    
    def _calculate_durations(self, df_timeline, end_date) -> Tuple[Tuple[List, List], Tuple[List, List]]:
        end_date = pd.to_datetime(end_date)
        tbf_d, tbf_e = [], []
        ttr_d, ttr_e = [], []
        
        if df_timeline.empty:
            return (tbf_d, tbf_e), (ttr_d, ttr_e)
        
        last_index = len(df_timeline) - 1
        for i, row in df_timeline.iterrows():
            start_time = pd.to_datetime(row["start_time"])
            end_time = pd.to_datetime(row["end_time"])
            status = row["status"]
            duration = (end_time - start_time) / pd.Timedelta(days=1)
            if duration <= 0:
                continue
            is_censored = (i == last_index) and (end_time == end_date)
            observed = 0 if is_censored else 1
            if status == "가동":
                tbf_d.append(duration)
                tbf_e.append(observed)
            else:
                ttr_d.append(duration)
                ttr_e.append(observed)
        
        return (tbf_d, tbf_e), (ttr_d, ttr_e)
    
    def _find_best_distribution(self, durations, events):
        if not durations or len(durations) < 2:
            return None
        models = {
            "LogNormal": LogNormalFitter(),
            "Exponential": ExponentialFitter(),
            "Weibull": WeibullFitter(),
        }
        best_model, best_aic = None, np.inf
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for name, model in models.items():
                try:
                    model.fit(durations, event_observed=events)
                    if not np.isfinite(model.AIC_):
                        continue
                    if model.AIC_ < best_aic:
                        best_aic, best_model = model.AIC_, model
                except Exception:
                    pass
        return best_model
    
    def _calculate_ram_metrics(self, tbf_model, ttr_model) -> Dict[str, float]:
        mtbf = self._get_model_mean(tbf_model)
        mttr = self._get_model_mean(ttr_model)
        failure_rate = 1.0 / mtbf if mtbf and mtbf > 0 else 0.0
        repair_rate = 1.0 / mttr if mttr and mttr > 0 else 0.0
        if mtbf and mtbf > 0:
            if mttr and mttr > 0:
                availability = mtbf / (mtbf + mttr)
            else:
                availability = 1.0
        else:
            availability = 0.0
        return {
            "mtbf": round(float(mtbf), 4) if np.isfinite(mtbf) else 0.0,
            "mttr": round(float(mttr), 4) if np.isfinite(mttr) else 0.0,
            "failure_rate": round(float(failure_rate), 6),
            "repair_rate": round(float(repair_rate), 6),
            "availability": round(float(availability), 4),
        }
    
    def _get_model_mean(self, model):
        if model is None:
            return 0.0
        model_type = model.__class__.__name__
        mean_val = 0.0
        try:
            if model_type == "LogNormalFitter":
                mean_val = np.exp(model.mu_ + (model.sigma_ ** 2) / 2)
            elif model_type == "ExponentialFitter":
                mean_val = model.lambda_
            elif model_type == "WeibullFitter":
                mean_val = model.lambda_ * gamma(1 + 1 / model.rho_)
            elif hasattr(model, "mean_"):
                mean_val = model.mean_
        except Exception:
            mean_val = np.nan
        
        if np.isfinite(mean_val):
            return mean_val
        try:
            median_val = model.median_
            return median_val if np.isfinite(median_val) else np.nan
        except Exception:
            return np.nan
    
    def _create_viz_data(self, tbf_model, ttr_model, tbf_durations, ttr_durations, ram_metrics) -> pd.DataFrame:
        max_tbf = int(np.max(tbf_durations)) if tbf_durations else 0
        max_ttr = int(np.max(ttr_durations)) if ttr_durations else 0
        t_max = max(max_tbf, max_ttr, 1)
        t = np.arange(t_max + 1)
        
        reliability = np.zeros_like(t, dtype=float)
        hazard_rate = np.zeros_like(t, dtype=float)
        maintainability = np.zeros_like(t, dtype=float)
        
        if tbf_model and tbf_durations:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                reliability = tbf_model.survival_function_at_times(t).values
                hazard_rate = tbf_model.hazard_at_times(t).values
        
        if ttr_model and ttr_durations:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                maintainability = 1.0 - ttr_model.survival_function_at_times(t).values
        
        df_viz = pd.DataFrame({
            "time": t,
            "reliability": reliability,
            "maintainability": maintainability,
            "hazard_rate": hazard_rate,
            "availability": ram_metrics.get("availability", 0.0),
        })
        return df_viz
    
    def _dist_name(self, model) -> Optional[str]:
        if model is None:
            return None
        return model.__class__.__name__.replace("Fitter", "")
    
    def _generate_report(self, df_summary, chart_files, output_dir: Path) -> Path:
        html_path = output_dir / "report.html"
        rows = ""
        for _, row in df_summary.iterrows():
            rows += f"<tr><td>{row['pn']}</td><td>{row['pclrt_idno']}</td><td>{row['mtbf']}</td><td>{row['mttr']}</td><td>{row['availability']}</td></tr>"
        
        charts_html = ""
        for cf in chart_files:
            rel = os.path.basename(cf)
            charts_html += f'<li><a href="charts/{rel}">{rel}</a></li>'
        
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>RAM 분석 보고서</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 40px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
th {{ background-color: #f2f2f2; }}
h1 {{ color: #333; }}
</style></head>
<body>
<h1>RAM 분석 보고서</h1>
<p>생성일: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<h2>요약</h2>
<table>
<tr><th>부품번호</th><th>식별번호</th><th>MTBF</th><th>MTTR</th><th>가용도</th></tr>
{rows}
</table>
<h2>차트</h2>
<ul>{charts_html}</ul>
</body></html>"""
        html_path.write_text(html, encoding="utf-8")
        return html_path
