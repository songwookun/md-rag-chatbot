"""라우터 공용 의존성.

TS 대응: 각 route.ts 맨 위의 `if (!verifyAuthToken(req)) return unauthorizedResponse()`
반복이 사라지고, FastAPI 의존성으로 한 번만 선언하면 된다.

    @router.post("/chat")
    async def chat(req: ChatRequest, _=Depends(require_auth)):
"""

import hmac

from fastapi import HTTPException, Request

from app.config import get_settings
from app.core.security import TOKEN_COOKIE, verify_token

UNAUTHORIZED_MESSAGE = "인증이 필요합니다. 다시 로그인해주세요."


async def require_auth(request: Request) -> None:
    """쿠키 토큰을 검증하고, 실패하면 401 을 던진다.

    ★ 반환값이 없다 — 통과 여부만 관심사이기 때문.
      (나중에 사용자 정보가 필요해지면 여기서 반환하도록 바꾸면 된다)

    ※ 응답 본문 형태: TS는 {"reply": "..."} 였고 FastAPI 기본은 {"detail": "..."} 다.
      ChatWindow.tsx:58 이 `res.status === 401` 로 먼저 분기하고 본문을 읽지 않으므로
      프론트 동작에는 차이가 없다. 본문을 읽는 클라이언트가 생기면 그때 맞춘다.
    """
    if not verify_token(request.cookies.get(TOKEN_COOKIE)):
        raise HTTPException(status_code=401, detail=UNAUTHORIZED_MESSAGE)


async def require_bearer(request: Request) -> None:
    """collect 엔드포인트 전용 — Authorization: Bearer <AUTH_PASSWORD> 검사.

    ★ 왜 chat 과 인증 방식이 다른가:
      collect 는 브라우저가 아니라 외부 도구(iOS 단축어 등)가 호출하는 엔드포인트다.
      쿠키가 없으므로 헤더로 인증한다.

    TS 대응: collect/route.ts:10-13 (원본은 == 비교 — 여기서 개선했다)
    """
    header = request.headers.get("authorization") or ""
    expected = f"Bearer {get_settings().auth_password}"

    # ★ == 대신 compare_digest — 헤더 값도 무차별 시도의 표적이다.
    if not hmac.compare_digest(header.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")
