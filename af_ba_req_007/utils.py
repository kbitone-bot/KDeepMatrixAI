import numpy as np
import pandas as pd

from datetime import datetime

def counts_es(df, type_name):
    now = datetime.now()
    year_val = now.year
    month_val = now.month
    
    return_json = []
    for es_num in [1,2,3,5,6,7,8]:
        sheet_name = str(es_num) + "시험소"
        es_df = df[sheet_name]

        es_df = es_df.replace("―", np.nan)
        es_df = es_df.dropna(subset=[type_name])
        es_df = es_df.reset_index(drop=True)
        es_df = es_df[['Unnamed: 1', type_name]]

        def extract_grade(value):
            return int(str(value)[0])

        es_df[type_name] = es_df[type_name].apply(extract_grade)

        count_type1 = (
            es_df[type_name]
            .value_counts()
            .sort_index()
            .reindex([1, 2, 3, 4], fill_value=0)
        )

        row = {
            "AFF": sheet_name,
            "FIELD": type_name,
            "GRAD_1_COUNT": int(count_type1.loc[1]),
            "GRAD_2_COUNT": int(count_type1.loc[2]),
            "GRAD_3_COUNT": int(count_type1.loc[3]),
            "GRAD_4_COUNT": int(count_type1.loc[4]),
            "YEAR": year_val,
            "MONTH": month_val,
        }

        # count_type1.index = [f"{i}등급" for i in count_type1.index]

        return_json.append(row)

    df = pd.DataFrame(return_json)

    return df





def counting_total(category_df, personal_status):
    now = datetime.now()
    year_val = now.year
    month_val = now.month
    
    caliber_info = np.array(category_df['IMQC 관리항목(신)_도량']['WUC'])
    electric_info = np.array(category_df['IMQC 관리항목(신)_전기']['WUC'])
    electron_info = np.array(category_df['IMQC 관리항목(신)_전자']['WUC'])

    wuc = np.concatenate((caliber_info, electron_info, electric_info))
    a = np.array(["도량"] * len(caliber_info))
    b = np.array(["전기/전자"] * (len(electric_info) + len(electron_info)))
    field = np.concatenate((a,b))
    wuc_df = pd.DataFrame({"정밀측정분류코드": wuc, "작업": field})

    personal_status = personal_status[personal_status['계획년도'] == 2025]
    personal_status = personal_status[['군', '지원시험소_코드화', '계획년도', '계획월', '계획여부','표준인시', '난이도', '정밀측정분류코드']]

    merged_df = personal_status.merge(
        wuc_df,
        how="left",
        left_on="정밀측정분류코드",
        right_on="정밀측정분류코드"
    )

    plan_2025_df = merged_df.dropna()
    plan_2025_df = plan_2025_df[plan_2025_df['계획여부'] == 'Y']
    plan_2025_df = plan_2025_df[plan_2025_df['군'] == '공군']
    plan_2025_df = plan_2025_df.drop_duplicates(subset=['군', '지원시험소_코드화', '계획년도', '계획월', '계획여부', '난이도', '정밀측정분류코드', '작업'])

    result = (
        plan_2025_df
        .groupby(["작업", "지원시험소_코드화", "계획년도", "계획월", "난이도"])["표준인시"]
        .sum()
        .reset_index()
    )


    _MONTH_WORK_DAYS = {1:23, 2:20, 3:21, 4:22, 5:22, 6:21,
                        7:23, 8:21, 9:22, 10:23, 11:20, 12:23}

    def _int_required(std_hour_sum: float, month: int) -> int:
        days = _MONTH_WORK_DAYS.get(int(month), 22)
        if not std_hour_sum:
            return 0
        return int((float(std_hour_sum) / 5.05) / days)

    need_map = {}
    for _, row in result.iterrows():
        field_val = row["작업"]
        aff_val = row["지원시험소_코드화"]

        if aff_val not in ["시험소001", "시험소002", "시험소003", "시험소005", "시험소006", "시험소007", "시험소008"]:
            continue

        month_val = int(row["계획월"])
        diff = row["난이도"]
        st_sum = float(row["표준인시"])


        diff_int = int(diff)

        required = _int_required(st_sum, month_val)

        key = (field_val, aff_val, month_val)

        if key not in need_map:
            need_map[key] = {
                "grad_1_count": 0,
                "grad_2_count": 0,
                "grad_3_count": 0,
                "grad_4_count": 0,
            }

        col_name = f"grad_{diff_int}_count"
        need_map[key][col_name] += required

    # print(need_map)

    YEAR_VALUE = year_val   # 원하는 year 값 넣기

    rows = []

    for (field, aff, month), counts in need_map.items():
        rows.append({
            "AFF": aff,
            "FIELD": field,
            "YEAR": YEAR_VALUE,
            "MONTH": month,
            "GRAD_1_COUNT": counts.get("grad_1_count", 0),
            "GRAD_2_COUNT": counts.get("grad_2_count", 0),
            "GRAD_3_COUNT": counts.get("grad_3_count", 0),
            "GRAD_4_COUNT": counts.get("grad_4_count", 0)
        })

    df = pd.DataFrame(rows)

    # print(df)
    
    return df