"""Gemini 어댑터 — 임베딩 생성 + 텍스트 생성.

TS 원본: src/lib/gemini.ts

adapters 의 규칙: **외부 호출과 프롬프트만** 둔다.
"저장이냐 질문이냐" 같은 판단은 services/ 로 간다 (TS에서는 한 파일에 섞여 있었다).

SDK 차이 메모 (TS @google/generative-ai → Python google-genai):
    TS:  genAI.getGenerativeModel({model}).generateContent(prompt)
    PY:  client.models.generate_content(model=..., contents=...)
    FastAPI async 핸들러에서는 client.aio.* 를 쓴다 — 동기 버전을 그냥 부르면
    이벤트 루프가 그동안 멈춰서 다른 요청까지 대기한다.
"""

import re
from functools import lru_cache

from google import genai
from google.genai import types

from app.config import get_settings
from app.schemas.chat import Intent, LoadedNote, SummaryResult

# 모델명은 TS와 동일하게 유지
GENERATION_MODEL = "gemini-2.5-flash"
EMBEDDING_MODEL = "gemini-embedding-001"

# 응답이 ```json ... ``` 로 감싸져 올 때 벗겨내기 위한 패턴
_CODE_FENCE = re.compile(r"```(?:json)?")


@lru_cache
def _client() -> genai.Client:
    """google-genai 클라이언트 (한 번만 만들고 재사용).

    TS 대응: gemini.ts:3
    """
    api_key = get_settings().gemini_api_key
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 가 설정되지 않았습니다")
    return genai.Client(api_key=api_key)


async def embed(text: str, *, is_query: bool = False) -> list[float]:
    """텍스트 → 벡터. 문서 저장용과 질문 검색용을 같은 함수로 처리.

    ★ 왜 is_query 로 나누는가:
      같은 문장이라도 "저장되는 문서"와 "찾는 질문"은 벡터 공간에서 다르게
      배치돼야 검색이 잘 된다. Gemini는 task_type 으로 이를 지시한다.
        RETRIEVAL_DOCUMENT — 저장할 문서
        RETRIEVAL_QUERY    — 검색 질의

      ※ 실험①은 "분기가 오히려 손해"라고 결론냈지만, 실험②에서 뒤집혔다.
        실제 코드가 임베딩하는 **요약** 기준으로는 현재 조합(DOCUMENT/QUERY)이
        더 높다(AUC 0.982 vs 0.972). 그래서 유지한다.
        근거: docs/notion/02_sweep_study.md 결정 3

    TS 대응: gemini.ts:10-24
    """
    resp = await _client().aio.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT",
            output_dimensionality=get_settings().embedding_dimensions,
        ),
    )
    return list(resp.embeddings[0].values)


async def _generate(prompt: str) -> str:
    """텍스트 생성 공통 호출. 세 프롬프트 함수가 이걸 공유한다."""
    resp = await _client().aio.models.generate_content(
        model=GENERATION_MODEL,
        contents=prompt,
    )
    return (resp.text or "").strip()


async def summarize(text: str) -> SummaryResult:
    """입력을 제목/요약/태그/분류로 정리.

    ★ LLM은 요약·명명·분류만 시킨다. "관련 노트가 뭐냐"는 묻지 않는다 —
      그건 벡터 유사도(pinecone.find_related)가 훨씬 정확하다.
      LLM에게 사실 판단을 맡기지 않는 게 이 프로젝트의 원칙.

    TS 대응: gemini.ts:27-53

    ★ TS는 JSON.parse 결과를 그대로 리턴했다 — 필드가 빠져 있어도 한참 뒤에 터진다.
      여기서는 SummaryResult 로 검증해서, 이 줄을 통과하면 형식이 보장된다.

    나중에: config 에 response_mime_type="application/json" + response_schema=SummaryResult
      를 주면 코드펜스 벗기기 자체가 없어진다. 먼저 이대로 돌려보고 바꿀 것.
    """
    prompt = f"""당신은 지식 정리 어시스턴트입니다.

사용자가 보낸 내용을 분석해서 아래 JSON 형식으로 정리해주세요.

입력: {text}

반드시 아래 JSON 형식으로만 응답하세요 (마크다운 코드블록 없이):
{{
  "title": "제목 (간결하게)",
  "summary": "핵심 내용 요약 (3-5문장)",
  "tags": ["태그1", "태그2", "태그3"],
  "category": "articles | concepts | projects 중 하나"
}}"""

    raw = await _generate(prompt)
    return SummaryResult.model_validate_json(_CODE_FENCE.sub("", raw).strip())


async def classify_ambiguous(message: str) -> Intent:
    """규칙으로 판정 안 되는 애매한 메시지만 LLM에게 물어본다. "save" | "question" 반환.

    services/intent.py 에서 마지막 수단으로만 호출된다.
    (대부분의 입력은 규칙 단계에서 걸러져서 API 호출 비용이 안 든다)

    TS 대응: gemini.ts:72-83
    """
    prompt = f"""사용자 메시지를 분류하세요.
- "save": 저장할 정보, 링크, 메모, 학습 내용
- "question": 질문, 검색, 이전에 저장한 내용에 대한 문의

"save" 또는 "question" 중 하나만 응답하세요.

메시지: "{message}\""""

    answer = (await _generate(prompt)).lower()
    # ★ 기본값이 "save" 인 게 안전한 쪽이다 — 질문으로 잘못 보면 사용자가 보낸 메모가
    #   저장되지 않고 사라지지만, 저장으로 잘못 보면 노트 하나가 더 생길 뿐이다.
    return "question" if "question" in answer else "save"


async def answer_from_notes(question: str, notes: list[LoadedNote]) -> str:
    """저장된 노트 원본만 근거로 답변 생성 (grounding).

    ★ 프롬프트의 "엄수 규칙"이 이 RAG의 핵심이다.
      모델이 학습으로 아는 외부 지식을 쓰지 못하게 막아야
      "내 노트 기반 답변"이라는 신뢰가 성립한다.

    TS 대응: gemini.ts:87-112
    """
    notes_context = "\n\n".join(f"--- [{n.name}] ---\n{n.content}" for n in notes)

    prompt = f"""당신은 사용자의 개인 지식 베이스(아래 [자료])만 근거로 답하는 어시스턴트입니다.

[자료] — 사용자가 저장한 노트 원본:
{notes_context}

---
사용자 질문: {question}

[엄수 규칙]
- 오직 위 [자료]에 실제로 적힌 내용만 근거로 답하세요. 당신이 학습으로 아는 외부 지식·사전 상식은 절대 사용하지 마세요.
- [자료]에 없는 내용은 추측하거나 보완하지 말고, 없다고 명시하세요: "저장된 노트에 해당 내용이 없습니다."
- 근거로 사용한 노트는 [[노트이름]] 형식으로 표시하세요.
- 여러 노트를 종합해도 되지만, [자료] 밖의 사실은 한 문장도 추가하지 마세요.
- 한국어로 답하세요."""

    return await _generate(prompt)
