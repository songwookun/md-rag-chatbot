"""사용자 입력이 '저장할 내용'인지 '질문'인지 판별.

TS 원본: src/lib/gemini.ts:56-84 classifyIntent

★ 설계 포인트 — LLM 호출은 마지막 수단이다.
  규칙 3단으로 대부분을 걸러내고, 진짜 애매한 것만 LLM에게 넘긴다.
  이유: 매 메시지마다 API를 부르면 느리고, 비싸고, 결과도 흔들린다.
  코드가 확실히 아는 건 코드가 판단한다.

  ① URL 포함        → save  (링크를 던지는 건 저장 의도)
  ② 150자 이상      → save  (질문을 그렇게 길게 쓰지 않음)
  ③ 의문 표현 존재  → question
  ④ 그 외           → LLM (드묾)

=== 4단계에서 구현 (services는 직접 구현 영역) ===
"""

import re

from app.schemas.chat import Intent

# TS 대응: gemini.ts:62
URL_PATTERN = re.compile(r"https?://[^\s]+")

# 저장/질문을 가르는 길이 기준. TS: gemini.ts:65
LONG_TEXT_THRESHOLD = 150

# 한국어 의문 표현. TS 원문(gemini.ts:68-69)을 그대로 옮긴 것.
# ★ 순서 주의 — 이 검사는 ①②를 통과한 '짧은 텍스트'에만 적용된다.
#   "검색" 같은 단어가 들어간 긴 글은 질문이 아니라 저장이어야 하기 때문.
QUESTION_PATTERN = re.compile(
    r"[?？]|뭐|뭔|어때|어떻|어떡|왜|무엇|설명|알려|찾아|검색|어디|언제|누가|몇|얼마|인가|인지|할까|일까|줘$|줄래|있어|있나"
)


async def classify(message: str) -> Intent:
    """메시지 의도를 "save" 또는 "question" 으로 판별.

    TODO(4단계): 위 ①~④ 순서대로 구현
      1. text = message.strip()
      2. URL_PATTERN.search(text) 있으면 "save"
      3. len(text) >= LONG_TEXT_THRESHOLD 면 "save"
      4. QUESTION_PATTERN.search(text) 있으면 "question"
      5. 여기까지 왔으면 애매 → await gemini.classify_ambiguous(message) 결과 반환

      ★ 순서를 바꾸면 동작이 달라진다. 왜 이 순서인지 위 주석을 다시 볼 것.
    """
    raise NotImplementedError
