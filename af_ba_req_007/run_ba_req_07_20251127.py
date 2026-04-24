import pandas as pd
import numpy as np
from datetime import datetime
from tabulate import tabulate
from utils import *
import logging
from logging.handlers import RotatingFileHandler

now = datetime.now()
year_val = now.year
month_val = now.month

# =============================
# Logging 설정
# =============================
log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s"
)

log_handler = RotatingFileHandler(
    f"af_ba_req_007/analysis_log_{str(now).split(' ')[0]}.log",
    maxBytes=10*1024*1024,
    backupCount=5,
    encoding="utf-8"
)
log_handler.setFormatter(log_formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

logger.info("===== BA_REQ_007 =====")

pd.set_option('mode.chained_assignment',  None)

logger.info(f"YEAR={year_val}, MONTH={month_val}")

####################
##  Load dataset  ##
####################

print("분석에 필요한 데이터 불러오는 중 (3~4분 소요)")
logger.info("분석에 필요한 데이터 불러오는 중 (3~4분 소요)")

try:
    df = pd.read_excel("D:/85/af_ba_req_007/datasets/IMQC 등급현황 (1).xlsx",
                       header=3, engine='openpyxl', sheet_name=None)
    category_df = pd.read_excel("D:/85/af_ba_req_007/datasets/IMQC 개선 및 관리항목 (1).xlsx",
                                header=0, engine='openpyxl', sheet_name=None)
    personal_status = pd.read_excel("D:/85/af_ba_req_007/datasets/21-25년 계획수립현황_코드화.xlsx",
                                    engine='openpyxl')

    print("데이터 로드 성공")
    logger.info("데이터 로드 성공")

except Exception as e:
    logger.error("데이터 로드 실패", exc_info=True)
    raise


###############################
## 현재 인원 수 통계 계산   ##
###############################

results_calib = counts_es(df, "도량")
results_elec = counts_es(df, "전기/전자")

results_curr_per_aff = pd.concat((results_calib, results_elec))
logger.info("<분야, 시험소 별 IMQC 등급에 따른 현재 인원 수 통계 결과>")
logger.info(f"\n{tabulate(results_curr_per_aff, headers='keys', tablefmt='fancy_grid', showindex=False)}")

print("<분야, 시험소 별 IMQC 등급에 따른 현재 인원 수 통계 결과>")
print(tabulate(results_curr_per_aff, headers='keys', tablefmt='fancy_grid', showindex=False))


###############################################
## 필요 인원 (category_df + personal_status) ##
###############################################

results_counting_total = counting_total(category_df, personal_status)
results_counting_total = results_counting_total[results_counting_total["MONTH"] == month_val]


###############################################
## 현재 합계 vs 필요 합계 계산                  ##
###############################################

curr_totals = (
    results_curr_per_aff
    .groupby(["FIELD", "YEAR", "MONTH"], as_index=False)[
        ["GRAD_1_COUNT", "GRAD_2_COUNT", "GRAD_3_COUNT", "GRAD_4_COUNT"]
    ]
    .sum()
    .rename(columns={
        "GRAD_1_COUNT": "GRAD_1_CUR_TOTAL",
        "GRAD_2_COUNT": "GRAD_2_CUR_TOTAL",
        "GRAD_3_COUNT": "GRAD_3_CUR_TOTAL",
        "GRAD_4_COUNT": "GRAD_4_CUR_TOTAL",
    })
)

req_totals = (
    results_counting_total
    .groupby(["FIELD", "YEAR", "MONTH"], as_index=False)[
        ["GRAD_1_COUNT", "GRAD_2_COUNT", "GRAD_3_COUNT", "GRAD_4_COUNT"]
    ]
    .sum()
    .rename(columns={
        "GRAD_1_COUNT": "GRAD_1_REQ_TOTAL",
        "GRAD_2_COUNT": "GRAD_2_REQ_TOTAL",
        "GRAD_3_COUNT": "GRAD_3_REQ_TOTAL",
        "GRAD_4_COUNT": "GRAD_4_REQ_TOTAL",
    })
)

total_df = pd.merge(
    curr_totals,
    req_totals,
    on=["FIELD", "YEAR", "MONTH"],
    how="inner"
)

total_df = total_df[[
    "FIELD",
    "GRAD_1_CUR_TOTAL", "GRAD_2_CUR_TOTAL", "GRAD_3_CUR_TOTAL", "GRAD_4_CUR_TOTAL",
    "GRAD_1_REQ_TOTAL", "GRAD_2_REQ_TOTAL", "GRAD_3_REQ_TOTAL", "GRAD_4_REQ_TOTAL",
    "YEAR", "MONTH"
]]

logger.info("<분야 별 IMQC 등급에 따른 현재-필요 인원 수 합계>")
logger.info(f"\n{tabulate(total_df, headers='keys', tablefmt='fancy_grid', showindex=False)}")

print("\n<분야 별 IMQC 등급에 따른 현재-필요 인원 수 합계>")
print(tabulate(total_df, headers='keys', tablefmt='fancy_grid', showindex=False))

logger.info("===== 분석 종료 =====")
