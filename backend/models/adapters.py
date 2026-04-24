from abc import ABC, abstractmethod
from typing import Dict, Any, List
from backend.models.schemas import AnalysisResult, ChartSpec


class AnalysisModelAdapter(ABC):
    """Abstract adapter for analysis models."""
    
    def __init__(self, model_id: str, model_dir: str):
        self.model_id = model_id
        self.model_dir = model_dir
    
    @abstractmethod
    def inspect_inputs(self) -> Dict[str, Any]:
        """Return metadata about required inputs."""
        pass
    
    @abstractmethod
    def run_analysis(self, params: Dict[str, Any]) -> AnalysisResult:
        """Execute analysis with given parameters."""
        pass
    
    @abstractmethod
    def create_visualizations(self, result: AnalysisResult) -> List[ChartSpec]:
        """Create visualization specs from result."""
        pass
