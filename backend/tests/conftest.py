"""테스트 공통 설정.

★ backend/.env 에는 **실서비스 키**가 들어 있다.
  테스트가 그 값을 그대로 쓰면 실수로 진짜 API를 부를 수 있으므로,
  여기서 가짜 값으로 덮어쓴다. 환경변수가 .env 파일보다 우선순위가 높다.
"""

import pytest

from app.config import get_settings

TEST_PASSWORD = "test-password"
TEST_SECRET = "test-secret-key"


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    monkeypatch.setenv("AUTH_PASSWORD", TEST_PASSWORD)
    monkeypatch.setenv("AUTH_SECRET", TEST_SECRET)
    monkeypatch.setenv("APP_ENV", "development")
    # @lru_cache 라 한 번 만들어진 Settings 가 계속 재사용된다 → 비워야 새 값이 반영된다.
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
