import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from datetime import datetime
from backend.services.ram_service import RAMAnalysisService
from backend.utils.data_loader import load_ram_data, validate_columns
from backend.utils.date_utils import convert_mixed_dates
from backend.core.exceptions import DataLoadError, ColumnNotFoundError


def test_load_ram_data():
    model_dir = PROJECT_ROOT / "af_ba_req_001"
    df = load_ram_data(model_dir, date_cols=["mntnc_reqstdt", "rels_dhm"])
    assert not df.empty
    assert "pn" in df.columns
    assert "mntnc_rslt_actn_cd" in df.columns
    print(f"Loaded {len(df)} rows")


def test_convert_mixed_dates():
    s = pd.Series([45320, "2024-01-01", None])
    result = convert_mixed_dates(s)
    assert pd.notna(result.iloc[0])
    assert pd.notna(result.iloc[1])
    assert pd.isna(result.iloc[2])


def test_ram_service_full():
    service = RAMAnalysisService()
    params = {
        "mode": "수리",
        "no_pn": "부품번호00001",
        "no_pclrt_idno": "ATN-00073737",
        "start_date": "2021-01-01",
        "end_date": "2025-12-31",
    }
    result = service.analyze(params)
    assert result.status == "success", result.message
    assert result.metrics is not None
    summary = result.metrics.get("summary", [])
    assert len(summary) > 0
    metrics = summary[0]
    assert "mtbf" in metrics
    assert "mttr" in metrics
    assert "availability" in metrics
    assert 0 <= metrics["availability"] <= 1
    print(f"RAM Result: {metrics}")


def test_ram_service_all_pn():
    service = RAMAnalysisService()
    params = {
        "mode": "수리",
        "no_pn": None,
        "no_pclrt_idno": None,
        "start_date": "2021-01-01",
        "end_date": "2022-02-20",
    }
    result = service.analyze(params)
    assert result.status == "success", result.message
    print(f"All PN Result: {result.message}")


if __name__ == "__main__":
    test_load_ram_data()
    test_convert_mixed_dates()
    test_ram_service_full()
    test_ram_service_all_pn()
    print("All tests passed!")
