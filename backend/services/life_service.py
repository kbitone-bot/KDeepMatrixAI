from typing import Dict, Any
from backend.services.base import BaseAnalysisService
from backend.models.schemas import AnalysisResult


class LifeAnalysisService(BaseAnalysisService):
    model_id = "af_ba_req_002"
    model_name = "장비수명예측"
    
    def analyze(self, params: Dict[str, Any]) -> AnalysisResult:
        return AnalysisResult(
            analysis_id="",
            model_id=self.model_id,
            status="unavailable",
            message="af_ba_req_002 서비스는 현재 구조만 등록되어 있습니다.",
        )
