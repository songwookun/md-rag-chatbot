"""재색인 / 외부 수집 엔드포인트."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ingest import IngestResult, SaveOutcome
from tests.conftest import TEST_PASSWORD

NOTE_WITH_SUMMARY = "---\ntitle: x\n---\n\n# 제목\n\n## 요약\n요약 본문\n\n## 원본\n원문"
NOTE_OLD_FORMAT = "# 옛 노트\n요약 섹션이 없다"


@pytest.fixture
def client():
    session = TestClient(app)
    session.post("/api/auth", json={"password": TEST_PASSWORD})
    return session


# --- sync ------------------------------------------------------------


async def test_sync_requires_auth():
    assert TestClient(app).post("/api/sync").status_code == 401


def test_sync_does_not_clear_index_when_no_notes(client, monkeypatch):
    """★ 이 파일에서 가장 중요한 테스트.

    노트를 0개 읽어왔을 때 그게 '노트가 없는 것'인지 'GitHub 읽기 실패'인지
    구분할 수 없다. clear_index 를 부르면 멀쩡한 벡터DB가 통째로 날아간다.
    """
    from app.api import sync as sync_api

    cleared = []

    async def no_notes(limit=30):
        return []

    async def fake_clear():
        cleared.append(True)

    monkeypatch.setattr(sync_api.github, "get_all_contents", no_notes)
    monkeypatch.setattr(sync_api.pinecone, "clear_index", fake_clear)

    body = client.post("/api/sync").json()
    assert cleared == []  # ← 여기가 깨지면 데이터가 날아간다
    assert body["total"] == 0 and body["synced"] == 0


def test_sync_skips_notes_without_summary(client, monkeypatch):
    """'## 요약' 이 없는 옛 노트는 실패가 아니라 스킵이다."""
    from app.api import sync as sync_api

    upserted = []

    async def notes(limit=30):
        return [
            {"name": "새노트", "path": "concepts/new.md", "content": NOTE_WITH_SUMMARY},
            {"name": "옛노트", "path": "concepts/old.md", "content": NOTE_OLD_FORMAT},
        ]

    async def fake_clear():
        pass

    async def fake_upsert(*, title, path, summary):
        upserted.append((path, summary))

    monkeypatch.setattr(sync_api.github, "get_all_contents", notes)
    monkeypatch.setattr(sync_api.pinecone, "clear_index", fake_clear)
    monkeypatch.setattr(sync_api.pinecone, "upsert_note", fake_upsert)

    body = client.post("/api/sync").json()
    assert (body["synced"], body["skipped"], body["failed"]) == (1, 1, 0)
    assert body["total"] == 2
    # 노트 안에 적힌 요약을 그대로 쓴다 — Gemini 재호출 없음
    assert upserted == [("concepts/new.md", "요약 본문")]


def test_sync_continues_after_single_failure(client, monkeypatch):
    """노트 하나가 실패해도 나머지는 색인된다."""
    from app.api import sync as sync_api

    async def notes(limit=30):
        return [
            {"name": f"n{i}", "path": f"concepts/{i}.md", "content": NOTE_WITH_SUMMARY}
            for i in range(3)
        ]

    async def fake_clear():
        pass

    async def flaky(*, title, path, summary):
        if path == "concepts/1.md":
            raise RuntimeError("일시 오류")

    monkeypatch.setattr(sync_api.github, "get_all_contents", notes)
    monkeypatch.setattr(sync_api.pinecone, "clear_index", fake_clear)
    monkeypatch.setattr(sync_api.pinecone, "upsert_note", flaky)

    body = client.post("/api/sync").json()
    assert (body["synced"], body["failed"]) == (2, 1)


# --- collect ---------------------------------------------------------


def test_collect_requires_bearer_header():
    """쿠키가 아니라 헤더로 인증한다 — 브라우저가 아니라 외부 도구가 부른다."""
    anon = TestClient(app)
    assert anon.post("/api/collect", json={"content": "메모"}).status_code == 401
    # 값이 틀린 경우도 401. (HTTP 헤더는 non-ASCII 를 못 실으므로 ASCII 로 쓴다)
    assert (
        anon.post(
            "/api/collect",
            json={"content": "메모"},
            headers={"Authorization": "Bearer wrong-password"},
        ).status_code
        == 401
    )


def test_collect_indexes_to_vector_db(monkeypatch):
    """★ TS 원본의 버그가 사라졌는지 확인.

    원본 collect 는 GitHub 저장만 하고 Pinecone upsert 를 빠뜨렸다.
    그래서 단축어로 넣은 노트는 검색이 안 됐다.
    같은 ingest() 를 부르면 구조적으로 그럴 수 없다.
    """
    from app.api import collect as collect_api

    called = []

    async def fake_ingest(content):
        called.append(content)
        return IngestResult(
            title="제목",
            summary="요약",
            category="articles",
            tags=["t"],
            github=SaveOutcome(ok=True),
            vector=SaveOutcome(ok=True),
        )

    monkeypatch.setattr(collect_api.ingest_service, "ingest", fake_ingest)

    res = TestClient(app).post(
        "/api/collect",
        json={"content": "https://example.com 저장해"},
        headers={"Authorization": f"Bearer {TEST_PASSWORD}"},
    )
    body = res.json()
    assert res.status_code == 200
    assert called == ["https://example.com 저장해"]
    assert body["saved"] is True
    assert body["indexed"] is True  # ← TS 에는 없던 값


def test_collect_reports_partial_failure_with_200(monkeypatch):
    """저장이 실패해도 200 — 외부 도구가 재시도해서 노트가 두 개 생기면 안 된다."""
    from app.api import collect as collect_api

    async def fake_ingest(content):
        return IngestResult(
            title="제목",
            summary="요약",
            category="articles",
            tags=[],
            github=SaveOutcome(ok=False, error="⚠️ GitHub 토큰이 만료되었습니다."),
            vector=SaveOutcome(ok=True),
        )

    monkeypatch.setattr(collect_api.ingest_service, "ingest", fake_ingest)

    res = TestClient(app).post(
        "/api/collect",
        json={"content": "메모"},
        headers={"Authorization": f"Bearer {TEST_PASSWORD}"},
    )
    assert res.status_code == 200
    assert res.json()["saved"] is False
    assert res.json()["indexed"] is True
