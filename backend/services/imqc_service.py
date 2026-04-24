import os
import uuid
import warnings
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import pandas as pd
import numpy as np

from backend.services.base import BaseAnalysisService
from backend.models.schemas import AnalysisResult
from backend.core.config import PROJECT_ROOT
from backend.core.exceptions import DataLoadError, EmptyDataError


class IMQCAnalysisService(BaseAnalysisService):
    model_id = "af_ba_req_007"
    model_name = "IMQC인원수급분석"
    
    def analyze(self, params: Dict[str, Any]) -> AnalysisResult:
        analysis_id = str(uuid.uuid4())
        output_dir = PROJECT_ROOT / "outputs" / analysis_id
        output_dir.mkdir(parents=True, exist_ok=True)
        charts_dir = output_dir / "charts"
        charts_dir.mkdir(exist_ok=True)
        
        try:
            model_dir = PROJECT_ROOT / self.model_id
            datasets_dir = model_dir / "datasets"
            
            # 데이터 로드
            grade_df = self._load_grade_data(datasets_dir)
            category_df = self._load_category_data(datasets_dir)
            plan_df = self._load_plan_data(datasets_dir)
            
            # 현재 인원 집계
            curr_calib = self._counts_es(grade_df, "도량")
            curr_elec = self._counts_es(grade_df, "전기/전자")
            curr_total = pd.concat([curr_calib, curr_elec], ignore_index=True)
            
            # 필요 인원 산출
            req_total = self._counting_total(category_df, plan_df)
            
            # 병합: 현재 vs 필요
            merged = self._merge_results(curr_total, req_total)
            if merged.empty:
                raise EmptyDataError("병합 결과가 없습니다.")
            
            # 저장
            summary_csv = output_dir / "summary.csv"
            curr_csv = output_dir / "current_personnel.csv"
            req_csv = output_dir / "required_personnel.csv"
            merged.to_csv(summary_csv, index=False, encoding="utf-8-sig")
            curr_total.to_csv(curr_csv, index=False, encoding="utf-8-sig")
            req_total.to_csv(req_csv, index=False, encoding="utf-8-sig")
            
            # 시각화
            from backend.utils.viz_utils import create_imqc_charts
            chart_files = create_imqc_charts(curr_total, req_total, merged, charts_dir)
            
            metrics = {
                "current_total": curr_total.to_dict(orient="records"),
                "required_total": req_total.to_dict(orient="records"),
                "comparison": merged.to_dict(orient="records"),
            }
            
            return AnalysisResult(
                analysis_id=analysis_id,
                model_id=self.model_id,
                status="success",
                message=f"IMQC 인원수급 분석 완료: {len(merged)}개 항목",
                metrics=metrics,
                summary_csv=str(summary_csv),
                charts=chart_files,
            )
            
        except Exception as e:
            return AnalysisResult(
                analysis_id=analysis_id,
                model_id=self.model_id,
                status="failed",
                message=str(e),
            )
    
    def _load_grade_data(self, datasets_dir: Path):
        files = list(datasets_dir.glob("*.xlsx"))
        target = None
        for f in files:
            # 유니코드 정규화 대응
            name_nfc = __import__('unicodedata').normalize('NFC', f.name)
            if "등급현황" in name_nfc:
                target = f
                break
        if not target:
            raise DataLoadError("IMQC 등급현황 파일 없음")
        return pd.read_excel(target, header=3, engine="openpyxl", sheet_name=None)
    
    def _load_category_data(self, datasets_dir: Path):
        files = list(datasets_dir.glob("*.xlsx"))
        target = None
        for f in files:
            name_nfc = __import__('unicodedata').normalize('NFC', f.name)
            if "개선" in name_nfc and "관리항목" in name_nfc:
                target = f
                break
        if not target:
            raise DataLoadError("IMQC 개선 및 관리항목 파일 없음")
        return pd.read_excel(target, header=0, engine="openpyxl", sheet_name=None)
    
    def _load_plan_data(self, datasets_dir: Path):
        files = list(datasets_dir.glob("*.xlsx"))
        target = None
        for f in files:
            name_nfc = __import__('unicodedata').normalize('NFC', f.name)
            if "계획수립현황" in name_nfc:
                target = f
                break
        if not target:
            raise DataLoadError("계획수립현황 파일 없음")
        return pd.read_excel(target, engine="openpyxl")
    
    def _counts_es(self, df_dict, type_name):
        now = datetime.now()
        year_val = now.year
        month_val = now.month
        rows = []
        for es_num in [1, 2, 3, 5, 6, 7, 8]:
            sheet_name = f"{es_num}시험소"
            if sheet_name not in df_dict:
                continue
            es_df = df_dict[sheet_name]
            es_df = es_df.replace("―", np.nan)
            
            # type_name 컬럼 찾기 (정확한 이름 매칭)
            target_col = None
            for col in es_df.columns:
                if type_name in str(col):
                    target_col = col
                    break
            if target_col is None:
                continue
            
            es_df = es_df.dropna(subset=[target_col])
            es_df = es_df.reset_index(drop=True)
            
            # 등급 추출
            def extract_grade(value):
                try:
                    return int(str(value)[0])
                except:
                    return np.nan
            
            es_df["grade"] = es_df[target_col].apply(extract_grade)
            es_df = es_df.dropna(subset=["grade"])
            
            count_type = (
                es_df["grade"]
                .value_counts()
                .sort_index()
                .reindex([1, 2, 3, 4], fill_value=0)
            )
            
            rows.append({
                "AFF": sheet_name,
                "FIELD": type_name,
                "GRAD_1_COUNT": int(count_type.loc[1]),
                "GRAD_2_COUNT": int(count_type.loc[2]),
                "GRAD_3_COUNT": int(count_type.loc[3]),
                "GRAD_4_COUNT": int(count_type.loc[4]),
                "YEAR": year_val,
                "MONTH": month_val,
            })
        return pd.DataFrame(rows)
    
    def _counting_total(self, category_df, personal_status):
        now = datetime.now()
        year_val = now.year
        
        # WUC 코드 추출
        wuc_list = []
        field_list = []
        for sheet, field_name in [
            ("IMQC 관리항목(신)_도량", "도량"),
            ("IMQC 관리항목(신)_전기", "전기/전자"),
            ("IMQC 관리항목(신)_전자", "전기/전자"),
        ]:
            if sheet in category_df:
                wuc_list.extend(category_df[sheet]["WUC"].dropna().astype(str).tolist())
                field_list.extend([field_name] * len(category_df[sheet]["WUC"].dropna()))
        
        wuc_df = pd.DataFrame({"정밀측정분류코드": wuc_list, "작업": field_list})
        
        # 계획수립현황 필터링
        ps = personal_status[personal_status["계획년도"] == 2025].copy()
        ps = ps[["군", "지원시험소_코드화", "계획년도", "계획월", "계획여부",
                 "표준인시", "난이도", "정밀측정분류코드"]]
        ps = ps[ps["계획여부"] == "Y"]
        ps = ps[ps["군"] == "공군"]
        
        merged = ps.merge(wuc_df, on="정밀측정분류코드", how="left")
        merged = merged.dropna(subset=["작업"])
        merged = merged.drop_duplicates(subset=["군", "지원시험소_코드화", "계획년도",
                                                 "계획월", "계획여부", "난이도",
                                                 "정밀측정분류코드", "작업"])
        
        result = (
            merged
            .groupby(["작업", "지원시험소_코드화", "계획년도", "계획월", "난이도"])["표준인시"]
            .sum()
            .reset_index()
        )
        
        _MONTH_WORK_DAYS = {1:23, 2:20, 3:21, 4:22, 5:22, 6:21,
                            7:23, 8:21, 9:22, 10:23, 11:20, 12:23}
        
        def _int_required(std_hour_sum, month):
            days = _MONTH_WORK_DAYS.get(int(month), 22)
            if not std_hour_sum:
                return 0
            return int((float(std_hour_sum) / 5.05) / days)
        
        need_map = {}
        for _, row in result.iterrows():
            field_val = row["작업"]
            aff_val = row["지원시험소_코드화"]
            if aff_val not in ["시험소001", "시험소002", "시험소003",
                               "시험소005", "시험소006", "시험소007", "시험소008"]:
                continue
            month_val = int(row["계획월"])
            diff = row["난이도"]
            st_sum = float(row["표준인시"])
            diff_int = int(diff)
            required = _int_required(st_sum, month_val)
            key = (field_val, aff_val, month_val)
            if key not in need_map:
                need_map[key] = {"grad_1_count": 0, "grad_2_count": 0,
                                  "grad_3_count": 0, "grad_4_count": 0}
            col_name = f"grad_{diff_int}_count"
            need_map[key][col_name] += required
        
        rows = []
        for (field, aff, month), counts in need_map.items():
            rows.append({
                "AFF": aff,
                "FIELD": field,
                "YEAR": year_val,
                "MONTH": month,
                "GRAD_1_COUNT": counts.get("grad_1_count", 0),
                "GRAD_2_COUNT": counts.get("grad_2_count", 0),
                "GRAD_3_COUNT": counts.get("grad_3_count", 0),
                "GRAD_4_COUNT": counts.get("grad_4_count", 0),
            })
        return pd.DataFrame(rows)
    
    def _merge_results(self, curr_df, req_df):
        if curr_df.empty or req_df.empty:
            return pd.DataFrame()
        
        curr_totals = (
            curr_df
            .groupby(["FIELD", "YEAR", "MONTH"], as_index=False)[["GRAD_1_COUNT", "GRAD_2_COUNT",
                                                                    "GRAD_3_COUNT", "GRAD_4_COUNT"]]
            .sum()
            .rename(columns={"GRAD_1_COUNT": "GRAD_1_CUR_TOTAL", "GRAD_2_COUNT": "GRAD_2_CUR_TOTAL",
                             "GRAD_3_COUNT": "GRAD_3_CUR_TOTAL", "GRAD_4_COUNT": "GRAD_4_CUR_TOTAL"})
        )
        req_totals = (
            req_df
            .groupby(["FIELD", "YEAR", "MONTH"], as_index=False)[["GRAD_1_COUNT", "GRAD_2_COUNT",
                                                                    "GRAD_3_COUNT", "GRAD_4_COUNT"]]
            .sum()
            .rename(columns={"GRAD_1_COUNT": "GRAD_1_REQ_TOTAL", "GRAD_2_COUNT": "GRAD_2_REQ_TOTAL",
                             "GRAD_3_COUNT": "GRAD_3_REQ_TOTAL", "GRAD_4_COUNT": "GRAD_4_REQ_TOTAL"})
        )
        merged = pd.merge(curr_totals, req_totals, on=["FIELD", "YEAR", "MONTH"], how="inner")
        return merged
