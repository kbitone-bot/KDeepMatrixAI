"""
af_ba_req_004 시험소 작업량 예측 모델 학습 스크립트
합성데이터 기반 학습 → scaler + model + calibration 저장
"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import os
import json
import pickle
import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings('ignore')

# 모델들
from sklearn.linear_model import LinearRegression, Ridge, ElasticNet
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.svm import SVR
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor


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

MODEL_CLS = {
    "ElasticNet": ElasticNet(random_state=42, max_iter=2000),
    "RidgeRegression": Ridge(random_state=42),
    "LinearRegression": LinearRegression(),
    "XGBRegressor": GradientBoostingRegressor(random_state=42, n_estimators=200, max_depth=5),
    "KNN": KNeighborsRegressor(n_neighbors=5),
    "MLPRegressor": MLPRegressor(random_state=42, max_iter=1000, hidden_layer_sizes=(64, 32)),
    "SVR": SVR(kernel='rbf', C=1.0, gamma='scale'),
    "RandomForestRegressor": RandomForestRegressor(random_state=42, n_estimators=200),
}


def generate_synthetic_data(stl_num: str, n_samples: int = 5000, seed: int = 42):
    """시험소별 합성 학습데이터 생성"""
    rng = np.random.RandomState(seed)
    
    # 컬럼별 현실적인 분포 (prepare_dataset의 inferenceSet 구조 기반)
    df = pd.DataFrame()
    df['정비주기'] = rng.randint(1, 25, n_samples)
    df['시작온도'] = rng.normal(22, 3, n_samples).clip(15, 30).round(1)
    df['완료온도'] = (df['시작온도'] + rng.normal(2, 1.5, n_samples)).clip(18, 35).round(1)
    df['시작습도'] = rng.normal(55, 10, n_samples).clip(30, 80).round(1)
    df['완료습도'] = (df['시작습도'] + rng.normal(-2, 5, n_samples)).clip(25, 85).round(1)
    df['작업일수'] = rng.randint(1, 8, n_samples)
    df['소모인시'] = rng.normal(120, 40, n_samples).clip(20, 300).round(1)
    df['효율(%)'] = rng.normal(82, 8, n_samples).clip(50, 100).round(1)
    df['난이도_freq'] = rng.choice([0.15, 0.25, 0.30, 0.20, 0.10], n_samples)
    df['기술등급_freq'] = rng.choice([0.20, 0.30, 0.30, 0.15, 0.05], n_samples)
    df['요일번호'] = rng.randint(1, 8, n_samples)
    df['완료확인주'] = rng.randint(1, 54, n_samples)
    df['계절'] = rng.randint(1, 5, n_samples)
    df['year'] = rng.choice([2023, 2024, 2025], n_samples)
    df['week'] = rng.randint(1, 54, n_samples)
    
    # 타겟: 정비지시서번호_개수 (주간 작업량) - 여러 변수의 함수 + 노이즈
    base = (
        df['효율(%)'] * 0.3
        + df['정비주기'] * 1.5
        + df['소모인시'] * 0.05
        + df['난이도_freq'] * 20
        + df['기술등급_freq'] * 15
        + df['작업일수'] * 2
        - 50
    )
    noise = rng.normal(0, 8, n_samples)
    df['정비지시서번호_개수'] = (base + noise).clip(5, 200).round(0).astype(int)
    
    return df


def train_for_stl(stl_num: str, output_dir: Path):
    print(f"\n=== Training for {stl_num} ===")
    model_name = BEST_MODELS[stl_num]
    
    # 1. 합성데이터 생성
    df = generate_synthetic_data(stl_num, n_samples=8000, seed=42)
    
    # 2. X, y 분리
    y = df['정비지시서번호_개수'].values
    X = df.drop('정비지시서번호_개수', axis=1)
    feature_cols = list(X.columns)
    
    # 3. 학습/검증 분할
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 4. 스케일링
    scaler = MinMaxScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s = scaler.transform(X_val)
    
    # 5. 모델 학습
    model = MODEL_CLS[model_name]
    model.fit(X_train_s, y_train)
    
    # 6. 검증
    y_pred = model.predict(X_val_s)
    mae = mean_absolute_error(y_val, y_pred)
    rmse = np.sqrt(mean_squared_error(y_val, y_pred))
    print(f"  MAE: {mae:.2f}, RMSE: {rmse:.2f}")
    
    # 7. Calibration (Conformal Prediction)
    residuals = np.abs(y_val - y_pred)
    q_090 = float(np.quantile(residuals, 0.90))
    q_095 = float(np.quantile(residuals, 0.95))
    calib_data = {
        "q_090": q_090,
        "q_095": q_095,
        "nonconformity_scores": residuals.tolist(),
    }
    
    # 8. Common calibration (bootstrap용)
    common_calib = {
        "X_fit": pd.DataFrame(X_train_s, columns=feature_cols),
        "y_fit": pd.Series(y_train, name="target"),
        "random_seed": 42,
    }
    
    # 9. valueRatio CSV 생성 (prepare_dataset용)
    rng2 = np.random.RandomState(43)
    difficulties = ['missing', 'A', 'B', 'C', 'D']
    tech_grades = ['missing', '1C', '2C', '3C', '4C']
    diff_freqs = {d: float(np.mean(df['난이도_freq'].iloc[rng2.choice(len(df), 100)])) for d in difficulties}
    tech_freqs = {t: float(np.mean(df['기술등급_freq'].iloc[rng2.choice(len(df), 100)])) for t in tech_grades}
    
    value_ratio_rows = []
    for d in difficulties:
        value_ratio_rows.append({"변수명": "난이도", "범주명": d, "freq": diff_freqs.get(d, 0.2)})
    for t in tech_grades:
        value_ratio_rows.append({"변수명": "기술등급", "범주명": t, "freq": tech_freqs.get(t, 0.2)})
    df_ratio = pd.DataFrame(value_ratio_rows)
    
    # 10. inferenceSet CSV 생성 (prepare_dataset용)
    df_inf = df.copy()
    df_inf['완료확인주'] = df_inf['week']
    df_inf = df_inf[feature_cols + ['정비지시서번호_개수', '완료확인주', 'year', 'week']]
    
    # 11. 저장
    stl_dir = output_dir / stl_num
    stl_dir.mkdir(parents=True, exist_ok=True)
    
    joblib.dump(scaler, stl_dir / f"Simulation_049_{stl_num}_minmax.pickle")
    joblib.dump(model, stl_dir / f"Simulation_049_{stl_num}_{model_name}.pickle")
    
    with open(stl_dir / f"Simulation_049_{stl_num}_{model_name}_calibration.pkl", "wb") as f:
        pickle.dump(calib_data, f)
    
    with open(stl_dir / f"Simulation_049_{stl_num}_common_calibration.pkl", "wb") as f:
        pickle.dump(common_calib, f)
    
    df_ratio.to_csv(stl_dir / f"Simulation_051_valueRatio_{stl_num}.csv", index=False, encoding="utf-8-sig")
    df_inf.to_csv(stl_dir / f"Simulation_051_inferenceSet_{stl_num}.csv", index=False, encoding="utf-8-sig")
    
    # 메타
    meta = {
        "stl_num": stl_num,
        "model_name": model_name,
        "n_samples": len(df),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "q_090": q_090,
        "features": feature_cols,
    }
    with open(stl_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    
    print(f"  Saved to: {stl_dir}")
    return meta


def main():
    output_dir = PROJECT_ROOT / "outputs" / "models_004"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 우선 3개 시험소만 학습 (데모용)
    target_stls = ["시험소008", "시험소010", "시험소012"]
    all_meta = []
    for stl in target_stls:
        meta = train_for_stl(stl, output_dir)
        all_meta.append(meta)
    
    with open(output_dir / "all_meta.json", "w", encoding="utf-8") as f:
        json.dump(all_meta, f, ensure_ascii=False, indent=2)
    
    print("\n=== 004 Training Completed ===")


if __name__ == "__main__":
    main()
