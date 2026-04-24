from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class CustomBaseModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


class AnalysisMode(str, Enum):
    REPAIR = "수리"
    ADJUST = "조절"


class ModelInfo(CustomBaseModel):
    model_id: str
    name: str
    description: str = ""
    source_files: List[str] = []
    data_files: List[str] = []
    result_files: List[str] = []
    status: str = "ready"  # ready, partial, unavailable


class RAMAnalysisRequest(CustomBaseModel):
    model_id: str = "af_ba_req_001"
    mode: AnalysisMode = AnalysisMode.REPAIR
    no_pn: Optional[str] = None
    no_pclrt_idno: Optional[str] = None
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None    # YYYY-MM-DD


class RAMMetrics(CustomBaseModel):
    mtbf: float
    mttr: float
    failure_rate: float
    repair_rate: float
    availability: float
    best_tbf_dist: Optional[str] = None
    best_ttr_dist: Optional[str] = None


class AnalysisResult(CustomBaseModel):
    analysis_id: str
    model_id: str
    status: str  # success, partial, failed
    message: str = ""
    metrics: Optional[Dict[str, Any]] = None
    summary_csv: Optional[str] = None
    viz_csv: Optional[str] = None
    timeline_csv: Optional[str] = None
    charts: List[str] = []
    report_html: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class ChartSpec(CustomBaseModel):
    chart_id: str
    title: str
    chart_type: str
    data: Optional[Dict[str, Any]] = None
    file_path: Optional[str] = None
