"""2단계 — 인증 엔드포인트 + 프론트 계약.

★ 여기서 지키려는 건 "파이썬 코드가 맞게 도나"가 아니라
  "프론트가 기대하는 대로 응답하나"다. 프론트는 안 고치기로 했으므로
  계약이 깨지면 화면이 조용히 잘못 동작한다.
"""

from fastapi.testclient import TestClient

from app.core.security import TOKEN_COOKIE
from app.main import app
from tests.conftest import TEST_PASSWORD

client = TestClient(app)


def test_login_sets_httponly_cookie():
    res = client.post("/api/auth", json={"password": TEST_PASSWORD})
    assert res.status_code == 200
    assert res.json()["success"] is True

    cookie_header = res.headers["set-cookie"]
    assert TOKEN_COOKIE in cookie_header
    assert "HttpOnly" in cookie_header  # JS 에서 못 읽어야 한다 (XSS 방어)
    assert "Secure" not in cookie_header  # 개발 환경에서는 꺼져 있어야 로컬 http 에서 저장된다


def test_login_rejects_wrong_password():
    res = client.post("/api/auth", json={"password": "틀린비번"})
    assert res.status_code == 401


def test_check_returns_401_when_unauthenticated():
    """★ page.tsx:15 가 `if (res.ok)` 로 상태 코드만 본다.

    여기서 200 을 돌려주면 로그인 화면이 영영 안 뜬다.
    """
    fresh = TestClient(app)
    assert fresh.get("/api/auth/check").status_code == 401


def test_check_returns_200_after_login():
    session = TestClient(app)
    session.post("/api/auth", json={"password": TEST_PASSWORD})
    res = session.get("/api/auth/check")
    assert res.status_code == 200
    assert res.json()["authenticated"] is True
