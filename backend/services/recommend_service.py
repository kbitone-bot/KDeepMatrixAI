from typing import Dict, Any
from backend.services.base import BaseAnalysisService
from backend.models.schemas import AnalysisResult


class RecommendAnalysisService(BaseAnalysisService):
    model_id = "af_ba_req_005"
    model_name = "기술검토자동처리"
    
    def analyze(self, params: Dict[str, Any]) -> AnalysisResult:
        return AnalysisResult(
            analysis_id="",
            model_id=self.model_id,
            status="unavailable",
            message="af_ba_req_005 서비스는 현재 구조만 등록되어 있습니다.",
        )
