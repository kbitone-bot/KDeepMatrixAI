import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for Fitter in tests
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


class TestAPIModels:
    """GET /api/v1/models 테스트"""

    def test_get_models(self):
        response = client.get("/api/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 5
        model_ids = [m["model_id"] for m in data]
        assert "af_ba_req_001" in model_ids
        assert "af_ba_req_004" in model_ids
        assert "af_ba_req_005" in model_ids


class TestAPIAnalyzeRAM:
    """POST /api/v1/analyze/ram 테스트"""

    def test_analyze_ram_success(self):
        response = client.post("/api/v1/analyze/ram", json={
            "mode": "수리",
            "no_pn": "부품번호00001",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["model_id"] == "af_ba_req_001"
        assert "metrics" in data

    def test_analyze_ram_invalid_mode(self):
        response = client.post("/api/v1/analyze/ram", json={
            "mode": "INVALID",
            "no_pn": "부품번호00001",
        })
        assert response.status_code == 422  # Validation error


class TestAPIAnalyzeLife:
    """POST /api/v1/analyze/life 테스트"""

    def test_analyze_life_success(self):
        response = client.post("/api/v1/analyze/life", json={
            "pn": "부품번호01217",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["model_id"] == "af_ba_req_002"

    def test_analyze_life_all_pn(self):
        response = client.post("/api/v1/analyze/life", json={
            "pn": "부품번호00593",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


class TestAPIAnalyzeSim:
    """POST /api/v1/analyze/{model_id} — 004 테스트"""

    def test_analyze_sim_success(self):
        response = client.post("/api/v1/analyze/af_ba_req_004", json={
            "stl_num": "시험소008",
            "difficulty": "A",
            "tech_grade": "2C",
            "efficiency": 80,
            "maint_cycle": 12,
            "cons_mh": 100,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["model_id"] == "af_ba_req_004"
        assert "metrics" in data
        metrics = data["metrics"]
        assert "y_pred" in metrics
        assert "pi_lower" in metrics
        assert "pi_upper" in metrics


class TestAPIAnalyzeRecommend:
    """POST /api/v1/analyze/{model_id} — 005 테스트"""

    def test_analyze_recommend_success(self):
        response = client.post("/api/v1/analyze/af_ba_req_005", json={
            "part_no": "75(0-6)KG-B",
            "topn": 5,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["model_id"] == "af_ba_req_005"


class TestAPIAnalyzeIMQC:
    """POST /api/v1/analyze/imqc 테스트"""

    def test_analyze_imqc_success(self):
        response = client.post("/api/v1/analyze/imqc", json={
            "year": 2025,
            "month": 1,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["model_id"] == "af_ba_req_007"


class TestAPINotFound:
    """존재하지 않는 모델 테스트"""

    def test_analyze_unknown_model(self):
        response = client.post("/api/v1/analyze/af_ba_req_999", json={})
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
