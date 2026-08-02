"""인증 엔드포인트.

TS 원본: src/app/api/auth/route.ts, src/app/api/auth/check/route.ts

    POST /api/auth        로그인 → 쿠키 발급
    GET  /api/auth/check  로그인 상태 확인

=== 2단계에서 구현 ===
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/auth")
async def login():
    """비밀번호 확인 후 HttpOnly 쿠키 발급.

    TS 대응: auth/route.ts:4-16

    TODO(2단계): 구현
      1. 인자로 body: LoginRequest, response: Response 를 받는다
      2. hmac.compare_digest(body.password, settings.auth_password) 로 비교
         ★ == 대신 compare_digest — 로그인은 무차별 시도의 표적이다
      3. 틀리면 raise HTTPException(401, "Unauthorized")
      4. 맞으면 token, _ = create_token()
         response.set_cookie(value=token, **cookie_kwargs())
         return LoginResponse(success=True)

      ※ set_cookie 는 Response 객체에 직접 해야 한다.
        FastAPI 핸들러 인자로 `response: Response` 를 선언하면 주입된다.
    """
    raise NotImplementedError


@router.get("/auth/check")
async def check():
    """페이지 로드 시 이미 로그인 상태인지 확인.

    ★ 여기서는 401 을 던지지 않고 {"authenticated": false} 를 200 으로 돌려준다.
      로그인 화면을 보여줄지 결정하는 용도라 '실패'가 아니기 때문.

    TS 대응: auth/check/route.ts

    TODO(2단계): 구현
      request.cookies.get(TOKEN_COOKIE) → verify_token → AuthCheckResponse
    """
    raise NotImplementedError
