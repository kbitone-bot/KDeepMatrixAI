import os
import uuid
import pickle
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
from sklearn.base import clone

from backend.services.base import BaseAnalysisService
from backend.models.schemas import AnalysisResult
from backend.core.config import PROJECT_ROOT
from backend.core.exceptions import DataLoadError


BEST_MODELS = {
    "시험소002": "ElasticNet",
    "시험소003": "RidgeRegression",
    "시험소004": "LinearRegression",
    "시험소005": "LinearRegression",
    "시험소006": "XGBRegressor",
    "시험소007": "KNN",
    "시험소008": "XGBRegressor",
    "시험소009": "MLPRegressor",
    "시험소010": "SVR",
    "시험소011": "RidgeRegression",
    "시험소012": "RandomForestRegressor",
    "시험소014": "RandomForestRegressor",
}


class SimAnalysisService(BaseAnalysisService):
    model_id = "af_ba_req_004"
    model_name = "시험소작업량예측"
    
    def __init__(self):
        self.models_dir = PROJECT_ROOT / "outputs" / "models_004"
        self._cache = {}
    
    def _load_stl(self, stl_num: str):
        if stl_num in self._cache:
            return self._cache[stl_num]
        
        stl_dir = self.models_dir / stl_num
        if not stl_dir.exists():
            raise DataLoadError(f"Model for {stl_num} not found. Run scripts/train_004.py first.")
        
        model_name = BEST_MODELS.get(stl_num, "XGBRegressor")
        
        scaler = joblib.load(stl_dir / f"Simulation_049_{stl_num}_minmax.pickle")
        model = joblib.load(stl_dir / f"Simulation_049_{stl_num}_{model_name}.pickle")
        
        calib_path = stl_dir / f"Simulation_049_{stl_num}_{model_name}_calibration.pkl"
        with open(calib_path, "rb") as f:
            calib_data = pickle.load(f)
        
        common_path = stl_dir / f"Simulation_049_{stl_num}_common_calibration.pkl"
        X_fit, y_fit, random_seed = None, None, 42
        if common_path.exists():
            with open(common_path, "rb") as f:
                common = pickle.load(f)
            X_fit = common["X_fit"]
            y_fit = common["y_fit"]
            random_seed = common.get("random_seed", 42)
        
        self._cache[stl_num] = {
            "scaler": scaler,
            "model": model,
            "model_name": model_name,
            "calib": calib_data,
            "X_fit": X_fit,
            "y_fit": y_fit,
            "random_seed": random_seed,
            "stl_dir": stl_dir,
        }
        return self._cache[stl_num]
    
    def _prepare_dataset(self, stl_num: str, week_num: int, var_Difficulty: str,
                         var_TechGrade: str, var_Efficiency: int,
                         var_MaintCycle: int, var_ConsMH: int):
        stl_dir = self.models_dir / stl_num
        
        # inference set 로드
        inf_path = stl_dir / f"Simulation_051_inferenceSet_{stl_num}.csv"
        df_infSet = pd.read_csv(inf_path, encoding="utf-8-sig")
        df_inf_week = df_infSet[df_infSet['week'] == week_num]
        if df_inf_week.empty:
            diff = (df_infSet['week'] - week_num).abs()
            nearest_week = df_infSet.loc[diff.idxmin(), 'week']
            df_inf_week = df_infSet[df_infSet['week'] == nearest_week]
        
        df_inf_week = df_inf_week.drop(['정비지시서번호_개수', '완료확인주', 'year', 'week'], axis=1, errors='ignore')
        
        cols_check = df_inf_week.columns.difference(['요일번호', '계절'])
        mask = (df_inf_week[cols_check] == 0).all(axis=1)
        zero_weekdays = df_inf_week.loc[mask, '요일번호'].tolist()
        
        # 조정변수
        df_inf_week['효율(%)'] = var_Efficiency
        df_inf_week['정비주기'] = var_MaintCycle
        df_inf_week['소모인시'] = var_ConsMH
        
        # valueRatio
        ratio_path = stl_dir / f"Simulation_051_valueRatio_{stl_num}.csv"
        df_ratio = pd.read_csv(ratio_path, encoding="utf-8-sig")
        diff_freq = df_ratio.loc[(df_ratio['변수명'] == '난이도') & (df_ratio['범주명'] == var_Difficulty), 'freq'].iloc[0]
        tech_freq = df_ratio.loc[(df_ratio['변수명'] == '기술등급') & (df_ratio['범주명'] == var_TechGrade), 'freq'].iloc[0]
        df_inf_week['난이도_freq'] = diff_freq
        df_inf_week['기술등급_freq'] = tech_freq
        
        # zero_weekdays 처리
        cols_to_zero = df_inf_week.columns.difference(['요일번호', '계절'])
        if zero_weekdays:
            df_inf_week.loc[df_inf_week['요일번호'].isin(zero_weekdays), cols_to_zero] = 0
        
        return df_inf_week
    
    def _bootstrap_ci(self, model, X_train, y_train, X_new, B=200, conf=0.90, random_state=42):
        rng = np.random.RandomState(random_state)
        n = len(X_train)
        preds = []
        for _ in range(B):
            idx = rng.randint(0, n, n)
            Xb = X_train.iloc[idx] if hasattr(X_train, "iloc") else X_train[idx]
            yb = y_train.iloc[idx] if hasattr(y_train, "iloc") else y_train[idx]
            model_b = clone(model)
            model_b.fit(Xb, yb)
            pred_week = float(np.sum(model_b.predict(X_new)))
            preds.append(pred_week)
        preds = np.array(preds)
        alpha = 1 - conf
        ci_lower = float(np.percentile(preds, 100 * (alpha / 2)))
        ci_upper = float(np.percentile(preds, 100 * (1 - alpha / 2)))
        mean_pred = float(preds.mean())
        return mean_pred, ci_lower, ci_upper
    
    def analyze(self, params: Dict[str, Any]) -> AnalysisResult:
        analysis_id = str(uuid.uuid4())
        try:
            stl_num = params.get("stl_num", "시험소008")
            week_num = int(params.get("week_num", datetime.now().isocalendar()[1]))
            difficulty = params.get("difficulty", "A")
            tech_grade = params.get("tech_grade", "2C")
            efficiency = int(params.get("efficiency", 80))
            maint_cycle = int(params.get("maint_cycle", 12))
            cons_mh = int(params.get("cons_mh", 100))
            
            cache = self._load_stl(stl_num)
            scaler = cache["scaler"]
            model = cache["model"]
            calib = cache["calib"]
            X_fit = cache["X_fit"]
            y_fit = cache["y_fit"]
            random_seed = cache["random_seed"]
            
            # 데이터 준비
            df_inf_week = self._prepare_dataset(stl_num, week_num, difficulty, tech_grade,
                                                efficiency, maint_cycle, cons_mh)
            
            # 스케일링
            X_new = df_inf_week.values
            X_new_scaled = scaler.transform(X_new)
            
            # 예측
            yhat_daily = model.predict(X_new_scaled)
            yhat_week = float(np.sum(yhat_daily))
            
            alpha = 0.10
            q = calib['q_090'] if alpha == 0.10 else calib.get('q_095', calib['q_090'])
            pi_lower = max(yhat_week - q, 0)
            pi_upper = max(yhat_week + q, 0)
            
            result = {
                "stl_num": stl_num,
                "model_name": cache["model_name"],
                "y_pred": int(np.rint(yhat_week)),
                "pi_lower": int(np.rint(pi_lower)),
                "pi_upper": int(np.rint(pi_upper)),
            }
            
            return AnalysisResult(
                analysis_id=analysis_id,
                model_id=self.model_id,
                status="success",
                message=f"{stl_num} 작업량 예측 완료",
                metrics=result,
            )
            
        except Exception as e:
            return AnalysisResult(
                analysis_id=analysis_id,
                model_id=self.model_id,
                status="failed",
                message=str(e),
            )
