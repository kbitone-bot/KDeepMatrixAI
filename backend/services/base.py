from abc import ABC, abstractmethod
from typing import Dict, Any
from backend.models.schemas import AnalysisResult


class BaseAnalysisService(ABC):
    """Base class for analysis services."""
    
    model_id: str = ""
    model_name: str = ""
    
    @abstractmethod
    def analyze(self, params: Dict[str, Any]) -> AnalysisResult:
        pass
