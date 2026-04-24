from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from backend.models.schemas import AnalysisResult, RAMAnalysisRequest
from backend.services.ram_service import RAMAnalysisService
from backend.services.life_service import LifeAnalysisService
from backend.services.sim_service import SimAnalysisService
from backend.services.recommend_service import RecommendAnalysisService
from backend.services.imqc_service import IMQCAnalysisService

router = APIRouter()

SERVICE_MAP = {
    "af_ba_req_001": RAMAnalysisService(),
    "af_ba_req_002": LifeAnalysisService(),
    "af_ba_req_004": SimAnalysisService(),
    "af_ba_req_005": RecommendAnalysisService(),
    "af_ba_req_007": IMQCAnalysisService(),
}

@router.post("/analyze/ram", response_model=AnalysisResult)
def analyze_ram(req: RAMAnalysisRequest):
    service = RAMAnalysisService()
    params = req.model_dump()
    result = service.analyze(params)
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.message)
    return result

@router.post("/analyze/{model_id}", response_model=AnalysisResult)
def analyze(model_id: str, params: Dict[str, Any]):
    service = SERVICE_MAP.get(model_id)
    if not service:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    result = service.analyze(params)
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.message)
    return result
