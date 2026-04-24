import warnings
warnings.filterwarnings('ignore')

import os
import random
import numpy as np
import pandas as pd
import joblib
from scipy.optimize import differential_evolution
import datetime
import argparse

random_SEED = 42
os.environ["PYTHONHASHSEED"] = str(random_SEED)
random.seed(random_SEED)
np.random.seed(random_SEED)

test_name = 'Simulation_inference'
prj_dir = os.path.dirname(os.path.abspath('__file__'))
model_dir = os.path.join(prj_dir, 'Model', test_name)


# ========================================================================
# Inverse_Estimation: 역추정
# ========================================================================
def Inverse_Estimation(stl_num, week_num, y_target, model_name):
    """
    주간 목표 작업량(y_target)을 달성하기 위한 최적 변수 조합 역추정
    
    최적화 대상: 효율(%), 정비주기, 소모인시, 난이도_freq, 기술등급_freq
    고정 변수: 시작온도, 완료온도, 시작습도, 완료습도, 작업일수, 요일번호, 계절
    """
    
    # 모델 및 스케일러 로드
    scalerX_dir = os.path.join(model_dir, f'Simulation_049_{stl_num}_minmax.pickle')
    scaler = joblib.load(scalerX_dir)

    trained_model_dir = os.path.join(model_dir, f'Simulation_049_{stl_num}_{model_name}.pickle')
    model = joblib.load(trained_model_dir)

    # valueRatio (freq_mappings) 로드
    try:
        df_ratio = pd.read_csv(os.path.join(model_dir, f'Simulation_051_valueRatio_{stl_num}.csv'), encoding='cp949')
    except:
        df_ratio = pd.read_csv(os.path.join(model_dir, 'Simulation_051_valueRatio_시험소008.csv'), encoding='cp949')
    
    # 난이도와 기술등급의 범주별 freq 추출
    freq_mappings = {}
    for var_name in ['난이도', '기술등급']:
        var_data = df_ratio[df_ratio['변수명'] == var_name]
        freq_mappings[var_name] = dict(zip(var_data['범주명'], var_data['freq']))

    # Feature names 정의
    feature_names = ['정비주기', '시작온도', '완료온도', '시작습도', '완료습도', '작업일수', '소모인시',
                     '효율(%)', '난이도_freq', '기술등급_freq', '요일번호', '계절']
    
    total_dim = len(feature_names)
    name_to_idx = {name: i for i, name in enumerate(feature_names)}

    # 베이스라인 데이터 로드
    df_infSet = pd.read_csv(os.path.join(model_dir, f'Simulation_051_inferenceSet_{stl_num}.csv'), encoding='cp949')
    df_inf_week = df_infSet[df_infSet['week'] == week_num]
    if df_inf_week.empty:
        diff = (df_infSet['week'] - week_num).abs()
        nearest_week = df_infSet.loc[diff.idxmin(), 'week']
        df_inf_week = df_infSet[df_infSet['week'] == nearest_week]
    
    df_inf_week.drop(['정비지시서번호_개수', '완료확인주', 'year', 'week'], axis=1, inplace=True)
    
    # zero_weekdays 파악
    cols_check = df_inf_week.columns.difference(['요일번호', '계절'])
    mask = (df_inf_week[cols_check] == 0).all(axis=1)
    zero_weekdays = df_inf_week.loc[mask, '요일번호'].tolist()

    # 고정 변수 - 베이스라인에서 가져옴
    # 시작온도, 완료온도, 시작습도, 완료습도, 작업일수는 베이스라인 데이터 사용
    baseline_fixed = {}
    for var in ['시작온도', '완료온도', '시작습도', '완료습도', '작업일수']:
        baseline_fixed[var] = df_inf_week[var].values  # (7,) array
    
    weekday_values = df_inf_week['요일번호'].values  # (7,)
    season_values = df_inf_week['계절'].values        # (7,)

    # 최적화 대상 변수만 정의 (연속형 3개)
    cont_bounds = {
        "정비주기": (3, 60),
        "소모인시": (10, 400),
        "효율(%)": (10, 100),
    }

    # 최적화 대상 변수만 정의 (범주형 2개)
    freq_bounds = {
        "기술등급_freq": (
            min(freq_mappings['기술등급'].values()), 
            max(freq_mappings['기술등급'].values())
        ),
        "난이도_freq": (
            min(freq_mappings['난이도'].values()), 
            max(freq_mappings['난이도'].values())
        ),
    }

    all_bounds = {**cont_bounds, **freq_bounds}
    free_names = list(all_bounds.keys())
    bounds_free = [all_bounds[n] for n in free_names]

    # print(f"\n전체 특징 변수 개수: {total_dim}")
    # print(f"최적화 변수 개수: {len(free_names)}")
    # print(f"최적화 변수: {free_names}")
    # print(f"고정 변수: ['시작온도', '완료온도', '시작습도', '완료습도', '작업일수', '요일번호', '계절']")
    # print(f"Zero weekdays (작업 없는 요일): {zero_weekdays}")

    # 목적 함수 - 고정 변수는 베이스라인 값 사용
    def objective(x_free):
        # 7개 요일에 대한 입력 생성
        X_week = np.zeros((7, total_dim))
        
        for day_idx in range(7):
            weekday = weekday_values[day_idx]
            season = season_values[day_idx]
            
            # zero_weekdays에 해당하는 요일은 모든 값을 0으로
            if weekday in zero_weekdays:
                X_week[day_idx, :] = 0
                X_week[day_idx, name_to_idx['요일번호']] = weekday
                X_week[day_idx, name_to_idx['계절']] = season
            else:
                # 최적화 변수 할당
                for i, var_name in enumerate(free_names):
                    X_week[day_idx, name_to_idx[var_name]] = x_free[i]
                
                # 고정 변수 할당 (베이스라인 값)
                for var_name, values in baseline_fixed.items():
                    X_week[day_idx, name_to_idx[var_name]] = values[day_idx]
                
                # 요일번호, 계절 할당
                X_week[day_idx, name_to_idx['요일번호']] = weekday
                X_week[day_idx, name_to_idx['계절']] = season
        
        # 스케일링 및 예측
        X_week_scaled = scaler.transform(X_week)
        y_pred_daily = model.predict(X_week_scaled)  # (7,)
        y_pred_week = y_pred_daily.sum()
        
        return (y_pred_week - y_target) ** 2

    # 최적화 실행
    result = differential_evolution(
        objective,
        bounds=bounds_free,
        seed=42,
        maxiter=500,
        popsize=15,
        atol=1e-4,
        tol=1e-4,
        disp=False
    )

    # print(f"\n=== 최적화 결과 ===")
    # print(f"목표 y값 (주간 합계): {y_target}")
    # print(f"최종 손실: {result.fun:.6f}")

    # 최적 입력 변수 출력 (연속형)
    print(f"\n최적 입력 변수 (연속형)")
    # for var_name in cont_bounds.keys():
    #     idx = free_names.index(var_name)
    #     print(f"{var_name:15s}: {result.x[idx]:8.1f}")
    
    for var_name in cont_bounds.keys():
        idx = free_names.index(var_name)
        value = result.x[idx]
        
        # 변수별 출력 형식 지정
        if var_name in ["정비주기", "소모인시"]:
            # 정수로 반올림하여 표시
            print(f"{var_name:15s}: {int(round(value)):8d}")
        elif var_name == "효율(%)":
            # 소수점 둘째 자리까지 표시
            print(f"{var_name:15s}: {value:8.2f}")
        else:
            # 기본 형식
            print(f"{var_name:15s}: {value:8.4f}")

    # 최적 입력 변수 출력 (범주형)
    print(f"\n최적 입력 변수 (범주형)")
    for var_name in ['기술등급', '난이도']:
        freq_col = f"{var_name}_freq"
        idx = free_names.index(freq_col)
        freq_value = result.x[idx]
        
        # 가장 가까운 범주 찾기
        category = min(freq_mappings[var_name].keys(), 
                      key=lambda k: abs(freq_mappings[var_name][k] - freq_value))
        actual_freq = freq_mappings[var_name][category]
        # print(f"{var_name}: 최적화 값: {freq_value:.4f} → 범주: {category} (실제 freq: {actual_freq:.4f})")
        print(f"{var_name}: 최적화 값 범주: {category}")


    # # 고정 변수 출력
    # print(f"\n고정 변수 (베이스라인 평균값)")
    # for var_name, values in baseline_fixed.items():
    #     # zero_weekdays를 제외한 평균
    #     non_zero_values = [values[i] for i in range(7) if weekday_values[i] not in zero_weekdays]
    #     if non_zero_values:
    #         avg_val = np.mean(non_zero_values)
    #         print(f"{var_name:15s}: {avg_val:8.4f}")

    return y_target, result, feature_names, free_names, scaler, model, weekday_values, season_values, zero_weekdays, baseline_fixed


# ========================================================================
# main
# ========================================================================
def main():

    
    parser = argparse.ArgumentParser(
        description='시험소 역추정 최적화 도구 - 목표 작업량을 달성하기 위한 최적 입력 변수 계산',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
        
    # 필수 인자
    parser.add_argument(
        '--stl_num',
        type=str,
        required=True,
        choices=['시험소002', '시험소003', '시험소004', '시험소005', 
                 '시험소006', '시험소007', '시험소008', '시험소009',
                 '시험소010', '시험소011', '시험소012', '시험소014'],
        help='시험소 번호 (예: 시험소008)'
    )
    
    parser.add_argument(
        '--y_target',
        type=int,
        required=True,
        help='주간 목표 작업량 (예: 100)'
    )

    args = parser.parse_args()
    
    best_model_dict = {
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
    
    # stl_num = '시험소008'
    week_num = int(datetime.datetime.now().strftime('%U'))
    # y_target = 100  # 주간 목표 작업량
    model_name = best_model_dict[args.stl_num]

    y_target, result, feature_names, free_names, scaler, model, weekday_values, season_values, zero_weekdays, baseline_fixed = \
        Inverse_Estimation(args.stl_num, week_num, args.y_target, model_name)

    # 검증    
    total_dim = len(feature_names)
    name_to_idx = {name: i for i, name in enumerate(feature_names)}
    X_week_opt = np.zeros((7, total_dim))
    
    for day_idx in range(7):
        weekday = weekday_values[day_idx]
        season = season_values[day_idx]
        
        if weekday in zero_weekdays:
            X_week_opt[day_idx, :] = 0
            X_week_opt[day_idx, name_to_idx['요일번호']] = weekday
            X_week_opt[day_idx, name_to_idx['계절']] = season
        else:
            # 최적화 변수
            for i, var_name in enumerate(free_names):
                X_week_opt[day_idx, name_to_idx[var_name]] = result.x[i]
            
            # 고정 변수
            for var_name, values in baseline_fixed.items():
                X_week_opt[day_idx, name_to_idx[var_name]] = values[day_idx]
            
            X_week_opt[day_idx, name_to_idx['요일번호']] = weekday
            X_week_opt[day_idx, name_to_idx['계절']] = season
    
    # 예측
    X_week_opt_scaled = scaler.transform(X_week_opt)
    y_pred_daily = model.predict(X_week_opt_scaled)
    y_pred_week = y_pred_daily.sum()
    
    # print(f"일별 예측값: {y_pred_daily}")
    # print(f"주간 예측값 (합계): {y_pred_week:.4f}")
    # print(f"목표값: {y_target}")
    # print(f"절대 오차: {abs(y_pred_week - y_target):.4f}")
    # print(f"상대 오차: {abs(y_pred_week - y_target) / y_target * 100:.2f}%")



# ========================================================================
# __main__
# ========================================================================
if __name__ == "__main__":
    main()


# python Simulation_055.py --stl_num 시험소008 --y_target 160