"""1단계 확인용 테스트 — 서버가 뜨고 /health 가 응답하는지.

실행:  pytest        (backend/ 안에서, .venv 활성화 상태로)

★ TestClient 는 실제 서버를 띄우지 않고 앱을 직접 호출한다.
  uvicorn 을 켜둘 필요가 없어서 빠르다.

다음 단계 테스트를 추가할 자리:
  - test_security.py  (2단계) — create_token → verify_token 왕복, 위조 토큰 거부, 만료 처리
  - test_markdown.py  (4단계) — build_filename / build_note / extract_summary
                                외부 호출이 없는 순수 함수라 가장 쓰기 쉽다. 여기부터 시작할 것
  - test_intent.py    (4단계) — URL/길이/의문표현 각 분기. LLM 폴백은 모킹
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_responds():
    res = client.get("/health")
    assert res.status_code == 200
    # 환경변수가 안 채워졌으면 "misconfigured" 가 정상 — status 값 자체는 단정하지 않는다
    assert res.json()["status"] in ("ok", "misconfigured")


def test_health_reports_missing_env():
    """missing_env 는 항상 리스트여야 한다 (프론트/스크립트가 length 를 볼 수 있게)."""
    res = client.get("/health")
    assert isinstance(res.json()["missing_env"], list)
