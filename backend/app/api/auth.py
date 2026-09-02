"""인증 엔드포인트.

TS 원본: src/app/api/auth/route.ts, src/app/api/auth/check/route.ts

    POST /api/auth        로그인 → 쿠키 발급
    GET  /api/auth/check  로그인 상태 확인
"""

import hmac

from fastapi import APIRouter, HTTPException, Request, Response

from app.config import get_settings
from app.core.security import TOKEN_COOKIE, cookie_kwargs, create_token, verify_token
from app.schemas.auth import AuthCheckResponse, LoginRequest, LoginResponse

router = APIRouter()


@router.post("/auth", response_model=LoginResponse)
async def login(body: LoginRequest, response: Response) -> LoginResponse:
    """비밀번호 확인 후 HttpOnly 쿠키 발급.

    TS 대응: auth/route.ts:4-16
    """
    # ★ == 대신 compare_digest — 로그인은 무차별 시도의 표적이다.
    # ※ compare_digest 는 str 을 받으면 ASCII 전용이다. 한글이 섞인 비밀번호에서
    #   TypeError 가 나므로 bytes 로 넘긴다.
    if not hmac.compare_digest(
        body.password.encode(), get_settings().auth_password.encode()
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token, _ = create_token()
    response.set_cookie(value=token, **cookie_kwargs())
    return LoginResponse(success=True)


@router.get("/auth/check", response_model=AuthCheckResponse)
async def check(request: Request) -> AuthCheckResponse:
    """페이지 로드 시 이미 로그인 상태인지 확인.

    ★ 미인증일 때 401 을 내야 한다.
      page.tsx:15 가 `if (res.ok) setAuthenticated(true)` 로 **상태 코드만** 본다.
      200 + {"authenticated": false} 로 돌려주면 항상 로그인된 것으로 처리되어
      로그인 화면이 영영 안 뜬다. (뼈대 주석에 200으로 적혀 있었으나 TS 원본이 맞다)

    TS 대응: auth/check/route.ts
    """
    if not verify_token(request.cookies.get(TOKEN_COOKIE)):
        raise HTTPException(status_code=401, detail="Unauthenticated")
    return AuthCheckResponse(authenticated=True)
