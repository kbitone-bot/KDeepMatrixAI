import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import subprocess
import time
import urllib.request


class TestStreamlitUI:
    """Streamlit UI 로드 및 응답 테스트"""

    @pytest.fixture(scope="class")
    def streamlit_process(self):
        """Streamlit 서버를 백그라운드에서 실행"""
        proc = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app/app.py",
             "--server.headless", "true", "--server.port", "8502"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # 서버 기동 대기
        for _ in range(30):
            try:
                urllib.request.urlopen("http://localhost:8502/_stcore/health", timeout=1)
                break
            except Exception:
                time.sleep(1)
        else:
            proc.terminate()
            raise RuntimeError("Streamlit server failed to start")
        yield proc
        proc.terminate()
        proc.wait(timeout=10)

    def test_health_endpoint(self, streamlit_process):
        """Health check 엔드포인트 응답 확인"""
        resp = urllib.request.urlopen("http://localhost:8502/_stcore/health", timeout=5)
        assert resp.status == 200
        body = resp.read().decode()
        assert body == "ok"

    def test_main_page_loads(self, streamlit_process):
        """메인 페이지 HTML 로드 확인 (Streamlit SPA shell)"""
        resp = urllib.request.urlopen("http://localhost:8502", timeout=10)
        assert resp.status == 200
        html = resp.read().decode()
        # Streamlit은 SPA이므로 초기 HTML은 JS shell
        assert "<title>Streamlit</title>" in html
        assert 'id="root"' in html
        assert "You need to enable JavaScript" in html

    def test_page_contains_model_selector(self, streamlit_process):
        """Streamlit JS 번들 로드 확인"""
        resp = urllib.request.urlopen("http://localhost:8502", timeout=10)
        html = resp.read().decode()
        assert "static/js/main" in html
        assert "static/css/main" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
