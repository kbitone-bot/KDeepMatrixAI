import pandas as pd
import argparse
from tqdm import tqdm
import uuid
import numpy as np
import warnings

# 시각화 라이브러리
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 신뢰성 분석 라이브러리
from scipy.special import gamma

# 신뢰성 분석 라이브러리
from lifelines import WeibullFitter, ExponentialFitter, LogNormalFitter

# 한글 폰트 설정
try:
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False # 마이너스 폰트 깨짐 방지
except Exception as e:
    print(f"한글 폰트(맑은 고딕) 설정 실패: {e}. (그래프의 한글이 깨질 수 있습니다)")
    pass

# 0. 데이터 로드
def load_data(file_path='data/가용도분석자료.xlsb'):
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
        df = pd.read_excel(file_path, dtype={'mntnc_reqstdt': object, 'rels_dhm': object}, engine='pyxlsb')
        df['mntnc_reqstdt'] = convert_mixed_dates(df['mntnc_reqstdt'])
        df['rels_dhm'] = convert_mixed_dates(df['rels_dhm'])

        # data, column_list = select_fetch_data('ROC_EQ_USAGE_TB')  # 데이터를 조회하는 함수 호출
        # df = pd.DataFrame(data=data, columns=column_list)
        
        if 'mntnc_rslt_actn_cd' in df.columns:
            df['mntnc_rslt_actn_cd'] = df['mntnc_rslt_actn_cd'].astype(str)
            
        print(f"데이터 로드 완료. 총 {len(df)} 행.")
        return df
    
    except FileNotFoundError:
        print(f"오류: {file_path} 파일을 찾을 수 없습니다.")
        return pd.DataFrame()
    except Exception as e:
        print(f"데이터 로드 중 오류 발생: {e}")
        return pd.DataFrame()

# 1. 데이터 전처리 및 필터링
def preprocess_data(df, no_pn, no_pclrt_idno, mode, start_date, end_date):
    """
    로드한 데이터를 대상으로 조치 코드 상태 변환 및 조건에 따른 데이터 조회
    """
    if df.empty:
        return pd.DataFrame()

    # 조치 코드 변환
    code_map = {'C': 'J', 'H': 'J', 'S': 'J', 'L': 'K'}

    df_processed = df.copy()
    df_processed['mntnc_rslt_actn_cd'] = df_processed['mntnc_rslt_actn_cd'].astype(str).replace(code_map)
    
    # 4개의 조치 코드 상태만 조회 
    valid_codes = ['F', 'G', 'J', 'K']
    df_processed = df_processed[df_processed['mntnc_rslt_actn_cd'].isin(valid_codes)]

    df_processed['mntnc_reqstdt'] = pd.to_datetime(df_processed['mntnc_reqstdt'])
    df_processed['rels_dhm'] = pd.to_datetime(df_processed['rels_dhm'])

    # 날짜 형식 변환 및 조건에 따른 데이터 조회
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    if no_pn and no_pclrt_idno:  # 둘 다 있는 경우
        df_processed = df_processed[(df_processed['pn'] == no_pn) & (df_processed['pclrt_idno'] == no_pclrt_idno)]
    elif no_pn:  # 부품번호만 있는 경우
        df_processed = df_processed[df_processed['pn'] == no_pn]
    elif no_pclrt_idno:  # 고유식별번호만 있는 경우
        df_processed = df_processed[df_processed['pclrt_idno'] == no_pclrt_idno]

    # 날짜 필터 (의뢰일자 < end) AND ( (출고일자 > start) OR (출고일자 is NaT) )
    df_processed = df_processed[
        ( df_processed['mntnc_reqstdt'] < end_date ) &
        ( (df_processed['rels_dhm'] > start_date) | (pd.isna(df_processed['rels_dhm'])) )
    ]
    
    # 가동/비가동 정보 event_status 컬럼 생성
    def assign_status(row):
        code = row['mntnc_rslt_actn_cd']
        if mode == '수리':
            return '가동' if code == 'J' else '비가동' # J만 가동, 나머지 비가동
        elif mode == '조절':
            return '비가동' # F, G, J, K 모두 비가동
        return 'N/A' 

    df_processed['event_status'] = df_processed.apply(assign_status, axis=1)
    df_processed = df_processed.sort_values(by=['pn', 'pclrt_idno', 'mntnc_reqstdt']).reset_index(drop=True)
    
    print(f"전처리 및 필터링 완료. 분석 대상 {len(df_processed)}")
    return df_processed

# 1.1. 운영 타임라인 데이터 생성
def create_timeline_data(df, start_date, end_date):
    """
    1. Rule #1: 분석 시작일(start_date) < 첫 의뢰일자일 때, 첫 의뢰일자의 상태와 반대 상태의 날짜 기간 생성
    2. Rule #2: 분석 시작일(start_date) > 첫 의뢰일자일 때, 의뢰일자를 분석 시작일로 변경 (첫 의뢰일자는 분석 시작일부터 시작)
    3. Rule #3: 마지막 출고일자 이후 분석 종료일(end_date)까지의 빈 날짜 간격 처리
    """
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    timeline_events = []
    
    if df.empty:
         print("경고: create_timeline_data에 빈 데이터프레임이 전달됨.")
         return pd.DataFrame(columns=['start_time', 'end_time', 'status'])
        
    first_event_start = df.iloc[0]['mntnc_reqstdt']
    
    # 첫 의뢰일자 앞 기간 데이터 생성
    if start_date < first_event_start:
        gap_status = '가동'
        timeline_events.append({
            'start_time': start_date,
            'end_time': first_event_start,
            'status': gap_status
        })

    # 이벤트 간 사이의 날짜 데이터 처리
    df['next_mntnc_reqstdt'] = df['mntnc_reqstdt'].shift(-1)
    
    for i, row in df.iterrows():
        event_start = row['mntnc_reqstdt']
        event_end = row['rels_dhm']
        next_event_start = row['next_mntnc_reqstdt']
        event_status = row['event_status']
        
        # 유효한 기간만 데이터 추가
        actual_event_start = max(event_start, start_date) 
        actual_event_end = min(event_end if pd.notna(event_end) else end_date, end_date)

        if actual_event_start < actual_event_end:
            timeline_events.append({
                'start_time': actual_event_start,
                'end_time': actual_event_end,
                'status': event_status
            })
        
        # 사이 공백 기간 처리
        if pd.notna(event_end) and event_end < end_date:
            actual_gap_start = max(event_end, start_date) 
            between_status = '가동'
            actual_between_end = min(next_event_start if pd.notna(next_event_start) else end_date, end_date)
            
            if actual_gap_start < actual_between_end:
                timeline_events.append({
                    'start_time': actual_gap_start,
                    'end_time': actual_between_end,
                    'status': between_status
                })

    if not timeline_events:
         return pd.DataFrame(columns=['start_time', 'end_time', 'status'])
         
    df_timeline = pd.DataFrame(timeline_events)
    
    df_timeline = df_timeline[df_timeline['start_time'] < df_timeline['end_time']]
    df_timeline = df_timeline.sort_values(by='start_time').reset_index(drop=True)

    if df_timeline.empty:
        return df_timeline

    # 날짜를 문자열로 변환
    df_timeline['start_time'] = df_timeline['start_time'].dt.strftime('%Y-%m-%d')
    df_timeline['end_time'] = df_timeline['end_time'].dt.strftime('%Y-%m-%d')
        
    return df_timeline

# 1.2. 일별 0/1 상태 로그 생성 (타임라인 기반 - 가동/비가동 플롯 시각화용 데이터)
def create_daily_status_log(df_timeline, start_date, end_date):
    """
    운영 타임라인 데이터(1.1.에서 생성)에서 일별 0/1 상태 로그를 생성 (가동=1, 비가동=0)
    """
    if df_timeline.empty:
        return pd.DataFrame(columns=['date', 'status_code'])

    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    df_daily_log = pd.DataFrame(date_range, columns=['date'])
    df_daily_log['status_code'] = 0 # 기본값 비가동(0)
    
    # 날짜를 datetime으로 변환
    for i, row in df_timeline.iterrows():
        if row['status'] == '가동':
            row_start = pd.to_datetime(row['start_time'])
            row_end = pd.to_datetime(row['end_time'])
            
            mask = (df_daily_log['date'] >= row_start) & \
                   (df_daily_log['date'] < row_end)
            
            if row_end == end_date:
                end_date_mask = (df_daily_log['date'] == end_date)
                mask = mask | end_date_mask

            df_daily_log.loc[mask, 'status_code'] = 1
    
    df_daily_log['date'] = df_daily_log['date'].dt.strftime('%Y-%m-%d')
    return df_daily_log

# 2. TTR/TBF 시간 데이터 계산 (타임라인 기반)
def calculate_durations_from_timeline(df_timeline, end_date):
    """
    운영 타임라인 데이터(1.1.에서 생성)에서 TTR/TBF 시간 데이터 추출
    """
    end_date = pd.to_datetime(end_date)
    tbf_durations, tbf_events = [], []
    ttr_durations, ttr_events = [], []

    if df_timeline.empty:
        return (tbf_durations, tbf_events), (ttr_durations, ttr_events)

    last_index = len(df_timeline) - 1

    for i, row in df_timeline.iterrows():
        start_time = pd.to_datetime(row['start_time'])
        end_time = pd.to_datetime(row['end_time'])
        status = row['status']
        
        duration = (end_time - start_time) / pd.Timedelta(days=1)
        if duration <= 0:
            continue
        
        # 우측관측중단(right censored 적용)
        is_censored = (i == last_index) and (end_time == end_date)
        observed = 0 if is_censored else 1
            
        if status == '가동':
            tbf_durations.append(duration)
            tbf_events.append(observed)
        else:
            ttr_durations.append(duration)
            ttr_events.append(observed)
            
    # print(f"TBF 데이터 {len(tbf_durations)}개 생성 (관측완료 {sum(tbf_events)}개)")
    # print(f"TTR 데이터 {len(ttr_durations)}개 생성 (관측완료 {sum(ttr_events)}개)")

    return (tbf_durations, tbf_events), (ttr_durations, ttr_events)

# 3. 분포 비교 및 최적 분포 선정
def find_best_distribution(durations, events):
    """
    fit() 이후 AIC를 대상으로 분포를 비교하여 최적 분포 선정
    """
    if not durations or len(durations) < 2:
        print(f"경고: 분포 피팅을 위한 데이터 부족 < 2")
        return None
        
    models = { "LogNormal": LogNormalFitter(), "Exponential": ExponentialFitter(), "Weibull": WeibullFitter() }
    best_model, best_aic = None, np.inf
    
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, model in models.items():
            try:
                model.fit(durations, event_observed=events)
                print(f"{name} :{model.AIC_}")

                if not np.isfinite(model.AIC_):
                    print(f"{name} 모델 피팅 실패 (AIC={model.AIC_})")
                    continue
                if model.AIC_ < best_aic:
                    best_aic, best_model = model.AIC_, model
            except Exception as e:
                print(f"{name} 모델 피팅 중 예외 발생: {e}")
                pass 
            
    if best_model is None: 
        return None
    return best_model

# 4.1. 모델 평균 계산
def get_model_mean(model):
    """
    최적 분포로 선정된 norm, expon, weibull_min 모델의 파라미터로 계산
    """
    if model is None:
        return 0
    
    model_type = model.__class__.__name__
    mean_val = 0 

    try:
        if model_type == 'LogNormalFitter':
            if hasattr(model, 'mu_') and hasattr(model, 'sigma_'):
                mean_val = np.exp(model.mu_ + (model.sigma_**2) / 2)
        elif model_type == 'ExponentialFitter':
            if hasattr(model, 'lambda_'):
                mean_val = model.lambda_
        elif model_type == 'WeibullFitter':
            if hasattr(model, 'lambda_') and hasattr(model, 'rho_'):
                mean_val = model.lambda_ * gamma(1 + 1 / model.rho_)
        elif hasattr(model, 'mean_'):
            mean_val = model.mean_
            
    except Exception as e:
        print(f"{model_type} 평균 계산 중 오류: {e}")
        mean_val = np.nan

    # 평균 값에 문제가 있을 경우 중앙 값으로 대체 
    if np.isfinite(mean_val):
        return mean_val 
        
    try:
        median_val = model.median_
        if np.isfinite(median_val):
            return median_val
        else:  # 중앙값이 없는 경우 nan으로 처리
            return np.nan
    except Exception as e:
        return np.nan # 문제가 있을 경우 nan으로 처리 

# --- 4. RAM 지표 계산 ---
def calculate_ram_metrics(tbf_model, ttr_model):
    """
    ttr/tbf 데이터로 최적 선정한 모델을 사용해 RAM 지표를 계산
    """

    mtbf = get_model_mean(tbf_model)
    mttr = get_model_mean(ttr_model)
            
    failure_rate = 1 / mtbf if mtbf > 0 else 0
    repair_rate = 1 / mttr if mttr > 0 else 0
    availability = mtbf / (mtbf + mttr) if mtbf > 0 else 0
        
    return {
        'mtbf': mtbf,
        'mttr': mttr,
        'failure_rate': failure_rate,
        'repair_rate': repair_rate,
        'availability': availability
    }

# --- 5. 시각화 구성 데이터 생성 ---
def create_visualization_data(tbf_model, ttr_model, tbf_durations, ttr_durations, ram_metrics):
    """
    3가지 시각화 차트(신뢰도, 보전도, 고장률)를 위한 데이터 생성
    """
    max_ttr = 0
    max_tbf = 0

    reliability = 0
    hazard_rate = 0
    maintainability = 0

    if tbf_model and tbf_durations:
        x_tbf = np.arange(0, int(np.max(tbf_durations))+1)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            reliability = tbf_model.survival_function_at_times(x_tbf)
            hazard_rate = tbf_model.hazard_at_times(x_tbf)

        max_tbf = int(np.max(tbf_durations)) if len(tbf_durations) > 0 else 0

    if ttr_model and ttr_durations:

        x_ttr = np.arange(0, int(np.max(ttr_durations)) + 1)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            maintainability = 1 - ttr_model.survival_function_at_times(x_ttr)

        max_ttr = int(np.max(ttr_durations)) if len(ttr_durations) > 0 else 0

    t = np.arange(max(max_ttr, max_tbf)+1)

    viz_data = {'time': t, 'reliability': reliability, 'maintainability': maintainability, 'hazard_rate': hazard_rate, 'availability': ram_metrics.get('availability')}

    df_viz = pd.DataFrame(viz_data)

    return df_viz

# 6. 시각화 처리 함수
# 6.1. 타임라인 스텝 플롯 생성 ---
def create_timeline_plot(df_daily_log, no_pclrt_idno, mode, save_filename="timeline_plot.png"):
    """
    0/1로 구성된 df_daily_log를 기반으로 가동/비가동 플롯을 생성
    """
    if df_daily_log.empty:
        print("경고: 플롯을 생성할 타임라인 데이터가 없습니다.", no_pclrt_idno)
        return

    try:
        df_daily_log['date'] = pd.to_datetime(df_daily_log['date'], format='%Y-%m-%d')

        # x, y 준비
        x_dates = df_daily_log['date']
        y_values = df_daily_log['status_code']

        # step plot
        plt.figure(figsize=(10, 4))
        plt.step(x_dates, y_values, where='post', label=f"ID: {no_pclrt_idno}")
        plt.yticks([0, 1], ['비가동', '가동'])
        plt.ylim(-0.2, 1.2)
        plt.xlabel("날짜")
        plt.ylabel("상태")
        plt.title(f"장비 가동 상태 타임라인 - {mode}")
        plt.legend()
        plt.grid(True, axis='x', linestyle='--', alpha=0.5)

        # x축 포맷
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gcf().autofmt_xdate()

        # 저장
        plt.savefig(save_filename, dpi=150, bbox_inches='tight')
        plt.close()

        # print(f"타임라인 플롯 저장 완료: {save_filename}")

    except Exception as e:
        print(f"타임라인 플롯 생성 실패: {e}")

# 6.2. RAM 곡선 플롯 생성 (5개)
def create_ram_plots(df_viz, serial_no, mode, save_prefix="ram_plot"):
    """
    ram_viz_data(5.에서 생성)를 시영헤 5개의 신뢰성 곡선 플롯 생성
    """
    if df_viz.empty or 'time' not in df_viz.columns:
        print("경고: 플롯을 생성할 시각화 데이터가 없습니다.", serial_no)
        return

    time = df_viz['time']
    plot_info = [
        ('reliability', f"신뢰도 곡선(R(t)) - {mode}", "reliability"),
        ('maintainability', f"보전도 곡선(M(t)) - {mode}", "maintainability"),
        ('hazard_rate', f"고장률 곡선(h(t)) - {mode}", "hazard_rate")
    ]
    saved_files = []

    for y_col, title, y_label in plot_info:
        if y_col not in df_viz.columns:
            print(f"{y_col} 컬럼이 없어 건너뜁니다.")
            continue
        
        try:
            plt.figure(figsize=(10, 6))
            plt.plot(time, df_viz[y_col], label=f"{y_col} (ID: {serial_no})")
            
            if y_col in ['reliability', 'maintainability', 'hazard_rate']:
                plt.ylim(-0.05, 1.05)
                
            plt.title(title)
            plt.xlabel("시간(일)")
            plt.ylabel(y_label)
            plt.legend()
            plt.grid(True, linestyle='--', alpha=0.6)
            
            safe_y_col = "".join(c for c in y_col if c.isalnum() or c in ['(', ')'])
            save_filename = f"{save_prefix}_{safe_y_col}.png"
            plt.savefig(save_filename, dpi=150, bbox_inches='tight')
            plt.close()
            saved_files.append(save_filename)

        except Exception as e:
            print(f"오류: {title} 플롯 생성 실패: {e}")
            plt.close() 
            
    # print(f"RAM 곡선 플롯 {len(saved_files)}개 저장 완료")

# 6.3. 운용가용도 상태 플롯 생성
def create_oper_availability_plot(ram_metrics, save_filename="operational_availability.png"):
    """
    ram_metrics의 운용가용도를 기반으로 플롯 생성
    """
    try:
        plt.figure(figsize=(4,6))
        plt.bar(['availability'], [ram_metrics.get('availability')], color='skyblue')
        plt.ylim(0,1)
        plt.ylabel("availability")
        plt.title("pn availability")

        # 저장
        plt.savefig(save_filename, dpi=150, bbox_inches='tight')
        plt.close()

        # print(f"운용가용도 플롯 저장 완료: {save_filename}")

    except Exception as e:
        print(f"운용가용도 플롯 생성 실패: {e}")

# 메인 실행 함수
def analyze_ram(no_pn, no_pclrt_idno, mode, start_date, end_date):
    
    # 단계 0: 데이터 로드
    try:
        df_raw = load_data()
    except Exception as e: 
        print(f"데이터 로드 실패: {e}")
        return

    # 단계 1: 전처리
    try:
        df_filter = preprocess_data(df_raw, no_pn, no_pclrt_idno, mode, start_date, end_date)
    except Exception as e:
        print(f"데이터 전처리 중 오류 발생: {e}")
        return

    # 단계 1.1: 필터링 결과 확인 (데이터 없음)
    if df_filter.empty:
        print("-" * 30)
        print(f"분석 중단: 해당 부품({no_pn} / {no_pclrt_idno})는")
        print(f"분석 기간({start_date} ~ {end_date}) 내에 유효한 데이터가 없습니다.")
        print("-" * 30)
        return

    # 단계 2 ~ 5: 분석 진행
    try:

        # 표준 UUID (32자리 hex + 하이픈)
        analysis_id = str(uuid.uuid4())
        print('analysis_id : ', analysis_id)

        pn_no_list = df_filter.loc[:, 'pn'].unique().tolist()

        df_summarys = pd.DataFrame()
        df_visualizations = pd.DataFrame()
        df_daily_log = None

        for pn_no_loop in tqdm(pn_no_list, desc="부품번호"):

            pclrt_idno_no_list = df_filter.loc[df_filter['pn'] == pn_no_loop, 'pclrt_idno'].unique().tolist()

            ttr_durations = []
            ttr_events = []
            tbf_durations = []
            tbf_events = []

            df_daily_log = None

            for pclrt_idno_no_loop in tqdm(pclrt_idno_no_list, desc=f"부품번호 : {pn_no_loop}"):

                df_time = df_filter[(df_filter['pn'] == pn_no_loop) & (df_filter['pclrt_idno'] == pclrt_idno_no_loop)]

                df_timeline = create_timeline_data(df_time.copy(), start_date, end_date)

                if no_pclrt_idno:
                    df_daily_log = create_daily_status_log(df_timeline, start_date, end_date)

                    df_daily_log['analysis_id'] = analysis_id
                    df_daily_log['pn'] = pn_no_loop
                    df_daily_log['pclrt_idno'] = no_pclrt_idno if no_pclrt_idno else 'ALL'
                    df_daily_log = df_daily_log[['analysis_id', 'pn', 'pclrt_idno', 'date', 'status_code']]
            
                # 단계 2.3: TTR/TBF 데이터셋 생성
                (tbf_duration, tbf_event), (ttr_duration, ttr_event) = calculate_durations_from_timeline(df_timeline.copy(), end_date)
            
                ttr_durations.extend(ttr_duration)
                ttr_events.extend(ttr_event)
                tbf_durations.extend(tbf_duration)
                tbf_events.extend(tbf_event)

            print("== TBF, TTR 시간 데이터 구성 ==")
            print(f"tbf_durations : {tbf_durations}, tbf_events : {tbf_events}")
            print(f"ttr_durations : {ttr_durations}, ttr_events : {ttr_events}")

            # 단계 3: 분포 비교 후 최적 분포 선정
            print("== 모수적 방법을 이용한 최적 분포 선정 ==")
            print("-- TBF 최적 분포 선정 진행 --")
            tbf_model = find_best_distribution(tbf_durations, tbf_events)
            print("-- TTR 최적 분포 선정 진행 --")
            ttr_model = find_best_distribution(ttr_durations, ttr_events)
            print(f"tbf_model : {tbf_model}\nttr_model : {ttr_model}")

            # 단계 4: RAM 지표 계산
            ram_metrics = calculate_ram_metrics(tbf_model, ttr_model)

            print(f"== MTBF, MTTR, 수리율, 고장율, 운용가용도 계산 ==\n{ram_metrics}")

            summary_data = {
                'analysis_id': [analysis_id],
                'pn': [pn_no_loop],
                'pclrt_idno': [no_pclrt_idno if no_pclrt_idno else 'ALL'],
                **ram_metrics
            }

            df_summary_data = pd.DataFrame(summary_data)
            
            # 단계 5: 시각화 데이터 생성
            df_visualization_data = create_visualization_data(ttr_model, tbf_model, ttr_durations, tbf_durations, ram_metrics)

            df_visualization_data['analysis_id'] = analysis_id
            df_visualization_data['pn'] = pn_no_loop
            df_visualization_data['pclrt_idno'] = no_pclrt_idno if no_pclrt_idno else 'ALL'

            df_visualization_data = df_visualization_data[['analysis_id', 'pn', 'pclrt_idno', 'time', 'reliability', 'maintainability', 'hazard_rate', 'availability']]

            df_summarys = pd.concat([df_summarys, df_summary_data])
            df_visualizations = pd.concat([df_visualizations, df_visualization_data])
            
            no_pclrt_tag = no_pclrt_idno if no_pclrt_idno else 'ALL'

            if no_pn:
                avail_plot_file_name = f"result/1.운용가용도 상태_{no_pn}_{no_pclrt_tag}_{mode}.png"
                ram_plot_prefix = f"result/1.RAM 곡선_{no_pn}_{no_pclrt_tag}_{mode}"

                try:
                    # 2. RAM 3개 곡선 (3개 PNG)
                    create_ram_plots(df_visualization_data, no_pclrt_tag, mode, ram_plot_prefix)

                    # 3. 운용가용도 (1개 PNG)
                    create_oper_availability_plot(ram_metrics, avail_plot_file_name)

                except Exception as e:
                    print(f"시각화 생성 중 오류 발생: {e}")
            
            if no_pclrt_idno:
                time_plot_file_name = f"result/1.가동&비가동 상태_{no_pn}_{no_pclrt_idno}_{mode}.png"
                try:
                    # 1. 타임라인 스텝 (1개 PNG)
                    if df_daily_log is not None:
                        create_timeline_plot(df_daily_log, no_pclrt_idno, mode, time_plot_file_name) 
                    else:
                        print(f"경고: {no_pclrt_idno}의 일별 로그 데이터가 없어 타임라인 플롯을 건너뜁니다.")
                except Exception as e:
                    print(f"타임라인 시각화 생성 중 오류 발생: {e}")

        print('== 운용가용도 분석 결과 ==')
        print(df_summarys.head(1))

        print('== 시각화 데이터 추출 결과 ==')
        print(df_visualizations.head(5))

        summary_filename = f"result/1.ram_result_{mode}.csv"
        viz_filename = f"result/1.ram_viz_data_{mode}.csv"
        
        df_summarys.to_csv(summary_filename, index=False, encoding='utf-8-sig')
        df_visualizations.to_csv(viz_filename, index=False, encoding='utf-8-sig')

    except Exception as e:
        print(f"장비의 운용가용도 추출에 실패했습니다. (분석 단계 오류): {e}")
        return

# 스크립트 실행 (argparse)
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="장비 RAM 분석 스크립트")
    # parser.add_argument("--no_pn", type=str, default='부품번호00009', help="부품번호")
    parser.add_argument("--no_pn", type=str, default='', help="부품번호")
    # parser.add_argument("--no_pclrt_idno", type=str, default='ATN-00429286', help="고유식별번호")
    parser.add_argument("--no_pclrt_idno", type=str, default='', help="고유식별번호")
    parser.add_argument("--mode", type=str, default='조절', choices=['수리', '조절'], help="분석 모드 ('수리' 또는 '조절')")
    parser.add_argument("--start_date", type=str, default='2021-01-01', help="분석 시작일 (YYYY-MM-DD)")
    parser.add_argument("--end_date", type=str, default='2022-02-20', help="분석 종료일 (YYYY-MM-DD)")
    args = parser.parse_args()

    try:
        analyze_ram(
            no_pn=args.no_pn,
            no_pclrt_idno=args.no_pclrt_idno,
            mode=args.mode,
            start_date=args.start_date,
            end_date=args.end_date
        )
    except Exception as e:
        print(f"분석 중 치명적인 오류 발생: {e}")