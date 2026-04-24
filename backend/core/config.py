import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIRS = [d for d in PROJECT_ROOT.iterdir() if d.is_dir() and d.name.startswith("af_ba_req_")]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

MODEL_NAMES = {
    "af_ba_req_001": "장비운용가용도분석 (RAM)",
    "af_ba_req_002": "장비수명예측",
    "af_ba_req_004": "시험소작업량예측",
    "af_ba_req_005": "기술검토자동처리",
    "af_ba_req_007": "IMQC인원수급분석",
}

VALID_CODES = ["F", "G", "J", "K"]
CODE_MAP = {"C": "J", "H": "J", "S": "J", "L": "K"}
