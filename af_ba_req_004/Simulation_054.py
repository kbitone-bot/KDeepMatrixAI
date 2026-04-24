import warnings
warnings.filterwarnings('ignore')

import os
import random
import pandas as pd
import numpy as np
import joblib
import datetime
import pickle
import argparse

from sklearn.base import clone

random_SEED = 42
os.environ["PYTHONHASHSEED"] = str(random_SEED)
random.seed(random_SEED)
np.random.seed(random_SEED)

test_name = 'Simulation_inference'
prj_dir = os.path.dirname(os.path.abspath('__file__'))
model_dir = os.path.join(prj_dir, 'Model', test_name)
result_dir = os.path.join(prj_dir, 'Results', test_name)

# ========================================================================
# prepare_dataset: 전처리
# ========================================================================
def prepare_dataset(stl_num, week_num, var_Difficulty, var_TechGrade, var_Efficiency, var_MaintCycle, var_ConsMH):

    # inference set ---------------------------------------
    df_infSet = pd.read_csv(os.path.join(model_dir, 'Simulation_051_inferenceSet_' + stl_num + '.csv'), encoding='cp949')
    df_inf_week = df_infSet[df_infSet['week'] == week_num]
    if df_inf_week.empty:
        diff = (df_infSet['week'] - week_num).abs()
        nearest_week = df_infSet.loc[diff.idxmin(), 'week']
        print(nearest_week)
        df_inf_week = df_infSet[df_infSet['week'] == nearest_week]

    df_inf_week.drop(['정비지시서번호_개수', '완료확인주', 'year', 'week'], axis=1, inplace=True)

    # print(df_inf_week)
    # print(df_inf_week.columns)
    # ['정비지시서번호_개수', '정비주기', '시작온도', '완료온도', '시작습도', '완료습도', '작업일수', '소모인시',
    #    '효율(%)', '난이도_freq', '기술등급_freq', '요일번호', '완료확인주', '계절', 'year',
    #    'week']

    cols_check = df_inf_week.columns.difference(['요일번호', '계절'])
    mask = (df_inf_week[cols_check] == 0).all(axis=1)
    zero_weekdays = df_inf_week.loc[mask, '요일번호'].tolist()
    # print(zero_weekdays)

    # --------------------------------------------- 조정변수
    df_inf_week['효율(%)'] = var_Efficiency
    df_inf_week['정비주기'] = var_MaintCycle
    df_inf_week['소모인시'] = var_ConsMH

    # --------------------------------------------- 조정변수: 난이도/기술등급 valueRatio 
    try: 
        df_ratio = pd.read_csv(os.path.join(model_dir, 'Simulation_051_valueRatio_' + stl_num + '.csv'), encoding='cp949')
        # print(df_ratio)

        # 난이도 freq 추출
        diff_freq = df_ratio.loc[(df_ratio['변수명'] == '난이도') & (df_ratio['범주명'] == var_Difficulty), 'freq'].iloc[0]
        # 기술등급 freq 추출
        tech_freq = df_ratio.loc[(df_ratio['변수명'] == '기술등급') & (df_ratio['범주명'] == var_TechGrade), 'freq'].iloc[0]
        # df_inf_week 전체를 해당 값으로 채우기
        df_inf_week['난이도_freq'] = diff_freq
        df_inf_week['기술등급_freq'] = tech_freq

    except Exception as e:
        
        # Fallback: stl_num을 시험소008로 고정
        fallback_stl = '시험소008'
        df_ratio = pd.read_csv(os.path.join(model_dir, 'Simulation_051_valueRatio_' + fallback_stl + '.csv'), encoding='cp949')

        diff_freq = df_ratio.loc[(df_ratio['변수명'] == '난이도') & (df_ratio['범주명'] == var_Difficulty), 'freq'].iloc[0]
        tech_freq = df_ratio.loc[(df_ratio['변수명'] == '기술등급') & (df_ratio['범주명'] == var_TechGrade), 'freq'].iloc[0]
        df_inf_week['난이도_freq'] = diff_freq
        df_inf_week['기술등급_freq'] = tech_freq

    
    # --------------------------------------------- zero_weekdays 행은 나머지 컬럼 0으로
    cols_to_zero = df_inf_week.columns.difference(['요일번호', '계절'])
    if zero_weekdays:  # 리스트가 비어있지 않을 때만 실행
        df_inf_week.loc[df_inf_week['요일번호'].isin(zero_weekdays), cols_to_zero] = 0

    return df_inf_week


# ========================================================================
# bootstrap_confidence_interval_single: 신뢰구간
# ========================================================================
def bootstrap_confidence_interval_single(base_estimator, X_train, y_train, X_new, 
                                        B=200, conf=0.90, random_state=42):
    """
    단일 샘플에 대한 부트스트랩 신뢰구간 계산
    학습된 모델을 기반으로 부트스트랩 리샘플링하여 신뢰구간 추정
    
    Returns:
    --------
    mean_pred : float (부트스트랩 평균 예측값)
    ci_lower : float (신뢰구간 하한)
    ci_upper : float (신뢰구간 상한)
    """
    rng = np.random.RandomState(random_state)
    n = len(X_train)
    preds = []
    
    # 부트스트랩 반복
    for b in range(B):
        # 복원추출
        idx = rng.randint(0, n, n)
        Xb = X_train.iloc[idx] if hasattr(X_train, "iloc") else X_train[idx]
        yb = y_train.iloc[idx] if hasattr(y_train, "iloc") else y_train[idx]
        
        # 모델 복제 및 재학습
        model_b = clone(base_estimator)
        model_b.fit(Xb, yb)
        
        # 주별 샘플
        pred_daily = model_b.predict(X_new)     # shape (7,)
        pred_week  = float(np.sum(pred_daily))       # 주단위 합
        preds.append(pred_week)
    
    preds = np.array(preds)
    
    # 신뢰구간 계산 (Percentile Method)
    alpha = 1 - conf
    ci_lower = float(np.percentile(preds, 100 * (alpha / 2)))
    ci_upper = float(np.percentile(preds, 100 * (1 - alpha / 2)))
    mean_pred = float(preds.mean())
    
    return mean_pred, ci_lower, ci_upper


# ========================================================================
# inference_single_sample: 추론
# ========================================================================
def inference_single_sample(stl_num, model_name, X_new):

    alpha=0.10 # alpha : 예측구간 오류율    
    conf  = 0.90  # 신뢰구간 수준
    B=200

    # 1. 스케일러 로드 및 적용
    scalerX_path = os.path.join(model_dir, f'Simulation_049_{stl_num}_minmax.pickle')
    scalerX = joblib.load(scalerX_path)
    
    # X_new 형태 변환 및 스케일링
    if isinstance(X_new, pd.Series):
        X_new_scaled = scalerX.transform(X_new.values.reshape(1, -1))
    elif isinstance(X_new, pd.DataFrame):
        X_new_scaled = scalerX.transform(X_new.values)   # 7×p 그대로
    else:
        X_new_scaled = scalerX.transform(X_new.reshape(1, -1))
    
    # 2. 모델 로드
    model_path = os.path.join(model_dir, f'Simulation_049_{stl_num}_{model_name}.pickle')
    model = joblib.load(model_path)
    
    # 3. 보정 데이터 로드
    calib_path = os.path.join(model_dir, f'Simulation_049_{stl_num}_{model_name}_calibration.pkl')
    with open(calib_path, 'rb') as f:
        calib_data = pickle.load(f)
    
    # 4. 예측 및 예측구간 계산
    if alpha == 0.10:
        q = calib_data['q_090']
    elif alpha == 0.05:
        q = calib_data['q_095']
    else:
        q = np.quantile(calib_data['nonconformity_scores'], 1 - alpha)

    # ---- (1) 일별 예측 → 주간 합, 예측구간(PI) ----
    yhat_daily = model.predict(X_new_scaled)          # (7,)
    yhat_week  = yhat_daily.sum()
    pi_lower   = yhat_week - q
    pi_upper   = yhat_week + q

    # ---- (2) 부트스트랩 신뢰구간(CI) 추가 ----
    ci_lower = None
    ci_upper = None
    bootstrap_mean = None
        
    # 공통 보정셋 로드
    common_calib_path = os.path.join(model_dir, f'Simulation_049_{stl_num}_common_calibration.pkl')
    if not os.path.exists(common_calib_path):
        print("공통 보정셋을 찾을 수 없습니다. 신뢰구간 계산을 건너뜁니다.")
        compute_ci = False
    else:
        with open(common_calib_path, 'rb') as f:
            common_calib = pickle.load(f)
        
        X_fit = common_calib['X_fit']
        y_fit = common_calib['y_fit']
        random_seed = common_calib.get('random_seed', 42)
        
        # 부트스트랩 신뢰구간 계산
        bootstrap_mean, ci_lower, ci_upper = bootstrap_confidence_interval_single(
            model, X_fit, y_fit, X_new_scaled, B=B, conf=conf, random_state=random_seed
        ) # X_new_scaled

    # 음수 값은 0으로 보정 ---------------------------------
    pi_lower = max(pi_lower, 0)
    pi_upper = max(pi_upper, 0)

    if ci_lower is not None:
        ci_lower = max(ci_lower, 0)
    if ci_upper is not None:
        ci_upper = max(ci_upper, 0)

    result = {
        'stl_num': stl_num,
        'model_name': model_name,
        'y_pred': int(np.rint(yhat_week)),
        'pi_lower': int(np.rint(pi_lower)),
        'pi_upper': int(np.rint(pi_upper)),
        # 'alpha': alpha,
        # 'q': float(q),
        'ci_lower': int(np.rint(ci_lower)),
        'ci_upper': int(np.rint(ci_upper)),
    }
    
    return result


# ========================================================================
# main
# ========================================================================
def main():
    
    # ArgumentParser 생성
    parser = argparse.ArgumentParser(
        description='시험소 예측 모델 실행',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 필수 및 선택적 인자 추가
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
        '--difficulty',
        type=str,
        default='A',
        choices=['missing', 'A', 'B', 'C', 'D'],
        help='난이도 (기본값: A)'
    )
    
    parser.add_argument(
        '--tech_grade',
        type=str,
        default='2C',
        choices=['missing', '1C', '2C', '3C', '4C'],
        help='기술등급 (기본값: 2C)'
    )
    
    parser.add_argument(
        '--efficiency',
        type=int,
        default=80,
        help='효율(%%) (기본값: 80)'
    )
    
    parser.add_argument(
        '--maint_cycle',
        type=int,
        default=12,
        help='정비주기 (기본값: 12)'
    )
    
    parser.add_argument(
        '--cons_mh',
        type=int,
        default=100,
        help='소모인시 (기본값: 100)'
    )
    
    # 인자 파싱
    args = parser.parse_args()


    # 시험소 및 예측시점 정보 ---------------------------------------
    # stl_num = '시험소008'
    week_num = int(datetime.datetime.now().strftime('%U')) # 연 기준 주 번호 (0~53)
    # print(stl_num, week_num)
    
    # # 조정 변수 ---------------------------------------
    # var_Difficulty = 'A' # '난이도': ['missing', 'A', 'B', 'C', 'D']
    # var_TechGrade = '2C' # '기술등급': ['missing', '1C', '2C', '3C', '4C']
    # var_Efficiency = 80 # '효율(%)'
    # var_MaintCycle = 12 # '정비주기'
    # var_ConsMH = 100 # '소모인시'

    # inference set 준비 ---------------------------------------
    df_inf_week = prepare_dataset(
        args.stl_num, 
        week_num, 
        args.difficulty, 
        args.tech_grade, 
        args.efficiency, 
        args.maint_cycle, 
        args.cons_mh)
    

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

    result_single = inference_single_sample(args.stl_num, best_model_dict[args.stl_num], df_inf_week)
    print(result_single)


# ========================================================================
# __main__
# ========================================================================
if __name__ == "__main__":
    main()


# python Simulation_054.py --stl_num 시험소008 --difficulty B --tech_grade 3C --efficiency 85 --maint_cycle 15 --cons_mh 120

