from typing import Dict, Any
from backend.services.base import BaseAnalysisService
from backend.models.schemas import AnalysisResult


class IMQCAnalysisService(BaseAnalysisService):
    model_id = "af_ba_req_007"
    model_name = "IMQC인원수급분석"
    
    def analyze(self, params: Dict[str, Any]) -> AnalysisResult:
        return AnalysisResult(
            analysis_id="",
            model_id=self.model_id,
            status="unavailable",
            message="af_ba_req_007 서비스는 현재 구조만 등록되어 있습니다.",
        )
