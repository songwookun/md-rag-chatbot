"""채팅 엔드포인트 — 백엔드의 단일 진입점.

TS 원본: src/app/api/chat/route.ts (253줄)

★ TS 원본은 253줄이었지만 여기는 훨씬 짧아야 한다.
  판단 로직은 services/ 로, 에러 문구는 core/errors.py 로 이미 빠졌기 때문.
  이 파일에 남는 책임은 세 가지뿐:
      ① 인증        (Depends)
      ② 분기        (질문이냐 저장이냐)
      ③ 예외 → 사용자 문구 변환

  라우트 핸들러가 길어지고 있다면 로직이 잘못된 층에 있다는 신호다.

=== 6단계에서 구현 ===
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/chat")
async def chat():
    """사용자 메시지를 받아 저장하거나 답변한다.

    TS 대응: chat/route.ts:51-253

    TODO(6단계): 구현

      시그니처:
        async def chat(body: ChatRequest, _=Depends(require_auth)) -> ChatResponse

      [1] 의도 분류
          try: intent = await intent_service.classify(body.message)
          except as e: return ChatResponse(reply=errors.user_message(e, "Gemini"))
          ★ 여기서 예외를 잡아 200 + 안내문으로 돌려주는 이유:
            프론트(ChatWindow.tsx)가 응답을 말풍선으로 그대로 렌더한다.
            500 을 던지면 사용자는 "무언가 잘못됨"만 보고 원인을 모른다.
            TS 원본도 같은 판단을 했다 (chat/route.ts:66-69).

      [2] 질문 모드
          try: return ChatResponse(reply=await retrieval.answer(body.message))
          except as e:
              어느 서비스에서 났는지 구분해 errors.user_message(e, ...) 호출
              ※ retrieval 안에서 Pinecone/GitHub/Gemini 셋 다 부르므로,
                서비스 구분이 필요하면 각각 전용 예외 클래스를 만들어
                retrieval 에서 감싸 던지는 방식이 깔끔하다.
                (처음엔 그냥 "Gemini" 로 두고 나중에 개선해도 된다)

      [3] 저장 모드
          result = await ingest.ingest(body.message)
          return ChatResponse(reply=_format_ingest_reply(result))
    """
    raise NotImplementedError


def _format_ingest_reply(result) -> str:
    """IngestResult → 사용자에게 보여줄 마크다운 문자열.

    ★ 문장 만들기를 서비스가 아니라 여기서 하는 이유:
      services/ingest.py 는 "무슨 일이 있었는지"만 알면 되고,
      그걸 어떻게 보여줄지는 표현 계층의 몫이다.
      나중에 응답을 JSON 구조로 바꾸고 싶어져도 서비스는 안 건드린다.

    TS 대응: chat/route.ts:219-242

    TODO(6단계): 구현
      제목 / 요약 / 분류 / 태그 / 관련 노트 를 나열하고,
      마지막에 저장 상태 4분기:
        github O, vector O → "저장 완료 (GitHub + 벡터DB)"
        github O, vector X → "GitHub 저장 완료" + vector_error
        github X, vector O → "벡터DB 저장 완료" + github_error
        둘 다 X           → 두 에러 메시지
    """
    raise NotImplementedError
