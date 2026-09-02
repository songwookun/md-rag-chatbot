"""채팅 엔드포인트 — 프론트가 쓰는 단일 진입점.

TS 원본: src/app/api/chat/route.ts (253줄)


이 파일의 책임은 셋뿐이다
────────────────────────────────────────────────────────────────
    ① 인증          Depends(require_auth)
    ② 분기          질문이냐 저장이냐
    ③ 표현          예외 → 안내 문구, 결과 → 사용자 메시지

판단 로직은 services/ 로, 에러 문구 표는 core/errors.py 로 이미 빠졌다.
그래서 TS 의 253줄이 여기서는 훨씬 짧다.
**라우트 핸들러가 길어지고 있다면 로직이 잘못된 층에 있다는 신호다.**


정한 것
────────────────────────────────────────────────────────────────
① 실패해도 200 + 안내 문구로 돌려준다 (500 을 던지지 않는다)
   프론트(ChatWindow.tsx:63-66)가 응답의 reply 를 말풍선으로 그대로 렌더한다.
   500 을 던지면 사용자는 "무언가 잘못됨"만 보고 원인을 모른다.
   개인용 도구라 원인을 그대로 보여주는 쪽이 이득이 크다. TS 도 같은 판단을 했다.
   ※ 401 만 예외다 — 프론트가 상태 코드로 로그인 화면 전환을 판단한다.

② 어느 서비스 에러인지는 errors.detect_service 로 추정한다
   retrieval.answer 안에서 Pinecone·GitHub·Gemini 셋을 다 부르기 때문에
   api 층은 예외만 받고 출처를 모른다. 휴리스틱이고, 틀려도 원문이 노출된다.

③ 문장 만들기는 여기서 한다 (services 가 아니라)
   services/ingest.py 는 "무슨 일이 있었는지"만 알면 되고, 그걸 어떻게 보여줄지는
   표현 계층의 몫이다. 나중에 응답을 JSON 구조로 바꿔도 서비스는 안 건드린다.

④ 관련 노트 검색 실패는 사용자에게 알리지 않는다
   [[링크]]가 없는 것뿐이라 알려도 할 수 있는 게 없다. 로그에만 남긴다.
"""

from fastapi import APIRouter, Depends

from app.api.deps import require_auth
from app.core import errors
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import ingest as ingest_service
from app.services import intent as intent_service
from app.services import retrieval

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, _: None = Depends(require_auth)) -> ChatResponse:
    """메시지를 받아 저장하거나 답변한다. 실패해도 안내 문구를 담아 200 으로 돌려준다."""
    try:
        intent = await intent_service.classify(body.message)
    except Exception as exc:
        # 의도를 모르면 저장도 답변도 못 한다 — 여기서 끝낸다
        return _error_reply(exc)

    if intent == "question":
        try:
            return ChatResponse(reply=await retrieval.answer(body.message))
        except Exception as exc:
            return _error_reply(exc)

    try:
        result = await ingest_service.ingest(body.message)
    except Exception as exc:
        # 요약 실패 — 저장 실패는 예외로 오지 않고 result 안에 담겨 온다
        return _error_reply(exc)

    return ChatResponse(reply=_format_ingest_reply(result))


def _error_reply(exc: Exception) -> ChatResponse:
    """예외를 사용자용 안내 문구로. 상태 코드는 200 이다 (정한 것 ①)."""
    return ChatResponse(reply=errors.user_message(exc, errors.detect_service(exc)))


def _format_ingest_reply(result: ingest_service.IngestResult) -> str:
    """저장 결과 → 말풍선에 그대로 들어갈 마크다운 문자열.

    TS 대응: chat/route.ts:219-242
    """
    lines = [f"**{result.title}**", "", result.summary, ""]
    lines.append(f"**분류**: {result.category}")

    tag_line = " ".join(f"#{t}" for t in result.tags)
    related_line = ""
    if result.related:
        related_line = "\n**관련 노트**: " + ", ".join(f"[[{n}]]" for n in result.related)
    lines.append(f"**태그**: {tag_line}{related_line}")

    # 저장 상태 4분기 — 무엇이 됐고 무엇이 안 됐는지 정확히 알린다
    if result.github.ok and result.vector.ok:
        lines.append("\n✅ 저장 완료 (GitHub + 벡터DB)")
    elif result.github.ok:
        lines.append(f"\n✅ GitHub 저장 완료\n{result.vector.error}")
    elif result.vector.ok:
        lines.append(f"\n✅ 벡터DB 저장 완료\n{result.github.error}")
    else:
        lines.append(f"\n{result.github.error}\n{result.vector.error}")

    return "\n".join(lines)
