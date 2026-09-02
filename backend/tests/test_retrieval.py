"""RAG 검색 → 답변 — 네트워크 없이 abstention 을 검증한다.

★ 제일 중요한 건 "근거가 없으면 LLM 을 아예 부르지 않는다"이다.
  이게 깨지면 챗봇은 여전히 답을 하지만 **저장하지 않은 내용을 지어내기 시작한다.**
  터지지 않으므로 테스트가 없으면 영영 모른다.
"""

import pytest

from app.schemas.chat import NoteHit
from app.services import retrieval

ABOVE = retrieval.SCORE_THRESHOLD + 0.05
BELOW = retrieval.SCORE_THRESHOLD - 0.05


@pytest.fixture
def fake(monkeypatch):
    """어댑터를 가짜로. 호출 기록으로 '무엇을 안 불렀는지'까지 검사한다."""
    calls = {"loaded": [], "answered": []}
    state = {"hits": [], "contents": {}}

    async def fake_query(question, top_k=5):
        return state["hits"]

    async def fake_get_content(path):
        calls["loaded"].append(path)
        content = state["contents"].get(path)
        if content is None:
            raise RuntimeError(f"GitHub API error 404: {path}")
        return content

    async def fake_answer(question, notes):
        calls["answered"].append(notes)
        return "생성된 답변"

    monkeypatch.setattr(retrieval.pinecone, "query", fake_query)
    monkeypatch.setattr(retrieval.github, "get_content", fake_get_content)
    monkeypatch.setattr(retrieval.gemini, "answer_from_notes", fake_answer)
    return calls, state


async def test_abstains_and_never_calls_llm_when_all_below_threshold(fake):
    """★ 이 파일에서 가장 중요한 테스트.

    임계값에 다 걸리면 보류 문구를 돌려주고, **LLM 을 부르지 않는다.**
    실험②에서 0.6 일 때 답 없는 질문 3개가 전부 통과했던 게 이 지점이다.
    """
    calls, state = fake
    state["hits"] = [
        NoteHit(title="주제만 비슷한 노트", path="concepts/a.md", score=BELOW),
        NoteHit(title="더 낮은 노트", path="concepts/b.md", score=0.3),
    ]

    assert await retrieval.answer("BM25 하이브리드 검색?") == retrieval.NO_MATCH_MESSAGE
    assert calls["answered"] == []  # ← 여기가 깨지면 지어내기 시작한다
    assert calls["loaded"] == []  # GitHub 도 안 부른다


async def test_abstains_when_search_returns_nothing(fake):
    calls, state = fake
    state["hits"] = []
    assert await retrieval.answer("아무거나") == retrieval.NO_MATCH_MESSAGE
    assert calls["answered"] == []


async def test_only_hits_above_threshold_become_context(fake):
    """컷을 통과한 것만 로드하고 컨텍스트에 들어간다."""
    calls, state = fake
    state["hits"] = [
        NoteHit(title="통과A", path="concepts/a.md", score=ABOVE),
        NoteHit(title="탈락", path="concepts/b.md", score=BELOW),
        NoteHit(title="통과B", path="articles/c.md", score=0.99),
    ]
    state["contents"] = {
        "concepts/a.md": "A 원문",
        "concepts/b.md": "B 원문",
        "articles/c.md": "C 원문",
    }

    assert await retrieval.answer("질문") == "생성된 답변"
    assert calls["loaded"] == ["concepts/a.md", "articles/c.md"]  # 탈락한 건 안 읽는다

    names = [n.name for n in calls["answered"][0]]
    assert names == ["통과A", "통과B"]


async def test_drops_hits_without_path(fake):
    """metadata 가 없는 옛 벡터 — path 가 없으면 원본을 못 읽으므로 근거가 못 된다."""
    calls, state = fake
    state["hits"] = [NoteHit(title="메타데이터 없음", path="", score=0.99)]

    assert await retrieval.answer("질문") == retrieval.NO_MATCH_MESSAGE
    assert calls["loaded"] == []


async def test_partial_load_failure_still_answers(fake):
    """★ 5개 중 일부만 읽혀도 나머지로 답한다.

    gather 에서 return_exceptions=True 를 빼면 여기가 깨진다 —
    하나가 404 나는 순간 전체가 취소되어 LOAD_FAILED 로 떨어진다.
    """
    calls, state = fake
    state["hits"] = [
        NoteHit(title="읽힘", path="concepts/ok.md", score=ABOVE),
        NoteHit(title="삭제된노트", path="concepts/gone.md", score=ABOVE),
    ]
    state["contents"] = {"concepts/ok.md": "살아있는 원문"}

    assert await retrieval.answer("질문") == "생성된 답변"

    notes = calls["answered"][0]
    assert len(notes) == 1
    # ★ zip 으로 짝을 안 맞추면 여기서 이름이 밀린다
    assert notes[0].name == "읽힘"
    assert notes[0].content == "살아있는 원문"


async def test_all_loads_fail_reports_different_message(fake):
    """'못 찾음'과 '못 읽음'은 원인이 다르므로 문구가 달라야 한다."""
    calls, state = fake
    state["hits"] = [NoteHit(title="찾긴 찾음", path="concepts/gone.md", score=ABOVE)]
    state["contents"] = {}

    assert await retrieval.answer("질문") == retrieval.LOAD_FAILED_MESSAGE
    assert retrieval.LOAD_FAILED_MESSAGE != retrieval.NO_MATCH_MESSAGE
    assert calls["answered"] == []  # 근거가 없으면 여전히 LLM 을 안 부른다


async def test_threshold_boundary_is_inclusive(fake):
    """정확히 임계값이면 통과한다 (>= 이지 > 가 아니다)."""
    calls, state = fake
    state["hits"] = [
        NoteHit(title="딱 임계값", path="concepts/a.md", score=retrieval.SCORE_THRESHOLD)
    ]
    state["contents"] = {"concepts/a.md": "원문"}

    assert await retrieval.answer("질문") == "생성된 답변"


async def test_search_failure_propagates(fake, monkeypatch):
    """검색 실패는 보류가 아니라 오류다 — api 층이 Pinecone 안내로 바꾼다."""

    async def boom(question, top_k=5):
        raise RuntimeError("Pinecone Unauthorized")

    monkeypatch.setattr(retrieval.pinecone, "query", boom)
    with pytest.raises(RuntimeError):
        await retrieval.answer("질문")
