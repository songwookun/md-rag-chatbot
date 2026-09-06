"""의도 분류 — 규칙 세 개는 API 없이, LLM 폴백은 가짜 함수로.

★ 이 파일이 지키는 건 "순서"다. 규칙 각각이 맞게 도는지보다,
  두 신호가 동시에 걸릴 때 어느 쪽이 이기는지가 이 함수의 판단이다.
"""

import pytest

from app.services import intent


async def test_url_wins_over_question_words():
    """★ 순서 검증 — URL 과 의문표현이 둘 다 있으면 저장이다.

    "이 글 어때?" 는 의문표현이지만, 링크를 던지는 건 저장 의도다.
    의문표현 검사를 앞에 두면 이 입력이 question 으로 새어나간다.
    """
    assert await intent.classify("이 글 어때? https://example.com/post") == "save"


async def test_long_text_wins_over_question_words():
    """★ 순서 검증 — 길면 의문표현이 있어도 저장이다.

    긴 글에 "왜", "설명" 같은 단어가 섞이는 건 흔하다. 질문을 200자로 쓰지 않는다.
    """
    long_note = "React 서버 컴포넌트 정리. " * 20 + "왜 이렇게 동작하는지 메모"
    assert len(long_note) >= intent.LONG_TEXT_THRESHOLD
    assert await intent.classify(long_note) == "save"


async def test_question_words_classify_as_question():
    assert await intent.classify("메타하네스가 뭐야?") == "question"
    assert await intent.classify("RSC 설명해줘") == "question"


@pytest.mark.parametrize("length,expected", [(149, "question"), (150, "save")])
async def test_length_boundary_is_inclusive(length, expected):
    """정확히 150자에서 갈린다 (>= 이지 > 가 아니다). TS: gemini.ts:65

    149자 쪽은 의문표현("뭐")을 넣어 두 번째 규칙을 통과했을 때 어디로 가는지 본다.
    """
    text = "뭐" * length
    assert await intent.classify(text) == expected


async def test_strips_before_measuring(monkeypatch):
    """★ 공백을 안 벗기면 조용히 틀리는 경우.

    이 테스트는 원래 `classify(...) == "save"` 만 확인했는데, 그건 아무것도 못 지켰다.
      - strip 이 있으면  → 5자로 줄어 규칙을 다 통과 → LLM 폴백이 "save" 를 돌려준다
      - strip 이 없으면  → 165자라 길이 규칙에서 "save"
    **어느 쪽이든 "save" 라 통과했다.** 게다가 폴백이 모킹돼 있지 않아
    매 실행마다 실제 Gemini 를 호출하고 있었다.

    그래서 결과가 아니라 **폴백에 무엇이 넘어갔는지**를 본다.
    strip 이 빠지면 길이 규칙에서 끝나 spy 가 아예 안 불린다.
    """
    seen = {}

    async def spy(text):
        seen["text"] = text
        return "save"

    monkeypatch.setattr(intent.gemini, "classify_ambiguous", spy)

    padded = " " * 20 + "짧은 메모" + " " * 140
    assert len(padded) >= intent.LONG_TEXT_THRESHOLD  # strip 없으면 길이 규칙에 걸린다

    assert await intent.classify(padded) == "save"
    assert seen["text"] == "짧은 메모"   # ← strip 이 빠지면 KeyError 로 실패한다


async def test_trailing_space_does_not_break_dollar_anchor(monkeypatch):
    """QUESTION_PATTERN 의 `줘$` 는 끝 공백이 있으면 안 걸린다.

    "메모해줘" → True 인데 "메모해줘 " → False.
    strip 하면 둘 다 같은 결과가 나와야 한다.
    """
    monkeypatch.setattr(
        intent.gemini, "classify_ambiguous", _fail("폴백이 불리면 안 된다")
    )
    assert await intent.classify("정리해줘") == "question"
    assert await intent.classify("정리해줘 ") == "question"
    assert await intent.classify("정리해줘\n") == "question"


async def test_empty_input_abstains_instead_of_saving(monkeypatch):
    """공백만 들어오면 question — 빈 텍스트로 노트를 만들면 안 된다.

    ChatRequest(min_length=1) 이 빈 문자열은 막지만 공백 한 칸은 통과한다.
    """
    monkeypatch.setattr(intent.gemini, "classify_ambiguous", _fail("LLM 부르면 안 된다"))
    assert await intent.classify("   ") == "question"


async def test_falls_back_to_llm_only_when_ambiguous(monkeypatch):
    """★ 이 함수의 존재 이유 — 규칙에서 끝나면 API 를 안 부른다."""
    calls = []

    async def fake(message):
        calls.append(message)
        return "save"

    monkeypatch.setattr(intent.gemini, "classify_ambiguous", fake)

    # 규칙으로 판정되는 것들 — 폴백이 안 불려야 한다
    await intent.classify("https://example.com")
    await intent.classify("뭐야?")
    assert calls == []

    # 짧고 의문표현 없음 → 여기서만 LLM
    assert await intent.classify("메타하네스") == "save"
    assert calls == ["메타하네스"]  # strip 된 텍스트가 넘어간다


def _fail(reason):
    async def _raise(message):
        raise AssertionError(f"{reason}: {message!r}")

    return _raise
