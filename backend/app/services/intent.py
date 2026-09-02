"""사용자 입력이 '저장할 내용'인지 '질문'인지 판별.

TS 원본: src/lib/gemini.ts:56-84 classifyIntent

★ 설계 포인트 — LLM 호출은 마지막 수단이다.
  규칙으로 대부분을 걸러내고, 진짜 애매한 것만 LLM에게 넘긴다.
  이유: 매 메시지마다 API를 부르면 느리고, 비싸고, 결과도 흔들린다.
  코드가 확실히 아는 건 코드가 판단한다.

=== 여기부터 직접 구현 ===
"""

import re

from app.adapters import gemini
from app.schemas.chat import Intent

# TS 대응: gemini.ts:62
URL_PATTERN = re.compile(r"https?://[^\s]+")

# 저장/질문을 가르는 길이 기준. TS: gemini.ts:65
# ※ 근거 없는 값이다 — notebooks/README.md 검증대상 #6. 아직 아무도 재지 않았다.
LONG_TEXT_THRESHOLD = 150

# 한국어 의문 표현. TS 원문(gemini.ts:68-69)을 그대로 옮긴 것.
# ※ 검증대상 #7 — 이 정규식이 실제로 질문을 잡는지도 측정된 적 없다.
QUESTION_PATTERN = re.compile(
    r"[?？]|뭐|뭔|어때|어떻|어떡|왜|무엇|설명|알려|찾아|검색|어디|언제|누가|몇|얼마|인가|인지|할까|일까|줘$|줄래|있어|있나"
)


async def classify(message: str) -> Intent:
    """메시지 의도 판별.

    계약
      입력  message: 사용자가 보낸 원문 (앞뒤 공백 포함 가능)
      출력  "save" | "question"   ← ★ Intent 는 Enum 이 아니라 Literal 이다.
            Intent.SAVE 같은 멤버가 없으므로 문자열을 그대로 반환한다.
      예외  LLM 호출이 실패하면 그대로 올려보낸다 (api/chat.py 가 안내 문구로 바꾼다)
      제약  대부분의 입력에서 API 를 부르지 않는다. 규칙 세 개가 먼저 걸러낸다.

    === 정한 것 ===

    ① 맨 처음에 strip() 한다
       안 하면 두 군데가 조용히 틀린다 (터지지 않아서 더 나쁘다):
         - 길이: 공백으로 패딩된 5자 메모가 165자로 세어져 save 로 간다
         - 의문표현: QUESTION_PATTERN 의 `줘$` 가 끝 공백에서 안 걸린다.
           "메모해줘" → True 인데 "메모해줘 " → False.
           개행은 통과한다($ 가 끝 개행 앞을 매칭) — 공백이냐 개행이냐로 결과가 갈린다.
       TS 도 같은 이유로 첫 줄이 message.trim() 이다 (gemini.ts:59).

    ② 규칙 순서: URL → 길이 → 의문표현
       순서가 결과를 바꾸는 입력이 실제로 있다.
         "이 글 어때? https://..."   URL 도 있고 의문표현도 있다 → **저장**
            링크를 던지는 건 저장 의도다. 링크에 감상 한 줄을 붙였다고 질문이 되지 않는다.
         "...(200자)... 왜 이렇게 동작하는지 메모"  길면서 의문표현도 있다 → **저장**
            질문을 200자로 쓰지 않는다. 긴 글은 저장할 내용이다.
       즉 **확실한 신호(URL·길이)를 약한 신호(단어 매칭)보다 앞에 둔다.**
       의문표현 정규식은 "검색", "설명" 같은 흔한 단어를 잡아서 오탐이 많다.

    ③ 길이 비교는 >= 다 (> 아님)
       TS 가 `text.length >= 150`. 정확히 150자에서 결과가 갈리므로 맞춰 둔다.
       ※ 150 자체는 근거 없는 값이다 — notebooks/README.md 검증대상 #6.

    ④ 규칙 셋 다 아니면 LLM 에 넘긴다 (세 번째 상태를 만들지 않는다)
       "메타하네스", "RSC 정리" 처럼 짧고 의문표현 없는 입력이 여기 온다.
       "unknown" 을 만들어 사용자에게 되묻는 선택지도 있었지만, 챗봇 흐름이 끊기고
       api/chat.py 가 3분기가 된다. 여기 오는 입력이 드물어 LLM 비용도 거의 안 든다.

    ⑤ strip 후 빈 문자열이면 "question"
       ChatRequest(min_length=1) 이 빈 문자열은 막지만 공백 한 칸은 통과한다.
       ★ ④의 폴백 기본값은 "save" 인데(메모를 잃는 게 노트 하나 느는 것보다 아프다)
         여기서는 반대로 간다. **기준이 "사용자가 보낸 내용을 잃지 않는다"이고,
         빈 입력은 잃을 내용이 없기 때문이다.**
         save 로 보내면 빈 텍스트로 Gemini 를 부르고 쓰레기 노트가 레포에 커밋된다.
         question 으로 보내면 retrieval 이 근거를 못 찾아 보류 문구를 돌려준다.

    검증
      tests/test_intent.py — 규칙 세 개는 API 없이 돈다. LLM 폴백은 monkeypatch.
    """
    text = message.strip()

    # ⑤ 빈 입력 — 저장할 내용이 없다
    if not text:
        return "question"

    # ① URL 포함 → 저장 (링크를 던지는 건 저장 의도)
    if URL_PATTERN.search(text):
        return "save"

    # ② 긴 텍스트 → 저장 (질문을 이렇게 길게 쓰지 않는다)
    if len(text) >= LONG_TEXT_THRESHOLD:
        return "save"

    # ③ 짧은 텍스트 + 의문 표현 → 질문
    if QUESTION_PATTERN.search(text):
        return "question"

    # ④ 짧고 의문 표현도 없음 = 진짜 애매 → 여기서만 LLM (드묾)
    return await gemini.classify_ambiguous(text)
