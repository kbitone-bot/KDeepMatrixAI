import pandas as pd
from pathlib import Path
from typing import List, Optional
from backend.core.exceptions import DataLoadError, ColumnNotFoundError
from backend.utils.date_utils import ensure_datetime


def list_data_files(model_dir: Path) -> List[Path]:
    """List all data files in the model's data directory."""
    data_dir = model_dir / "data"
    if not data_dir.exists():
        data_dir = model_dir / "datasets"
    if not data_dir.exists():
        return []
    exts = {".xlsb", ".xlsx", ".xls", ".csv", ".json"}
    return [f for f in data_dir.iterdir() if f.suffix.lower() in exts]


def load_dataframe(file_path: Path, sheet_name: Optional[str] = None) -> pd.DataFrame:
    """Load a dataframe from various file formats."""
    try:
        suffix = file_path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(file_path)
        elif suffix == ".xlsb":
            return pd.read_excel(file_path, engine="pyxlsb", sheet_name=sheet_name or 0)
        elif suffix in {".xlsx", ".xls"}:
            return pd.read_excel(file_path, sheet_name=sheet_name or 0)
        else:
            raise DataLoadError(f"Unsupported file format: {suffix}")
    except Exception as e:
        raise DataLoadError(f"Failed to load {file_path}: {e}")


def load_ram_data(model_dir: Path, date_cols: Optional[List[str]] = None) -> pd.DataFrame:
    """Load RAM analysis data (af_ba_req_001)."""
    data_files = list_data_files(model_dir)
    target = None
    for f in data_files:
        if "가용도분석자료" in f.name:
            target = f
            break
    if target is None and data_files:
        target = data_files[0]
    if target is None:
        raise DataLoadError(f"No data file found in {model_dir}")
    
    df = load_dataframe(target)
    if date_cols:
        df = ensure_datetime(df, date_cols)
    return df


def validate_columns(df: pd.DataFrame, required: List[str]):
    """Validate that required columns exist in the dataframe."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ColumnNotFoundError(f"Missing columns: {missing}")
