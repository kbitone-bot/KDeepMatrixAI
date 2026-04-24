import os
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
from sklearn.neighbors import NearestNeighbors

from backend.services.base import BaseAnalysisService
from backend.models.schemas import AnalysisResult
from backend.core.config import PROJECT_ROOT
from backend.core.exceptions import DataLoadError, EmptyDataError


class RecommendAnalysisService(BaseAnalysisService):
    model_id = "af_ba_req_005"
    model_name = "기술검토자동처리(유사부품추천)"
    
    def __init__(self):
        self.artifact_path = PROJECT_ROOT / "outputs" / "models_005" / "cluster_model_kmeans.joblib"
        self._artifact = None
    
    def _load_artifact(self):
        if self._artifact is not None:
            return self._artifact
        if not self.artifact_path.exists():
            raise DataLoadError(f"Model artifact not found: {self.artifact_path}. Run scripts/train_005.py first.")
        self._artifact = joblib.load(self.artifact_path)
        self._artifact.setdefault("nn_by_cluster", {})
        return self._artifact
    
    def analyze(self, params: Dict[str, Any]) -> AnalysisResult:
        analysis_id = str(uuid.uuid4())
        try:
            part_no = params.get("part_no", "").strip()
            topn = int(params.get("topn", 10))
            if not part_no:
                raise ValueError("부품번호(part_no)를 입력하세요.")
            
            artifact = self._load_artifact()
            df_rec, cluster_id = self._recommend(artifact, part_no, topn)
            
            if df_rec.empty:
                return AnalysisResult(
                    analysis_id=analysis_id,
                    model_id=self.model_id,
                    status="failed",
                    message=f"부품번호 '{part_no}'에 대한 추천 결과가 없습니다.",
                )
            
            # 결과 저장
            output_dir = PROJECT_ROOT / "outputs" / analysis_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            summary_csv = output_dir / "summary.csv"
            df_rec.to_csv(summary_csv, index=False, encoding="utf-8-sig")
            
            # JSON 리포트
            report_json = {
                "cluster": int(cluster_id),
                "query_part": part_no,
                "recommendations": df_rec.to_dict(orient="records")
            }
            
            metrics = {
                "query_part": part_no,
                "cluster": int(cluster_id),
                "recommendation_count": len(df_rec),
                "avg_similarity": round(float(df_rec["similarity"].mean()), 4) if "similarity" in df_rec.columns else None,
            }
            
            return AnalysisResult(
                analysis_id=analysis_id,
                model_id=self.model_id,
                status="success",
                message=f"부품번호 '{part_no}' (cluster={cluster_id}) 추천 완료: {len(df_rec)}건",
                metrics=metrics,
                summary_csv=str(summary_csv),
            )
            
        except Exception as e:
            return AnalysisResult(
                analysis_id=analysis_id,
                model_id=self.model_id,
                status="failed",
                message=str(e),
            )
    
    def _recommend(self, artifact, part: str, topn: int):
        df_display = artifact["df_display"]
        vectorizer = artifact["tfidf_vectorizer"]
        X_tfidf = artifact["X_tfidf"]
        ID_COL = "부품번호"
        
        # 클러스터 찾기
        mask = (df_display[ID_COL].astype(str).str.upper().str.strip() == part.upper().strip())
        if not mask.any():
            # 부품번호가 없으면 TF-IDF로 가장 가까운 행 찾기
            q_vec = vectorizer.transform([part.upper().strip()])
            from sklearn.metrics.pairwise import cosine_distances
            dists = cosine_distances(q_vec, X_tfidf).flatten()
            nearest_idx = int(np.argmin(dists))
            cluster_id = int(df_display.iloc[nearest_idx]["cluster"])
        else:
            cluster_id = int(df_display.loc[mask, "cluster"].iloc[0])
        
        # 클러스터 내 NearestNeighbors
        cache = artifact.setdefault("nn_by_cluster", {})
        if cluster_id not in cache:
            c_mask = (df_display["cluster"] == cluster_id).values
            X_sub = X_tfidf[c_mask, :]
            nn = NearestNeighbors(n_neighbors=min(500, X_sub.shape[0]), metric="cosine")
            nn.fit(X_sub)
            sub_indices = np.flatnonzero(c_mask)
            cache[cluster_id] = (nn, sub_indices)
        
        nn, sub_idx = cache[cluster_id]
        q_vec = vectorizer.transform([part.upper().strip()])
        dist, idxs_local = nn.kneighbors(q_vec, n_neighbors=min(topn * 10, len(sub_idx)))
        
        global_rows = np.array(sub_idx)[idxs_local[0]]
        out = df_display.iloc[global_rows].copy()
        out["similarity"] = 1.0 - dist[0]
        out = out[out["similarity"] > 0]
        
        out = out.sort_values("similarity", ascending=False)
        out = out.drop_duplicates(subset=[ID_COL], keep="first")
        
        # 유사도 1.0(자기 자신) 제거
        out = out[out[ID_COL].astype(str).str.upper().str.strip() != part.upper().strip()]
        
        return out.head(topn).reset_index(drop=True), cluster_id
