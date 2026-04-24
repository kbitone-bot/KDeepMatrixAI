import os
import uuid
import warnings
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import pandas as pd
import numpy as np
from scipy.stats import norm, expon, weibull_min
from fitter import Fitter

from backend.services.base import BaseAnalysisService
from backend.models.schemas import AnalysisResult
from backend.core.config import PROJECT_ROOT, VALID_CODES, CODE_MAP
from backend.core.exceptions import DataLoadError, EmptyDataError, DistributionFitError
from backend.utils.data_loader import load_ram_data, validate_columns
from backend.utils.date_utils import ensure_datetime
from backend.utils.viz_utils import (
    create_lifetime_pdf_plot,
    create_lifetime_cdf_plot,
)


class LifeAnalysisService(BaseAnalysisService):
    model_id = "af_ba_req_002"
    model_name = "장비수명예측"
    
    REQUIRED_COLS = ["pn", "acqdt", "aprv_prcss_dttm"]
    DATE_COLS = ["acqdt", "aprv_prcss_dttm"]
    
    def analyze(self, params: Dict[str, Any]) -> AnalysisResult:
        analysis_id = str(uuid.uuid4())
        output_dir = PROJECT_ROOT / "outputs" / analysis_id
        output_dir.mkdir(parents=True, exist_ok=True)
        charts_dir = output_dir / "charts"
        charts_dir.mkdir(exist_ok=True)
        
        try:
            model_dir = PROJECT_ROOT / self.model_id
            df_raw = self._load_data(model_dir)
            validate_columns(df_raw, self.REQUIRED_COLS)
            
            no_pn = params.get("pn") or params.get("no_pn") or None
            
            df_processed = self._preprocess(df_raw, no_pn)
            if df_processed.empty:
                raise EmptyDataError("필터링 후 분석 대상 데이터가 없습니다.")
            
            summaries = []
            visualizations = []
            chart_files = []
            
            pn_list = df_processed["pn"].unique().tolist()[:10]  # 상위 10개
            if no_pn:
                pn_list = [no_pn]
            
            for pn in pn_list:
                durations, total_values = self._create_use_data(df_processed, pn)
                if not durations or len(durations) < 2:
                    continue
                
                best_dist, best_params, best_pvalue = self._find_best_distribution(durations)
                if not best_dist:
                    continue
                
                metrics = self._calculate_metrics(best_dist, best_params)
                if not metrics:
                    continue
                
                summary_row = {
                    "analysis_id": analysis_id,
                    "pn": pn,
                    "total_values": total_values,
                    "valid_values": len(durations),
                    **metrics,
                    "best_dist": best_dist,
                    "p_value": round(float(best_pvalue), 6) if best_pvalue is not None else None,
                }
                summaries.append(summary_row)
                
                viz_df = self._create_viz_data(durations, best_dist, best_params, metrics)
                viz_df["analysis_id"] = analysis_id
                viz_df["pn"] = pn
                visualizations.append(viz_df)
                
                # Plotly 차트 생성
                pdf_fig = create_lifetime_pdf_plot(viz_df, best_dist, metrics["expected_lifetime"])
                pdf_path = charts_dir / f"pdf_{pn}.html"
                pdf_fig.write_html(str(pdf_path))
                chart_files.append(str(pdf_path))
                
                cdf_fig = create_lifetime_cdf_plot(viz_df, best_dist, metrics["lifetime_10p"], metrics["lifetime_50p"])
                cdf_path = charts_dir / f"cdf_{pn}.html"
                cdf_fig.write_html(str(cdf_path))
                chart_files.append(str(cdf_path))
            
            if not summaries:
                raise EmptyDataError("분석 결과가 생성되지 않았습니다.")
            
            df_summary = pd.DataFrame(summaries)
            df_viz = pd.concat(visualizations, ignore_index=True) if visualizations else pd.DataFrame()
            
            summary_csv = output_dir / "summary.csv"
            viz_csv = output_dir / "visualization.csv"
            df_summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
            if not df_viz.empty:
                df_viz.to_csv(viz_csv, index=False, encoding="utf-8-sig")
            
            return AnalysisResult(
                analysis_id=analysis_id,
                model_id=self.model_id,
                status="success",
                message=f"분석 완료: {len(summaries)}개 부품 번호",
                metrics={"summary": summaries},
                summary_csv=str(summary_csv),
                viz_csv=str(viz_csv) if not df_viz.empty else None,
                charts=chart_files,
            )
            
        except Exception as e:
            return AnalysisResult(
                analysis_id=analysis_id,
                model_id=self.model_id,
                status="failed",
                message=str(e),
            )
    
    def _load_data(self, model_dir: Path) -> pd.DataFrame:
        data_files = list((model_dir / "data").glob("*.xlsb"))
        if not data_files:
            raise DataLoadError(f"No data files in {model_dir}/data")
        # 컬럼으로 올바른 파일 선택 (acqdt 컬럼이 있는 파일)
        target = None
        for f in data_files:
            try:
                df_temp = pd.read_excel(f, nrows=1, engine="pyxlsb")
                if "acqdt" in df_temp.columns:
                    target = f
                    break
            except Exception:
                continue
        if not target:
            target = data_files[0]
        df = pd.read_excel(target, dtype={"acqdt": object, "aprv_prcss_dttm": object}, engine="pyxlsb")
        df["acqdt"] = ensure_datetime(df, ["acqdt"])["acqdt"]
        df["aprv_prcss_dttm"] = ensure_datetime(df, ["aprv_prcss_dttm"])["aprv_prcss_dttm"]
        return df
    
    def _preprocess(self, df, no_pn):
        if no_pn:
            df = df[df["pn"] == no_pn].copy()
        df = df.sort_values(by=["pn", "acqdt"]).reset_index(drop=True)
        return df
    
    def _create_use_data(self, df, no_pn):
        df_pn = df[df["pn"] == no_pn].copy()
        total_values = len(df_pn)
        df_pn["use_date"] = (df_pn["aprv_prcss_dttm"] - df_pn["acqdt"]) / pd.Timedelta(days=1)
        df_pn = df_pn[df_pn["use_date"] > 0.0]
        df_pn["use_year"] = (df_pn["use_date"] / 365).round(3)
        durations = df_pn["use_year"].tolist()
        return durations, total_values
    
    def _find_best_distribution(self, durations):
        if not durations or len(durations) < 2:
            return None, None, None
        try:
            models = ["norm", "expon", "weibull_min"]
            fin_dist = Fitter(durations, distributions=models, timeout=30)
            fin_dist.fit()
            summary_df = fin_dist.summary()
            best_dict = fin_dist.get_best()
            if not best_dict:
                return None, None, None
            best_dist = list(best_dict.keys())[0]
            best_params = fin_dist.fitted_param[best_dist]
            best_pvalue = summary_df.loc[best_dist, "ks_pvalue"]
            return best_dist, best_params, best_pvalue
        except Exception as e:
            return None, None, None
    
    def _calculate_metrics(self, best_dist, best_params):
        if not best_dist:
            return {}
        dist_map = {"norm": norm, "expon": expon, "weibull_min": weibull_min}
        dist_name = dist_map.get(best_dist)
        if not dist_name:
            return {}
        expected_lifetime = dist_name.mean(*best_params)
        lifetime_10p = dist_name.ppf(0.1, *best_params)
        lifetime_50p = dist_name.ppf(0.5, *best_params)
        return {
            "expected_lifetime": round(float(expected_lifetime), 3),
            "lifetime_10p": round(float(lifetime_10p), 3),
            "lifetime_50p": round(float(lifetime_50p), 3),
        }
    
    def _create_viz_data(self, durations, best_dist, best_params, metrics):
        dist_map = {"norm": norm, "expon": expon, "weibull_min": weibull_min}
        dist_name = dist_map.get(best_dist)
        if not dist_name:
            return pd.DataFrame()
        t = np.arange(int(np.floor(max(durations))) + 1)
        cdf = dist_name.cdf(t, *best_params)
        pdf = dist_name.pdf(t, *best_params)
        return pd.DataFrame({
            "time": t,
            "cdf": cdf,
            "pdf": pdf,
            "expected_lifetime": metrics.get("expected_lifetime"),
            "lifetime_10p": metrics.get("lifetime_10p"),
            "lifetime_50p": metrics.get("lifetime_50p"),
        })
