import os
from pathlib import Path
from typing import List, Dict
from backend.core.config import PROJECT_ROOT, MODEL_NAMES
from backend.models.schemas import ModelInfo


def scan_models() -> List[ModelInfo]:
    """Scan the project root for af_ba_req_* directories."""
    models = []
    for entry in sorted(PROJECT_ROOT.iterdir()):
        if entry.is_dir() and entry.name.startswith("af_ba_req_"):
            model_id = entry.name
            info = _inspect_model_dir(entry, model_id)
            models.append(info)
    return models


def _inspect_model_dir(model_dir: Path, model_id: str) -> ModelInfo:
    """Inspect a single model directory."""
    py_files = [f.name for f in model_dir.glob("*.py")]
    data_dir = model_dir / "data"
    datasets_dir = model_dir / "datasets"
    result_dir = model_dir / "result"
    
    data_files = []
    for d in (data_dir, datasets_dir):
        if d.exists():
            data_files.extend([f.name for f in d.iterdir() if f.is_file()])
    
    result_files = []
    if result_dir.exists():
        result_files = [f.name for f in result_dir.iterdir() if f.is_file()]
    
    status = "ready" if py_files and data_files else "partial" if py_files else "unavailable"
    return ModelInfo(
        model_id=model_id,
        name=MODEL_NAMES.get(model_id, model_id),
        description=f"Found {len(py_files)} scripts, {len(data_files)} data files",
        source_files=py_files,
        data_files=data_files,
        result_files=result_files,
        status=status
    )


def get_model(model_id: str) -> ModelInfo:
    models = scan_models()
    for m in models:
        if m.model_id == model_id:
            return m
    raise ValueError(f"Model {model_id} not found")
