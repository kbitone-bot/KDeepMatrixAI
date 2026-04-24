"""
af_ba_req_005 기술검토 자동처리 모델 학습 스크립트
KMeans + TF-IDF + NearestNeighbors 학습 및 artifact 저장
"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import os
import re
import numpy as np
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans


def load_data():
    data_dir = PROJECT_ROOT / "af_ba_req_005" / "db"
    files = list(data_dir.glob("*.xlsb"))
    if not files:
        raise FileNotFoundError("No xlsb files found in af_ba_req_005/db")
    target = [f for f in files if "복사" not in f.name][0]
    print(f"Loading: {target.name}")
    df = pd.read_excel(target, engine="pyxlsb")
    print(f"Loaded shape: {df.shape}")
    return df


def build_text_features(df: pd.DataFrame) -> pd.Series:
    """각 행의 텍스트 컬럼을 결합하여 하나의 문서 생성"""
    text_cols = [
        "부품번호", "한글품명", "재고번호", "보유부대명", "운영부대명",
        "정밀측정지원부대명", "입고시험소부대명", "정밀측정품목분류코드",
        "지원형태", "난이도", "정비주기", "작업표준ID"
    ]
    available = [c for c in text_cols if c in df.columns]
    
    def row_to_text(row):
        parts = []
        for col in available:
            val = row.get(col, "")
            if pd.notna(val) and str(val).strip() and str(val).strip() != "nan":
                parts.append(str(val).strip())
        return " ".join(parts)
    
    return df.apply(row_to_text, axis=1)


def train(output_dir: Path = None, n_clusters: int = 150):
    if output_dir is None:
        output_dir = PROJECT_ROOT / "outputs" / "models_005"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    df = load_data()
    
    # 메모리/속도를 위해 샘플링 (학습 품질에는 큰 영향 없음)
    if len(df) > 50000:
        df = df.sample(n=50000, random_state=42).reset_index(drop=True)
        print(f"Sampled to: {df.shape}")
    
    # 텍스트 특성 생성
    print("Building text features...")
    texts = build_text_features(df)
    
    # TF-IDF
    print("Fitting TF-IDF...")
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.9,
        dtype=np.float32,
    )
    X_tfidf = vectorizer.fit_transform(texts)
    print(f"TF-IDF shape: {X_tfidf.shape}")
    
    # KMeans
    print(f"Fitting KMeans (n_clusters={n_clusters})...")
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10, max_iter=300)
    labels = kmeans.fit_predict(X_tfidf)
    df["cluster"] = labels
    print(f"KMeans inertia: {kmeans.inertia_:.2f}")
    
    # artifact 구성 (test.py와 호환)
    artifact = {
        "df_display": df,
        "X_tfidf": X_tfidf,
        "tfidf_vectorizer": vectorizer,
        "model": kmeans,
        "labels": labels,
        "nn_by_cluster": {},
    }
    
    artifact_path = output_dir / "cluster_model_kmeans.joblib"
    joblib.dump(artifact, artifact_path)
    print(f"Artifact saved: {artifact_path}")
    
    # 메타 정보
    meta = {
        "n_samples": len(df),
        "n_features": X_tfidf.shape[1],
        "n_clusters": n_clusters,
        "inertia": float(kmeans.inertia_),
        "columns": list(df.columns),
    }
    meta_path = output_dir / "meta.json"
    import json
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Meta saved: {meta_path}")
    
    return artifact_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_clusters", type=int, default=150)
    args = parser.parse_args()
    train(n_clusters=args.n_clusters)
    print("Training completed!")
