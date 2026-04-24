import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from backend.utils.data_loader import load_ram_data
from backend.utils.date_utils import convert_mixed_dates

print("1. Testing data loader...")
model_dir = PROJECT_ROOT / "af_ba_req_001"
df = load_ram_data(model_dir, date_cols=["mntnc_reqstdt", "rels_dhm"])
print(f"   Loaded {len(df)} rows, columns: {list(df.columns)}")

print("2. Testing date conversion...")
s = pd.Series([45320, "2024-01-01", None])
result = convert_mixed_dates(s)
print(f"   Converted: {list(result)}")

print("3. Testing RAM service - single unit...")
from backend.services.ram_service import RAMAnalysisService
service = RAMAnalysisService()
params = {
    "mode": "수리",
    "no_pn": "부품번호00001",
    "no_pclrt_idno": "ATN-00073737",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
}
result = service.analyze(params)
print(f"   Status: {result.status}, Message: {result.message}")
if result.status == "success":
    summary = result.metrics.get("summary", [])
    if summary:
        print(f"   Metrics: {summary[0]}")

print("4. Testing RAM service - single pn (all units)...")
params2 = {
    "mode": "수리",
    "no_pn": "부품번호00001",
    "no_pclrt_idno": None,
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
}
result2 = service.analyze(params2)
print(f"   Status: {result2.status}, Message: {result2.message}")
if result2.status == "success":
    summary = result2.metrics.get("summary", [])
    if summary:
        print(f"   Metrics: {summary[0]}")
    print(f"   Charts: {result2.charts}")

print("5. Testing RAM service - 조절 mode...")
params3 = {
    "mode": "조절",
    "no_pn": "부품번호00001",
    "no_pclrt_idno": "ATN-00073737",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
}
result3 = service.analyze(params3)
print(f"   Status: {result3.status}, Message: {result3.message}")
if result3.status == "success":
    summary = result3.metrics.get("summary", [])
    if summary:
        print(f"   Metrics: {summary[0]}")

print("All quick tests completed!")
