import os, json, numpy as np, pandas as pd, joblib
from sklearn.neighbors import NearestNeighbors
import logging
from datetime import datetime
import builtins


# ===================================================================
# 1) 로그 설정 (파일 로그만)
# ===================================================================
LOG_DIR = "D:/85/af_ba_req_005/log"
os.makedirs(LOG_DIR, exist_ok=True)

log_filename = datetime.now().strftime("test_%Y-%m-%d_%H-%M-%S.log")
log_path = os.path.join(LOG_DIR, log_filename)

# StreamHandler 제거 → print가 콘솔 1번만 출력됨
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8")  # 파일에만 기록
    ]
)

# ===================================================================
# 2) print() 오버라이드 → 콘솔 1번 + 파일 로그 기록
# ===================================================================
original_print = print

def print_and_log(*args, **kwargs):
    msg = " ".join(str(a) for a in args)
    logging.info(msg)                # 파일 저장
    original_print(*args, **kwargs)  # 콘솔 출력 (1번만)

builtins.print = print_and_log


print("===== 기술검토 자동처리 프로그램 시작 =====")


# ===================================================================
# 3) 모델 로드 (KMeans)
# ===================================================================
KMEANS_PATH = "D:/85/af_ba_req_005/weight/cluster_model_kmeans.joblib"
ID_COL = "부품번호"

print("📦 기술검토 자동처리 모델 로딩 중...")

try:
    GLOBAL_ART = joblib.load(KMEANS_PATH)
    GLOBAL_ART.setdefault("nn_by_cluster", {})
    print("✅ 모델 로드 완료!")
except Exception as e:
    print(f"❌ 모델 로드 실패: {e}")
    GLOBAL_ART = None


# ===================================================================
# 4) 유틸 함수들
# ===================================================================
def _build_query_vector(vectorizer, part: str):
    q = "" if part is None else str(part).upper().strip()
    return vectorizer.transform([q])


def get_cluster_for_part(artifact, part: str) -> int:
    df = artifact["df_display"]
    mask = (df[ID_COL].astype(str).str.upper().str.strip() == part.upper().strip())

    if not mask.any():
        raise ValueError(f"'{ID_COL}={part}' 를 찾을 수 없습니다.")

    # 1) df_display에 cluster 컬럼이 이미 있을 경우
    if "cluster" in df.columns:
        return int(df.loc[mask, "cluster"].iloc[0])

    # 2) 없으면 labels / model.labels_ 에서 찾기
    idx = int(np.flatnonzero(mask)[0])

    if "labels" in artifact:
        return int(np.asarray(artifact["labels"])[idx])

    model = artifact.get("model")
    if model is not None and hasattr(model, "labels_"):
        return int(model.labels_[idx])

    return -1


def _get_cluster_nn(artifact, target_cluster: int):
    cache = artifact.setdefault("nn_by_cluster", {})

    if target_cluster in cache:
        return cache[target_cluster]

    df_display = artifact["df_display"]
    X_tfidf = artifact["X_tfidf"]

    mask = (df_display["cluster"] == target_cluster).values
    if not mask.any():
        raise ValueError(f"cluster={target_cluster} 데이터가 없습니다.")

    X_sub = X_tfidf[mask, :]
    nn = NearestNeighbors(n_neighbors=min(50, X_sub.shape[0]), metric="cosine")
    nn.fit(X_sub)

    sub_indices = np.flatnonzero(mask)
    cache[target_cluster] = (nn, sub_indices)
    return nn, sub_indices


def _dedup_full_rows(out: pd.DataFrame) -> pd.DataFrame:
    exclude = {ID_COL, "similarity", "cluster"}
    subset_cols = [c for c in out.columns if c not in exclude]
    out[subset_cols] = out[subset_cols].astype(str).apply(lambda s: s.str.strip())
    return out.drop_duplicates(subset=subset_cols, keep="first")


def recommend_in_cluster_df(artifact, part: str, topn: int = 10):
    df_display = artifact["df_display"]
    vectorizer = artifact["tfidf_vectorizer"]

    cluster_id = get_cluster_for_part(artifact, part)
    nn, sub_idx = _get_cluster_nn(artifact, cluster_id)

    Xq = _build_query_vector(vectorizer, part)
    dist, idxs_local = nn.kneighbors(Xq, n_neighbors=min(topn * 5000, len(sub_idx)))

    global_rows = np.array(sub_idx)[idxs_local[0]]
    out = df_display.iloc[global_rows].copy()
    out["similarity"] = 1.0 - dist[0]
    out = out[out["similarity"] > 0]

    out = out.sort_values("similarity", ascending=False)
    out = out.drop_duplicates(subset=[ID_COL], keep="first")
    out = _dedup_full_rows(out)

    return out.head(topn).reset_index(drop=True), cluster_id


# ===================================================================
# 5) 추천 함수
# ===================================================================
def infer_kmeans(part: str, topn: int = 5):
    print(f"===== 사용자 요청: {part} =====")

    if GLOBAL_ART is None:
        print("❌ 모델이 로드되지 않아 추천을 수행할 수 없습니다.")
        return None

    try:
        df_rec, cluster_id = recommend_in_cluster_df(GLOBAL_ART, part, topn)
    except ValueError as e:
        print(f"❌ 오류: {e}")
        return None

    print(f"\n🔷 기술검토 자동처리 결과 (cluster={cluster_id})")
    # df_rec = df_rec.loc[:, df_rec.columns!='부품번호'] # ----------
    print(df_rec)

    return df_rec, cluster_id


# ===================================================================
# 6) 사용자 입력 루프
# ===================================================================
if __name__ == "__main__":
    print("\n===== 기술검토 자동처리 부품 추천 테스트 =====")

    while True:
        user_part = input("\n부품번호 입력 (종료하려면 exit): ").strip()
        print(f"🧑 사용자 입력: {user_part}")

        if user_part.lower() == "exit":
            print("프로그램을 종료합니다.")
            break

        TOPN = 5
        result = infer_kmeans(user_part, topn=TOPN)

        if result is not None:
            df_rec, cluster_id = result
            RESULT_DIR = "D:/85/af_ba_req_005/result"
            os.makedirs(RESULT_DIR, exist_ok=True)
            save_path = "D:/85/af_ba_req_005/result.json"
            out_json = {
                "cluster": int(cluster_id),
                "recommendations": df_rec.to_dict(orient="records")
            }

            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(out_json, f, ensure_ascii=False, indent=2)

            print(f"💾 JSON 저장 완료 → {save_path}")
