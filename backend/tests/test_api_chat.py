"""채팅 엔드포인트 — 인증, 분기, 예외 → 문구 변환.

★ 여기서 지키는 건 **프론트 계약**이다.
  ChatWindow.tsx 는 401 이면 새로고침하고, 그 외에는 응답의 reply 를 말풍선에 렌더한다.
  그래서 실패해도 200 + 안내 문구여야 사용자가 원인을 본다.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ingest import IngestResult, SaveOutcome
from tests.conftest import TEST_PASSWORD


@pytest.fixture
def client(monkeypatch):
    """로그인된 클라이언트 + 서비스 계층을 가짜로."""
    session = TestClient(app)
    session.post("/api/auth", json={"password": TEST_PASSWORD})
    return session


def test_requires_auth():
    """쿠키 없으면 401 — 프론트가 상태 코드로 로그인 화면을 띄운다."""
    assert TestClient(app).post("/api/chat", json={"message": "안녕"}).status_code == 401


def test_rejects_empty_message(client):
    """ChatRequest(min_length=1) — 형식 오류는 핸들러 전에 걸린다."""
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


def test_question_returns_retrieval_answer(client, monkeypatch):
    from app.api import chat as chat_api

    async def fake_classify(msg):
        return "question"

    async def fake_answer(q):
        return "노트 기반 답변"

    monkeypatch.setattr(chat_api.intent_service, "classify", fake_classify)
    monkeypatch.setattr(chat_api.retrieval, "answer", fake_answer)

    res = client.post("/api/chat", json={"message": "메타하네스가 뭐야?"})
    assert res.status_code == 200
    assert res.json()["reply"] == "노트 기반 답변"


def test_save_formats_partial_failure(client, monkeypatch):
    """★ 저장 4분기 — GitHub 만 성공했으면 그 사실과 벡터 에러가 둘 다 보여야 한다."""
    from app.api import chat as chat_api

    async def fake_classify(msg):
        return "save"

    async def fake_ingest(msg):
        return IngestResult(
            title="제목",
            summary="요약",
            category="concepts",
            tags=["a", "b"],
            related=["관련노트"],
            github=SaveOutcome(ok=True),
            vector=SaveOutcome(ok=False, error="⚠️ Pinecone 키가 유효하지 않습니다."),
        )

    monkeypatch.setattr(chat_api.intent_service, "classify", fake_classify)
    monkeypatch.setattr(chat_api.ingest_service, "ingest", fake_ingest)

    reply = client.post("/api/chat", json={"message": "메모"}).json()["reply"]
    assert "**제목**" in reply
    assert "#a #b" in reply
    assert "[[관련노트]]" in reply
    assert "GitHub 저장 완료" in reply
    assert "Pinecone 키가 유효하지 않습니다" in reply  # 실패도 반드시 보여야 한다
    assert "저장 완료 (GitHub + 벡터DB)" not in reply


def test_service_error_returns_200_with_message(client, monkeypatch):
    """★ 500 을 던지지 않는다.

    프론트가 reply 를 말풍선에 그대로 렌더하므로, 500 이면 사용자는 원인을 못 본다.
    """
    from app.api import chat as chat_api

    async def boom(msg):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(chat_api.intent_service, "classify", boom)

    res = client.post("/api/chat", json={"message": "메모"})
    assert res.status_code == 200
    assert "사용량이 소진" in res.json()["reply"]


def test_detects_service_from_exception(client, monkeypatch):
    """retrieval 안에서 GitHub 이 터지면 GitHub 안내가 나와야 한다."""
    from app.api import chat as chat_api

    async def fake_classify(msg):
        return "question"

    async def boom(q):
        raise RuntimeError("GitHub API error 401 (load x.md): Bad credentials")

    monkeypatch.setattr(chat_api.intent_service, "classify", fake_classify)
    monkeypatch.setattr(chat_api.retrieval, "answer", boom)

    reply = client.post("/api/chat", json={"message": "질문?"}).json()["reply"]
    assert "GitHub 토큰이 만료" in reply
