"""Gemini 어댑터 — 임베딩 생성 + 텍스트 생성.

TS 원본: src/lib/gemini.ts

adapters 의 규칙: **외부 호출과 프롬프트만** 둔다.
"저장이냐 질문이냐" 같은 판단은 services/ 로 간다 (TS에서는 한 파일에 섞여 있었다).

SDK 차이 메모 (TS @google/generative-ai → Python google-genai):
    TS:  genAI.getGenerativeModel({model}).generateContent(prompt)
    PY:  client.models.generate_content(model=..., contents=...)
    비동기가 필요하면 client.aio.models.generate_content(...)  ← FastAPI async 핸들러에선 이쪽

=== 3단계에서 구현 ===
"""

from app.schemas.chat import LoadedNote, SummaryResult

# 모델명은 TS와 동일하게 유지 (임베딩 차원 3072가 Pinecone 인덱스 설정과 묶여 있음)
GENERATION_MODEL = "gemini-2.5-flash"
EMBEDDING_MODEL = "gemini-embedding-001"


def _client():
    """google-genai 클라이언트를 만들어 반환 (한 번만 만들고 재사용).

    TS 대응: gemini.ts:3  new GoogleGenerativeAI(process.env.GEMINI_API_KEY!)

    TODO(3단계): 구현
      힌트 — from google import genai
             genai.Client(api_key=get_settings().gemini_api_key)
             매 호출마다 새로 만들지 않도록 모듈 전역 캐시나 @lru_cache 사용
    """
    raise NotImplementedError


async def embed(text: str, *, is_query: bool = False) -> list[float]:
    """텍스트 → 벡터. 문서 저장용과 질문 검색용을 같은 함수로 처리.

    ★ 왜 is_query 로 나누는가:
      같은 문장이라도 "저장되는 문서"와 "찾는 질문"은 벡터 공간에서 다르게
      배치돼야 검색이 잘 된다. Gemini는 task_type 으로 이를 지시한다.
        RETRIEVAL_DOCUMENT — 저장할 문서
        RETRIEVAL_QUERY    — 검색 질의
      이걸 안 맞추면 유사도 점수가 전반적으로 뭉개져서 임계값 0.6이 의미를 잃는다.

    TS 대응: gemini.ts:10-24

    TODO(3단계): 구현
      힌트 — from google.genai import types
             await _client().aio.models.embed_content(
                 model=EMBEDDING_MODEL,
                 contents=text,
                 config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"),
             )
             반환값에서 .embeddings[0].values 를 꺼내면 list[float]
             (SDK 버전마다 응답 모양이 조금 다르니 print 로 한 번 찍어볼 것)
    """
    raise NotImplementedError


async def summarize(text: str) -> SummaryResult:
    """입력을 제목/요약/태그/분류로 정리.

    ★ LLM은 요약·명명·분류만 시킨다. "관련 노트가 뭐냐"는 묻지 않는다 —
      그건 벡터 유사도(adapters/pinecone.find_related)가 훨씬 정확하다.
      LLM에게 사실 판단을 맡기지 않는 게 이 프로젝트의 원칙.

    TS 대응: gemini.ts:27-53

    TODO(3단계): 구현
      1. 프롬프트는 TS gemini.ts:33-45 원문을 그대로 옮긴다
      2. 응답 텍스트에서 ```json 코드블록 감싸기를 벗겨낸다
         힌트 — re.sub(r"```(?:json)?", "", text).strip()
      3. ★ TS는 JSON.parse 결과를 그대로 리턴했지만, 여기서는
         SummaryResult.model_validate_json(cleaned) 를 쓴다.
         형식이 틀리면 여기서 바로 걸려서 디버깅이 쉬워진다.

      더 나은 방법(여유되면): config=types.GenerateContentConfig(
          response_mime_type="application/json", response_schema=SummaryResult)
      로 스키마를 강제하면 코드블록 벗기기 자체가 불필요해진다.
    """
    raise NotImplementedError


async def classify_ambiguous(message: str) -> str:
    """규칙으로 판정 안 되는 애매한 메시지만 LLM에게 물어본다. "save" | "question" 반환.

    이 함수는 services/intent.py 에서 마지막 수단으로만 호출된다.
    (대부분의 입력은 규칙 단계에서 걸러져서 API 호출 비용이 안 든다)

    TS 대응: gemini.ts:72-83

    TODO(3단계): 구현
      프롬프트 원문은 gemini.ts:73-79
      응답에 "question" 이 포함되면 "question", 아니면 "save"
    """
    raise NotImplementedError


async def answer_from_notes(question: str, notes: list[LoadedNote]) -> str:
    """저장된 노트 원본만 근거로 답변 생성 (grounding).

    ★ 프롬프트의 "엄수 규칙"이 이 RAG의 핵심이다.
      모델이 학습으로 아는 외부 지식을 쓰지 못하게 막아야
      "내 노트 기반 답변"이라는 신뢰가 성립한다.
      프롬프트를 옮길 때 이 부분을 빼먹지 말 것.

    TS 대응: gemini.ts:87-112

    TODO(3단계): 구현
      1. notes 를 "--- [이름] ---\\n본문" 형태로 이어붙여 컨텍스트 생성
      2. 프롬프트 원문은 gemini.ts:95-108 그대로
      3. generate_content 결과의 .text 반환
    """
    raise NotImplementedError
