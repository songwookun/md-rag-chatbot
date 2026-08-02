"""라우터 공용 의존성.

TS 대응: 각 route.ts 맨 위의 `if (!verifyAuthToken(req)) return unauthorizedResponse()`
반복이 사라지고, FastAPI 의존성으로 한 번만 선언하면 된다.

    @router.post("/chat")
    async def chat(req: ChatRequest, _=Depends(require_auth)):

=== 2단계에서 구현 ===
"""

from fastapi import Request

from app.core.security import TOKEN_COOKIE


async def require_auth(request: Request) -> None:
    """쿠키 토큰을 검증하고, 실패하면 401 을 던진다.

    ★ 반환값이 없다 — 통과 여부만 관심사이기 때문.
      (나중에 사용자 정보가 필요해지면 여기서 반환하도록 바꾸면 된다)

    TS 대응: auth.ts:53-58 unauthorizedResponse

    TODO(2단계): 구현
      raw = request.cookies.get(TOKEN_COOKIE)
      if not verify_token(raw):
          raise HTTPException(status_code=401,
                              detail="인증이 필요합니다. 다시 로그인해주세요.")

      ※ 프론트 계약 주의 — TS는 401 본문을 {"reply": "..."} 로 보냈다.
        FastAPI 기본 401 본문은 {"detail": "..."} 이다.
        ChatWindow.tsx 가 어느 키를 읽는지 확인하고, 다르면
        커스텀 exception handler 를 main.py 에 등록해 형태를 맞출 것.
    """
    raise NotImplementedError


async def require_bearer(request: Request) -> None:
    """collect 엔드포인트 전용 — Authorization: Bearer <AUTH_PASSWORD> 검사.

    ★ 왜 chat 과 인증 방식이 다른가:
      collect 는 브라우저가 아니라 외부 도구(iOS 단축어 등)가 호출하는 엔드포인트다.
      쿠키가 없으므로 헤더로 인증한다.

    TS 대응: collect/route.ts:10-13

    TODO(7단계): 구현
      header = request.headers.get("authorization")
      if header != f"Bearer {settings.auth_password}":
          raise HTTPException(401, "Unauthorized")

      ※ 여기도 문자열 == 비교는 타이밍 공격에 노출된다.
        hmac.compare_digest 로 바꾸는 게 낫다 (TS 원본은 == 로 되어 있음 — 개선 포인트).
    """
    raise NotImplementedError
