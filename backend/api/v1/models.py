from fastapi import APIRouter
from typing import List
from backend.model_registry import scan_models
from backend.models.schemas import ModelInfo

router = APIRouter()

@router.get("/models", response_model=List[ModelInfo])
def list_models():
    return scan_models()
