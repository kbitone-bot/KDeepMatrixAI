import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from backend.services.ram_service import RAMAnalysisService
from backend.services.life_service import LifeAnalysisService
from backend.services.sim_service import SimAnalysisService
from backend.services.recommend_service import RecommendAnalysisService
from backend.services.imqc_service import IMQCAnalysisService


class TestRAMService:
    """af_ba_req_001 장비운용가용도분석 테스트"""

    def test_ram_single_pn_single_unit(self):
        service = RAMAnalysisService()
        params = {
            "mode": "수리",
            "no_pn": "부품번호00001",
            "no_pclrt_idno": "ATN-00073737",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }
        result = service.analyze(params)
        assert result.status == "success", f"Failed: {result.message}"
        assert result.metrics is not None
        summary = result.metrics.get("summary", [])
        assert len(summary) > 0
        assert "mtbf" in summary[0]
        assert "availability" in summary[0]
        assert summary[0]["best_tbf_dist"] in ["Weibull", "LogNormal", "Exponential", None]

    def test_ram_single_pn_all_units(self):
        service = RAMAnalysisService()
        params = {
            "mode": "수리",
            "no_pn": "부품번호00001",
            "no_pclrt_idno": None,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }
        result = service.analyze(params)
        assert result.status == "success"
        assert len(result.charts) >= 2  # RAM curves + availability

    def test_ram_adjust_mode(self):
        service = RAMAnalysisService()
        params = {
            "mode": "조절",
            "no_pn": "부품번호00001",
            "no_pclrt_idno": "ATN-00073737",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }
        result = service.analyze(params)
        assert result.status == "success"


class TestLifeService:
    """af_ba_req_002 장비수명예측 테스트"""

    def test_life_single_pn(self):
        service = LifeAnalysisService()
        params = {"pn": "부품번호00001"}
        result = service.analyze(params)
        assert result.status == "success", f"Failed: {result.message}"
        assert result.metrics is not None
        summary = result.metrics.get("summary", [])
        assert len(summary) > 0
        assert "expected_lifetime" in summary[0]
        assert "lifetime_10p" in summary[0]
        assert "lifetime_50p" in summary[0]
        assert summary[0]["best_dist"] in ["norm", "expon", "weibull_min"]
        assert len(result.charts) > 0  # PDF + CDF charts

    def test_life_all_pn(self):
        service = LifeAnalysisService()
        params = {"pn": None}
        result = service.analyze(params)
        assert result.status == "success"
        summary = result.metrics.get("summary", [])
        assert len(summary) > 0  # At least one part analyzed


class TestSimService:
    """af_ba_req_004 시험소작업량예측 테스트 (AI Serving)"""

    def test_sim_prediction_basic(self):
        service = SimAnalysisService()
        params = {
            "stl_num": "시험소008",
            "difficulty": "A",
            "tech_grade": "2C",
            "efficiency": 80,
            "maint_cycle": 12,
            "cons_mh": 100,
        }
        result = service.analyze(params)
        assert result.status == "success", f"Failed: {result.message}"
        assert result.metrics is not None
        assert "y_pred" in result.metrics
        assert "pi_lower" in result.metrics
        assert "pi_upper" in result.metrics
        assert result.metrics["y_pred"] > 0
        assert result.metrics["pi_lower"] <= result.metrics["y_pred"] <= result.metrics["pi_upper"]

    def test_sim_prediction_different_labs(self):
        service = SimAnalysisService()
        for lab in ["시험소008", "시험소010"]:
            params = {
                "stl_num": lab,
                "difficulty": "B",
                "tech_grade": "1C",
                "efficiency": 75,
                "maint_cycle": 6,
                "cons_mh": 150,
            }
            result = service.analyze(params)
            assert result.status == "success", f"Failed for {lab}: {result.message}"


class TestRecommendService:
    """af_ba_req_005 유사부품추천 테스트 (AI Serving)"""

    def test_recommend_basic(self):
        service = RecommendAnalysisService()
        params = {"part_no": "75(0-6)KG-B", "topn": 5}
        result = service.analyze(params)
        assert result.status == "success", f"Failed: {result.message}"
        assert result.metrics is not None
        assert "recommendation_count" in result.metrics
        assert result.metrics["recommendation_count"] == 5
        assert "cluster" in result.metrics
        assert result.metrics["cluster"] >= 0
        assert result.summary_csv is not None

    def test_recommend_different_parts(self):
        service = RecommendAnalysisService()
        # 005 학습 데이터에 존재하는 부품번호 (train_005.py로 확인된 번호)
        test_parts = ["75(0-6)KG-B"]
        for part in test_parts:
            params = {"part_no": part, "topn": 3}
            result = service.analyze(params)
            assert result.status == "success", f"Failed for {part}: {result.message}"


class TestIMQCService:
    """af_ba_req_007 IMQC인원수급분석 테스트"""

    def test_imqc_basic(self):
        service = IMQCAnalysisService()
        params = {"year": 2025, "month": 1}
        result = service.analyze(params)
        assert result.status == "success", f"Failed: {result.message}"
        assert result.metrics is not None
        assert "current_total" in result.metrics
        assert "required_total" in result.metrics
        assert "comparison" in result.metrics
        assert len(result.metrics["current_total"]) > 0
        assert result.summary_csv is not None

    def test_imqc_different_months(self):
        service = IMQCAnalysisService()
        for month in [1, 6, 12]:
            params = {"year": 2025, "month": month}
            result = service.analyze(params)
            assert result.status == "success", f"Failed for month {month}: {result.message}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


class TestAIServingPerformance:
    """AI Serving 모델 성능/지연 테스트"""

    def test_sim_latency(self):
        """004: 10회 연속 예측 평균 응답 시간 < 3초"""
        import time
        service = SimAnalysisService()
        params = {
            "stl_num": "시험소008",
            "difficulty": "A",
            "tech_grade": "2C",
            "efficiency": 80,
            "maint_cycle": 12,
            "cons_mh": 100,
        }
        times = []
        for _ in range(10):
            t0 = time.time()
            result = service.analyze(params)
            t1 = time.time()
            assert result.status == "success"
            times.append(t1 - t0)
        avg_time = sum(times) / len(times)
        print(f"\n   004 avg latency: {avg_time:.3f}s (max: {max(times):.3f}s)")
        assert avg_time < 3.0, f"Average latency {avg_time:.3f}s exceeds 3s threshold"

    def test_recommend_latency(self):
        """005: 10회 연속 추천 평균 응답 시간 < 3초"""
        import time
        service = RecommendAnalysisService()
        params = {"part_no": "75(0-6)KG-B", "topn": 5}
        times = []
        for _ in range(10):
            t0 = time.time()
            result = service.analyze(params)
            t1 = time.time()
            assert result.status == "success"
            times.append(t1 - t0)
        avg_time = sum(times) / len(times)
        print(f"\n   005 avg latency: {avg_time:.3f}s (max: {max(times):.3f}s)")
        assert avg_time < 3.0, f"Average latency {avg_time:.3f}s exceeds 3s threshold"
