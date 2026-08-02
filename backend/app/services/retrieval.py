"""RAG 검색 → 답변 파이프라인.

TS 원본: src/app/api/chat/route.ts:72-129

=== 5단계. 이 프로젝트에서 가장 중요한 파일 ===

흐름:
    질문
     → pinecone.query          벡터 유사도 top_k + 임계값. path만 받음
     → (0건이면 abstain)       ★ 지어내지 않고 보류
     → github.get_content      path로 원본 .md 병렬 로드 (small-to-big)
     → (0건이면 abstain)
     → gemini.answer_from_notes 원본을 근거로 생성

★ 이 구조를 왜 이렇게 짰는지 (면접에서 물어볼 법한 것들):

  1) small-to-big — '찾을 때'와 '답할 때' 쓰는 텍스트가 다르다.
     찾기: 요약 벡터 (짧고 노이즈 적어 검색 정확)
     답하기: 원본 .md (세부 정보가 살아있어 답변 품질 높음)
     둘을 잇는 게 metadata 의 path 다.

  2) abstention — 유사도가 임계값에 못 미치면 LLM을 아예 부르지 않는다.
     관련 없는 노트를 컨텍스트로 주면 모델이 억지로 답을 만들어낸다.
     "모른다"고 말하는 것이 RAG의 신뢰를 만든다.

  3) 부분 실패 허용 — 노트 5개 중 2개 로드 실패해도 나머지 3개로 답한다.
     전부 실패했을 때만 포기.
"""

from app.schemas.chat import LoadedNote

# 검색해올 후보 수. 늘리면 회수율↑ 컨텍스트 길이↑ 비용↑
TOP_K = 5

# abstain 시 사용자에게 보낼 문구 (TS: chat/route.ts:87-89, 115)
NO_MATCH_MESSAGE = (
    "저장된 노트 중 이 질문과 관련된 내용을 찾지 못했습니다. "
    "(지어내지 않고 답변을 보류합니다)"
)
LOAD_FAILED_MESSAGE = "관련 노트를 찾았지만 원본을 불러오지 못했습니다."


async def _load_notes(hits) -> list[LoadedNote]:
    """검색 결과의 path 들로 GitHub 원본을 병렬 로드. 실패한 건 조용히 버린다.

    TS 대응: chat/route.ts:95-106 (Promise.all + 개별 try)

    TODO(5단계): 구현
      results = await asyncio.gather(
          *[github.get_content(h.path) for h in hits],
          return_exceptions=True,          ← ★ 이게 없으면 하나 실패에 전체가 취소된다
      )
      isinstance(r, Exception) 인 건 스킵하고,
      나머지를 LoadedNote(name=hit.title, content=r) 로 만들어 반환.
      ※ zip(hits, results) 로 짝지어야 어떤 hit 의 결과인지 안 잃어버린다.
    """
    raise NotImplementedError


async def answer(question: str) -> str:
    """질문에 대한 답변 문자열 생성. 근거가 없으면 보류 문구를 반환.

    TODO(5단계): 구현

      [1] 검색
          hits = await pinecone.query(question, TOP_K)
          ※ 이 단계 실패는 예외로 올려보낸다 (api 층이 Pinecone 에러로 안내)

      [2] abstain #1 — 임계값에 다 걸러진 경우
          if not hits: return NO_MATCH_MESSAGE
          ★ 여기서 LLM을 부르고 싶은 유혹을 참는 게 핵심이다.
            "노트에 없지만 일반 지식으로 답해줄까?" → 그 순간 이건 RAG가 아니게 된다.

      [3] 원본 로드
          notes = await _load_notes(hits)

      [4] abstain #2 — 하나도 못 읽은 경우
          if not notes: return LOAD_FAILED_MESSAGE

      [5] 생성
          return await gemini.answer_from_notes(question, notes)

      === 나중에 개선해볼 것 ===
      - 답변에 근거 노트 목록을 붙여 반환하면 사용자가 출처를 확인할 수 있다
        (프롬프트가 이미 [[노트이름]] 표기를 요구하고 있으니 중복인지 먼저 볼 것)
      - hits 를 score 순으로 정렬해 상위 N개만 컨텍스트에 넣으면 토큰을 아낄 수 있다
    """
    raise NotImplementedError
