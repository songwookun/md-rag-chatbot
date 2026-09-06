"""RAG 검색 → 답변 — 네트워크·모델 없이 abstention 을 검증한다.

★ 제일 중요한 건 "근거가 없으면 LLM 을 아예 부르지 않는다"이다.
  이게 깨져도 챗봇은 여전히 답을 한다 — 다만 **저장하지 않은 내용을 지어낼 뿐이다.**
  터지지 않으므로 테스트가 없으면 영영 모른다.

★ 실험③ 이후 순서가 바뀌었다: 로드 → 재순위 → 컷.
  재순위가 본문을 봐야 해서 로드가 컷보다 앞으로 왔다.
"""

import pytest

from app.config import get_settings
from app.schemas.chat import NoteHit
from app.services import retrieval


@pytest.fixture
def fake(monkeypatch):
    """어댑터를 전부 가짜로. 호출 기록으로 '무엇을 안 불렀는지'까지 검사한다."""
    calls = {"loaded": [], "answered": [], "reranked": []}
    state = {"hits": [], "contents": {}, "rerank": {}}

    async def fake_query(question, top_k=5):
        return state["hits"]

    async def fake_get_content(path):
        calls["loaded"].append(path)
        content = state["contents"].get(path)
        if content is None:
            raise RuntimeError(f"GitHub API error 404: {path}")
        return content

    async def fake_rerank(question, documents):
        calls["reranked"].append((question, list(documents)))
        # 본문 → 점수 표로 제어한다. 없으면 0점(= 컷)
        return [state["rerank"].get(d, 0.0) for d in documents]

    async def fake_answer(question, notes):
        calls["answered"].append(notes)
        return "생성된 답변"

    monkeypatch.setattr(retrieval.pinecone, "query", fake_query)
    monkeypatch.setattr(retrieval.github, "get_content", fake_get_content)
    monkeypatch.setattr(retrieval.reranker, "score", fake_rerank)
    monkeypatch.setattr(retrieval.gemini, "answer_from_notes", fake_answer)
    return calls, state


ABOVE = retrieval.RERANK_THRESHOLD + 0.1
BELOW = retrieval.RERANK_THRESHOLD - 0.1


# --- abstention -------------------------------------------------------


async def test_abstains_and_never_calls_llm_when_rerank_rejects_all(fake):
    """★ 이 파일에서 가장 중요한 테스트.

    재순위가 전부 컷 아래로 매기면 보류 문구를 돌려주고 **LLM 을 부르지 않는다.**
    실험③에서 리랭커가 답없음 28개를 전부 막은 게 이 경로다.
    """
    calls, state = fake
    state["hits"] = [
        NoteHit(title="주제만 비슷한 노트", path="concepts/a.md", score=0.90),
        NoteHit(title="다른 노트", path="concepts/b.md", score=0.88),
    ]
    state["contents"] = {"concepts/a.md": "A 원문", "concepts/b.md": "B 원문"}
    state["rerank"] = {"A 원문": BELOW, "B 원문": 0.001}

    assert await retrieval.answer("BM25 하이브리드 검색?") == retrieval.NO_MATCH_MESSAGE
    assert calls["answered"] == []  # ← 여기가 깨지면 지어내기 시작한다
    assert len(calls["reranked"]) == 1  # 재순위는 불렸다 (임베딩 점수가 높아도)


async def test_abstains_when_search_returns_nothing(fake):
    calls, state = fake
    state["hits"] = []
    assert await retrieval.answer("아무거나") == retrieval.NO_MATCH_MESSAGE
    assert calls["loaded"] == [] and calls["reranked"] == [] and calls["answered"] == []


async def test_drops_hits_without_path_before_loading(fake):
    """metadata 가 없는 옛 벡터 — path 가 없으면 원본을 못 읽으므로 근거가 못 된다.

    ★ 실험③ 이후 이 필터는 **로드 앞**에 있어야 한다. 뒤에 두면 get_content("") 를 부른다.
    """
    calls, state = fake
    state["hits"] = [NoteHit(title="메타데이터 없음", path="", score=0.99)]

    assert await retrieval.answer("질문") == retrieval.NO_MATCH_MESSAGE
    assert calls["loaded"] == []


# --- 재순위 ------------------------------------------------------------


async def test_only_documents_above_rerank_threshold_become_context(fake):
    """임베딩 순위가 아니라 **재순위 점수**가 컨텍스트를 정하고, 순서까지 바꾼다."""
    calls, state = fake
    state["hits"] = [
        NoteHit(title="임베딩1위", path="concepts/a.md", score=0.95),
        NoteHit(title="임베딩2위", path="concepts/b.md", score=0.90),
        NoteHit(title="임베딩3위", path="articles/c.md", score=0.85),
    ]
    state["contents"] = {"concepts/a.md": "A", "concepts/b.md": "B", "articles/c.md": "C"}
    # ★ 임베딩 1위를 재순위가 떨어뜨리고, 3위를 1위로 올린다 — 리랭커를 쓰는 이유다
    state["rerank"] = {"A": BELOW, "B": ABOVE, "C": 0.99}

    assert await retrieval.answer("질문") == "생성된 답변"

    names = [n.name for n in calls["answered"][0]]
    assert "임베딩1위" not in names            # 컷 아래는 빠진다
    assert names == ["임베딩3위", "임베딩2위"]  # ★ 재순위 점수 내림차순으로 넘어간다


async def test_context_order_follows_rerank_not_embedding(fake):
    """★ 컨텍스트 순서가 재순위를 따라야 한다.

    임베딩 순서를 그대로 두면 재순위가 뒤집은 순위가 LLM 에 반영되지 않는다.
    실험③에서 R@1 이 0.947 → 1.000 이 된 건 재순위가 1위를 바꿨기 때문이다.
    """
    calls, state = fake
    state["hits"] = [
        NoteHit(title=f"임베딩{i}위", path=f"c/{i}.md", score=0.9 - i * 0.01)
        for i in range(1, 4)
    ]
    state["contents"] = {f"c/{i}.md": f"D{i}" for i in range(1, 4)}
    # 임베딩 순서를 완전히 뒤집는 재순위 점수
    state["rerank"] = {"D1": 0.30, "D2": 0.60, "D3": 0.90}

    await retrieval.answer("질문")
    assert [n.name for n in calls["answered"][0]] == ["임베딩3위", "임베딩2위", "임베딩1위"]


async def test_rerank_threshold_is_inclusive(fake):
    """정확히 임계값이면 통과한다 (>= 이지 > 가 아니다)."""
    calls, state = fake
    state["hits"] = [NoteHit(title="딱 임계값", path="concepts/a.md", score=0.9)]
    state["contents"] = {"concepts/a.md": "A"}
    state["rerank"] = {"A": retrieval.RERANK_THRESHOLD}

    assert await retrieval.answer("질문") == "생성된 답변"


async def test_reranker_sees_full_body_not_title(fake):
    """재순위에 **본문**이 들어가야 한다.

    실험③은 본문으로 측정했다. 요약이나 제목으로 바꾸면 검증되지 않은 설정이 된다.
    """
    calls, state = fake
    state["hits"] = [NoteHit(title="짧은제목", path="concepts/a.md", score=0.9)]
    state["contents"] = {"concepts/a.md": "본문 전체가 여기 들어간다" * 20}
    state["rerank"] = {state["contents"]["concepts/a.md"]: ABOVE}

    await retrieval.answer("질문")
    _, docs = calls["reranked"][0]
    assert docs == [state["contents"]["concepts/a.md"]]


# --- 부분 실패 ---------------------------------------------------------


async def test_partial_load_failure_still_answers(fake):
    """★ 일부만 읽혀도 나머지로 답한다.

    gather 에서 return_exceptions=True 를 빼면 404 하나에 전체가 취소된다.
    """
    calls, state = fake
    state["hits"] = [
        NoteHit(title="읽힘", path="concepts/ok.md", score=0.9),
        NoteHit(title="삭제된노트", path="concepts/gone.md", score=0.9),
    ]
    state["contents"] = {"concepts/ok.md": "살아있는 원문"}
    state["rerank"] = {"살아있는 원문": ABOVE}

    assert await retrieval.answer("질문") == "생성된 답변"
    notes = calls["answered"][0]
    assert len(notes) == 1
    assert notes[0].name == "읽힘"  # zip 으로 짝을 안 맞추면 이름이 밀린다


async def test_all_loads_fail_reports_different_message(fake):
    """'못 찾음'과 '못 읽음'은 원인이 다르므로 문구가 달라야 한다."""
    calls, state = fake
    state["hits"] = [NoteHit(title="찾긴 찾음", path="concepts/gone.md", score=0.9)]
    state["contents"] = {}

    assert await retrieval.answer("질문") == retrieval.LOAD_FAILED_MESSAGE
    assert retrieval.LOAD_FAILED_MESSAGE != retrieval.NO_MATCH_MESSAGE
    assert calls["answered"] == [] and calls["reranked"] == []


async def test_search_failure_propagates(fake, monkeypatch):
    """검색 실패는 보류가 아니라 오류다 — api 층이 Pinecone 안내로 바꾼다."""

    async def boom(question, top_k=5):
        raise RuntimeError("Pinecone Unauthorized")

    monkeypatch.setattr(retrieval.pinecone, "query", boom)
    with pytest.raises(RuntimeError):
        await retrieval.answer("질문")


# --- 재순위 끄기 -------------------------------------------------------


async def test_falls_back_to_embedding_score_when_rerank_disabled(fake, monkeypatch):
    """★ RERANK_ENABLED=false 면 실험③ 이전 동작(임베딩 점수 컷)으로 돌아간다.

    torch 가 2GB 라 작은 인스턴스에 배포할 때 필요한 경로다.
    """
    calls, state = fake
    monkeypatch.setenv("RERANK_ENABLED", "false")
    get_settings.cache_clear()

    state["hits"] = [
        NoteHit(title="통과", path="concepts/a.md", score=retrieval.SCORE_THRESHOLD),
        NoteHit(title="탈락", path="concepts/b.md", score=retrieval.SCORE_THRESHOLD - 0.01),
    ]
    state["contents"] = {"concepts/a.md": "A", "concepts/b.md": "B"}

    assert await retrieval.answer("질문") == "생성된 답변"
    assert [n.name for n in calls["answered"][0]] == ["통과"]
    assert calls["reranked"] == []  # 재순위를 아예 안 부른다
