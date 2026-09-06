"""테스트 공통 설정.

★ backend/.env 에는 **실서비스 키**가 들어 있다.
  테스트가 그 값을 그대로 쓰면 실수로 진짜 API를 부른다.
  실제로 그런 일이 있었다 — test_intent.py 의 strip 테스트가 어댑터를 모킹하지
  않아서 매 실행마다 Gemini 를 호출하고 있었다. "61 passed" 가 네트워크와
  실키에 의존하고 있었던 것이다.

  그래서 외부 서비스 키를 **전부** 가짜로 덮는다. 어댑터를 monkeypatch 하지 않은
  테스트가 새로 생기면 조용히 새는 대신 **즉시 인증 오류로 실패**한다.
  환경변수가 .env 파일보다 우선순위가 높다.
"""

import pytest

from app.adapters import gemini, github, pinecone
from app.config import get_settings

TEST_PASSWORD = "test-password"
TEST_SECRET = "test-secret-key"


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    monkeypatch.setenv("AUTH_PASSWORD", TEST_PASSWORD)
    monkeypatch.setenv("AUTH_SECRET", TEST_SECRET)
    monkeypatch.setenv("APP_ENV", "development")

    # ★ 외부 서비스 키 — 실키가 새는 걸 구조적으로 막는다
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GITHUB_TOKEN", "test-github-token")
    monkeypatch.setenv("GITHUB_REPO", "test-owner/test-repo")
    monkeypatch.setenv("PINECONE_API_KEY", "test-pinecone-key")
    monkeypatch.setenv("PINECONE_INDEX", "test-index")

    # 어댑터는 @lru_cache 로 클라이언트를 들고 있다. 비워야 가짜 키가 반영된다.
    for mod in (gemini, pinecone, github):
        for fn in ("_client", "_index"):
            if hasattr(mod, fn):
                getattr(mod, fn).cache_clear()
    # @lru_cache 라 한 번 만들어진 Settings 가 계속 재사용된다 → 비워야 새 값이 반영된다.
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
