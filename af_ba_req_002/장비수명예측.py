import pandas as pd
import argparse
from tqdm import tqdm
import uuid
import numpy as np
from math import floor

# 신뢰성 분석 라이브러리
from scipy.stats import norm, expon, weibull_min
from fitter import Fitter

# 시각화 라이브러리
import matplotlib.pyplot as plt

# 한글 폰트 설정
try:
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False # 마이너스 폰트 깨짐 방지
except Exception as e:
    print(f"한글 폰트(맑은 고딕) 설정 실패: {e}. (그래프의 한글이 깨질 수 있습니다)")
    pass

# 0. 데이터 로드
def load_data(file_path='data/정밀측정폐품현황_날짜변환_코드화_부품번호추가.xlsb'):
    """
    데이터 소스(현재 Excel)에서 데이터를 로드하고 날짜 변환 수행
    """
    def convert_mixed_dates(column_series):
        numeric_dates = pd.to_numeric(column_series, errors='coerce')
        converted_from_numeric = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30')
        
        # 2. 문자열(표준 날짜) 변환 시도
        # errors='coerce'는 숫자를 NaT(NaN)로 만듭니다.
        converted_from_string = pd.to_datetime(column_series, errors='coerce')
        
        # 3. 1번 결과(숫자 변환)를 2번 결과(문자열 변환)로 채움
        #    (1번이 NaT이면 2번 값을, 1번이 값이 있으면 1번 값을 사용)
        return converted_from_numeric.fillna(converted_from_string)

    try:
        df = pd.read_excel(file_path, dtype={'acqdt': object, 'aprv_prcss_dttm': object}, engine='pyxlsb')
        df['acqdt'] = convert_mixed_dates(df['acqdt'])
        df['aprv_prcss_dttm'] = convert_mixed_dates(df['aprv_prcss_dttm'])
                    
        print(f"데이터 로드 완료. 총 {len(df)} 행.")
        return df
    
    except FileNotFoundError:
        print(f"오류: {file_path} 파일을 찾을 수 없습니다.")
        return pd.DataFrame()
    except Exception as e:
        print(f"데이터 로드 중 오류 발생: {e}")
        return pd.DataFrame()

# 1. 데이터 전처리 및 필터링
def preprocess_data(df, no_pn):
    """
    데이터를 전처리하고, event_status 컬럼을 생성
    """
    if no_pn:
        df_processed = df[df['pn'] == no_pn].copy()
    else:
        df_processed = df.copy()

    if df_processed.empty:
        return pd.DataFrame(), [], 0
    else:
        df_processed = df_processed.sort_values(by=['pn', 'acqdt']).reset_index(drop=True)

        print(f"필터링 완료. 분석 대상 {len(df_processed)} 행.")
        return df_processed

# 1. 데이터 전처리 및 필터링
def create_use_data(df, no_pn):
    """
    사용기간 계산 및 년단위 변환, 전처리 진행
    """
    try:
        df_processed = df[df['pn'] == no_pn].copy()

        # 최초 데이터 건수
        total_values = len(df_processed)

        # 데이터 처리
        df_processed.loc[df['pn'] == no_pn, 'use_date'] = (df_processed['aprv_prcss_dttm'] - df_processed['acqdt']) / pd.Timedelta(days=1)

        # 같은 날 사용 및 종료 또는 음수 기간 제거
        df_processed = df_processed[df_processed['use_date'] > 0.0]

        df_processed['use_year'] = round(df_processed['use_date'] / 365, 3)

        df_processed = df_processed.sort_values(by='acqdt').reset_index(drop=True)

        durations = df_processed['use_year'].tolist()
        
        return durations, total_values
    except Exception as e:
        print(f"사용기간 계산 실패했습니다. : {e}")
        return

# 3. 분포 비교 및 최적 분포 선정
def find_best_distribution(durations):
    """
    장비 사용 기간을 사용해 3개의 분포를 비교하고 최적 분포 선정
    """
    if not durations or len(durations) < 2:
        print("분포 fit을 위한 데이터가 부족합니다.")
        return None, "No Data", None
    
    models = ["norm", "expon", "weibull_min"]

    fin_dist = Fitter(durations, distributions=models)
    fin_dist.fit()

    summary_df = fin_dist.summary()  # 내부적으로 summary()가 이걸 출력함

    #best_dist = list(fin_dist.get_best(method='aic').keys())[0]
    best_dist = list(fin_dist.get_best().keys())[0]
    best_params = fin_dist.fitted_param[best_dist]
    best_pvalue = summary_df.loc[best_dist, 'ks_pvalue']

    if best_dist is None: return None, "Fit Fail"
    return best_dist, best_params, best_pvalue

# 3.1. 모델 파라메터 형식 변환
def trans_parameter_format(model, params):
    """
    모델 타입에 따라 파라메터 형식을 변환하여 반환 (확인용)
    """        
    if model == 'norm':
        mu, sigma = params
        param_str = f"μ={mu:.3f}, σ={sigma:.2f}"
    elif model == 'expon':
        loc, scale = params
        param_str = f"a={loc:.3f}, b={scale:.3f}"
    elif model == 'weibull_min':
        c, loc, scale = params
        param_str = f"c={c:.3f}, a={loc:.3f}, b={scale:.3f}"

    return param_str.strip("'\"").strip("'\'")

# 3. 지표 계산
def calculate_metrics(best_dist, best_params):
    """
    최적 분포 모델을 사용해 점 추정치, 장비 수명을 계산
    """
    if not best_dist:
        print("최적 분포가 없습니다.")
        return {}

    # 분포 모형의 파라메터 형식 변환
    param_str = trans_parameter_format(best_dist, best_params)

    dist_map = {'norm': norm, 'expon': expon, 'weibull_min': weibull_min}
    dist_name = dist_map[best_dist]

    # 점 추정치 계산
    expected_lifetime = dist_name.mean(*best_params)
    # 장비 수명 계산
    lifetime_10p = dist_name.ppf(0.1, *best_params)
    lifetime_50p = dist_name.ppf(0.5, *best_params)
            
    return {
        'expected_lifetime': round(expected_lifetime, 3),
        'lifetime_10p': round(lifetime_10p, 3),
        'lifetime_50p': round(lifetime_50p, 3)
    }

# 4. 시각화 데이터 생성
def create_visualization_data(durations, best_dist, best_params, metrics):
    """
    점 추정치, B10 수명, B50 수명에 대한 시각화 구성을 위한 데이터 생성
    """
    dist_map = {'norm': norm, 'expon': expon, 'weibull_min': weibull_min}
    dist_name = dist_map[best_dist]

    # x축 값
    t = np.arange(floor(max(durations)) + 1)

    # 각 함수 계산
    cdf = dist_name.cdf(t, *best_params)
    pdf = dist_name.pdf(t, *best_params)
        
    df_viz = pd.DataFrame({'time': t, 'cdf': cdf, 'pdf': pdf, **metrics})

    return df_viz

# 5. 시각화 플롯 생성
# 5.1. 점추정치 시각화 플롯 생성
def create_parameter_estimates_data(df_visualization, best_dist, save_filename="parameter_estimates.png"):
    """
    df_visualization을 사용해 점추정치 플롯 생성
    """
    try:
        years = df_visualization['time'].tolist()
        pdf = df_visualization['pdf'].tolist()
        mean_val = df_visualization['expected_lifetime'].unique()[0]

        plt.figure(figsize=(8, 5))
        plt.plot(years, pdf, color='blue')
        plt.axvline(mean_val, color='red', linestyle='--', label=f'점 추정치 (Mean): ({mean_val})')
        plt.title(f'{best_dist} 분포 - 점 추정치')
        plt.xlabel('사용 연도')
        plt.ylabel('확률 밀도')
        plt.legend()
        plt.grid(True)

        # 저장
        plt.savefig(save_filename, dpi=150, bbox_inches='tight')
        plt.close()

        # print(f"점추정치 플롯 저장 완료: {save_filename}")

    except Exception as e:
        print(f"점추정치 플롯 생성 실패: {e}")

# 5.2. B10/B50 수명 시각화 플롯 생성
def create_lifetime_data(df_visualization, best_dist, mode=10, save_filename="parameter_estimates.png"):
    """
    df_visualization을 사용해 B10/B50수명 플롯 생성
    """
    try:
        years = df_visualization['time'].tolist()
        cdf = df_visualization['cdf'].tolist()

        plt.figure(figsize=(8, 5))
        plt.plot(years, cdf, color='blue')
        if mode == 10:
            b10 = df_visualization['lifetime_10p'].unique()[0]
            plt.axvline(b10, color='orange', linestyle='--', label=f'B{mode} life: {b10:.2f}')
            plt.title(f'{best_dist} dist - B{mode} life ')
        else:
            b50 = df_visualization['lifetime_50p'].unique()[0]
            plt.axvline(b50, color='orange', linestyle='--', label=f'B{mode} life: {b50:.2f}')
            plt.title(f'{best_dist} dist - B{mode} life ')   

        plt.xlabel('사용 연도')
        plt.ylabel('누적 고장 확률')
        plt.legend()
        plt.grid(True)

        # 저장
        plt.savefig(save_filename, dpi=150, bbox_inches='tight')
        plt.close()

        # print(f"B{mode}수명 플롯 저장 완료: {save_filename}")

    except Exception as e:
        print(f"B{mode}수명 플롯 생성 실패: {e}")

# 메인 실행 함수
def analyze_life(no_pn):
    
    # 단계 0: 데이터 로드
    try:
        df_raw = load_data()
    except Exception as e:
        print(f"데이터 로드 실패: {e}")
        print("관련 조건의 데이터가 조회되지 않습니다.")
        return

    # 단계 1: 데이터 전처리
    try:
        df_processed = preprocess_data(df_raw, no_pn)
    except Exception as e:
        print(f"데이터 전처리 중 오류 발생: {e}")
        return
    
    if df_processed.empty:
        print(f"분석 중단: 해당 장비({no_pn})는 유효한 정보가 없습니다.")
        return

    try:
        analysis_id = str(uuid.uuid4())
        print('analysis_id : ', analysis_id)

        pn_no_list = df_processed.loc[:, 'pn'].unique().tolist()[:10]

        df_summarys = pd.DataFrame()
        df_visualizations = pd.DataFrame()

        for pn_no_loop in tqdm(pn_no_list, desc="부품번호"):

            durations, total_values = create_use_data(df_processed, pn_no_loop)

            # 단계 2: 최적 분포 모형 선정
            print(f"== 모수적 기반 최적 분포 선정 ==")
            best_dist, best_params, best_pvalue = find_best_distribution(durations)

            # 단계 3: 점추정치, 장비 수명 예측 결과 계산
            print(f"== 장비 수명 분석 ==")
            metrics = calculate_metrics(best_dist, best_params)
            summary_data = {'analysis_id': [analysis_id], 'pn': [no_pn if no_pn else pn_no_loop], **metrics, 'oper_life': [0],  'best_dist' : [best_dist], 'p_value': [best_pvalue]}
            df_summary_data = pd.DataFrame(summary_data)
            
            df_summarys = pd.concat([df_summarys, df_summary_data])

            if no_pn:
                # 단계 4: 시각화 데이터 생성
                df_visualization_data = create_visualization_data(durations, best_dist, best_params, metrics)
                df_visualization_data['analysis_id'] = analysis_id
                df_visualization_data['pn'] = pn_no_loop

                df_visualization_data = df_visualization_data[['analysis_id', 'pn', 'time', 'cdf', 'pdf', 'expected_lifetime', 'lifetime_10p', 'lifetime_50p']]

                df_visualizations = pd.concat([df_visualizations, df_visualization_data])

                create_parameter_estimates_data(df_visualization_data, best_dist, f"result/2.점추정치 시각화 결과_{no_pn}.png")
                create_lifetime_data(df_visualization_data, best_dist, mode=10, save_filename=f"result/2.B10수명 시각화 결과_{no_pn}.png")
                create_lifetime_data(df_visualization_data, best_dist, mode=50, save_filename=f"result/2.B50수명 시각화 결과_{no_pn}.png")

        # 단계 5: 데이터 저장
        summary_filename = f"result/2.usage_summary_{no_pn}.csv"
        viz_filename = f"result/2.usage_viz_data_{no_pn}.csv"

        print('== 수명 예측 결과 ==')
        print(df_summarys.head(5))

        print('== 시각화 데이터 추출 결과 ==')
        print(df_visualizations.head(5))
        
        df_summarys.to_csv(summary_filename, index=False, encoding='utf-8-sig')
        df_visualizations.to_csv(viz_filename, index=False, encoding='utf-8-sig')
    except Exception as e:
        print(f"수명 예측 추출에 실패했습니다. (분석 단계 오류): {e}")
        return

# 스크립트 실행 (argparse)
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="장비 수명 예측")
    # parser.add_argument("--no_pn", type=str, default='부품번호01217', help="부품번호")
    parser.add_argument("--no_pn", type=str, default='', help="부품번호")
    args = parser.parse_args()

    try:
        analyze_life(
            no_pn=args.no_pn
        )
    except Exception as e:
        print(f"분석 중 치명적인 오류 발생: {e}")