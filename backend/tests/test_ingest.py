"""저장 파이프라인 — 어댑터를 가짜로 갈아끼워 네트워크 없이 돌린다.

★ 여기서 지키는 건 '부분 실패 허용'이다. 두 저장소 중 하나가 죽어도
  나머지는 저장돼야 하고, 무엇이 실패했는지 결과에 남아야 한다.
  나중에 누가 두 저장을 asyncio.gather 로 묶으면 이 테스트가 잡아준다
  (gather 기본 동작은 하나가 터지면 나머지를 취소한다).
"""

import pytest

from app.schemas.chat import NoteHit, SummaryResult
from app.services import ingest

SUMMARY = SummaryResult(
    title="메타하네스 정리",
    summary="요약 본문.",
    tags=["ai", "agent"],
    category="concepts",
)


@pytest.fixture
def fake_adapters(monkeypatch):
    """어댑터 셋을 전부 가짜로. 호출 기록을 남겨 순서와 인자를 검사한다."""
    calls = {"github": [], "upsert": [], "related": []}

    async def fake_summarize(text):
        return SUMMARY

    async def fake_find_related(text, top_k=3):
        calls["related"].append(text)
        return [
            NoteHit(title="관련노트A", path="concepts/a.md", score=0.81),
            NoteHit(title="점수미달", path="concepts/b.md", score=0.40),
        ]

    async def fake_save(*, path, content, message):
        calls["github"].append({"path": path, "content": content})

    async def fake_upsert(*, title, path, summary):
        calls["upsert"].append({"path": path, "summary": summary})

    monkeypatch.setattr(ingest.gemini, "summarize", fake_summarize)
    monkeypatch.setattr(ingest.pinecone, "find_related", fake_find_related)
    monkeypatch.setattr(ingest.github, "save", fake_save)
    monkeypatch.setattr(ingest.pinecone, "upsert_note", fake_upsert)
    return calls


def _boom(message="터짐"):
    async def _raise(*args, **kwargs):
        raise RuntimeError(message)

    return _raise


async def test_path_includes_category_folder(fake_adapters):
    """★ category 가 폴더로 들어가야 한다.

    빠지면 노트가 레포 루트에 저장된다. 저장은 성공하고 아무것도 안 터지지만,
    github.list_notes() 가 세 폴더만 훑기 때문에 재색인에서 영영 사라진다.
    """
    await ingest.ingest("메타하네스에 대한 메모")

    path = fake_adapters["github"][0]["path"]
    assert path.startswith("concepts/"), f"폴더 없이 저장됨: {path}"
    assert path.endswith(".md")
    # 벡터에 넣는 path 도 같아야 한다 — 다르면 원본을 못 찾는다
    assert fake_adapters["upsert"][0]["path"] == path


async def test_embeds_summary_not_original(fake_adapters):
    """small-to-big — 벡터에는 요약이 들어간다. 원본은 GitHub 에."""
    original = "아주 긴 원문 " * 50
    await ingest.ingest(original)

    assert fake_adapters["upsert"][0]["summary"] == SUMMARY.summary
    assert original not in fake_adapters["upsert"][0]["summary"]
    # 원문은 노트 본문에 그대로 들어간다
    assert original in fake_adapters["github"][0]["content"]


async def test_related_search_uses_summary_and_filters_by_score(fake_adapters):
    """관련 노트는 요약으로 찾고, 임계값 미만은 버린다."""
    result = await ingest.ingest("메모")

    assert fake_adapters["related"] == [SUMMARY.summary]  # 원문이 아니라 요약
    assert result.related == ["관련노트A"]  # 0.40 짜리는 걸러짐
    assert "[[관련노트A]]" in fake_adapters["github"][0]["content"]


async def test_related_lookup_failure_does_not_block_saving(fake_adapters, monkeypatch):
    """★ 관련 노트 검색 실패는 저장 실패가 아니다.

    vector.error 에 담으면 "저장은 됐는데 에러도 있는" 모순 상태가 된다.
    """
    monkeypatch.setattr(ingest.pinecone, "find_related", _boom())
    result = await ingest.ingest("메모")

    assert result.related_lookup_failed is True
    assert result.related == []
    assert result.github.ok is True
    assert result.vector.ok is True
    assert result.vector.error == ""  # ★ 검색 실패가 저장 에러로 새면 안 된다


async def test_summarize_failure_propagates(fake_adapters, monkeypatch):
    """요약이 실패하면 제목도 본문도 없다 — 예외를 그대로 올린다."""
    monkeypatch.setattr(ingest.gemini, "summarize", _boom("Gemini 429"))
    with pytest.raises(RuntimeError):
        await ingest.ingest("메모")


# --- 부분 실패 4분기 -------------------------------------------------


async def test_both_saves_succeed(fake_adapters):
    result = await ingest.ingest("메모")
    assert (result.github.ok, result.vector.ok) == (True, True)
    assert result.github.error == "" and result.vector.error == ""


async def test_github_fails_vector_survives(fake_adapters, monkeypatch):
    """★ GitHub 이 죽어도 벡터 저장은 시도된다."""
    monkeypatch.setattr(ingest.github, "save", _boom("GitHub API error 403: rate limit"))
    result = await ingest.ingest("메모")

    assert result.github.ok is False
    assert "한도를 초과" in result.github.error  # 사용자용 문구로 변환됐다
    assert result.vector.ok is True  # ← gather 로 묶으면 여기가 깨진다
    assert len(fake_adapters["upsert"]) == 1


async def test_vector_fails_github_survives(fake_adapters, monkeypatch):
    monkeypatch.setattr(ingest.pinecone, "upsert_note", _boom("dimension mismatch"))
    result = await ingest.ingest("메모")

    assert result.github.ok is True
    assert result.vector.ok is False
    assert "차원" in result.vector.error
    assert len(fake_adapters["github"]) == 1


async def test_both_fail_reports_both_errors(fake_adapters, monkeypatch):
    monkeypatch.setattr(ingest.github, "save", _boom("GitHub API error 401"))
    monkeypatch.setattr(ingest.pinecone, "upsert_note", _boom("Unauthorized"))
    result = await ingest.ingest("메모")

    assert (result.github.ok, result.vector.ok) == (False, False)
    assert result.github.error and result.vector.error
    assert result.github.error != result.vector.error  # 서로 다른 안내가 나와야 한다
