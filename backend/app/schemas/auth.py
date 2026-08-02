"""인증 요청/응답 데이터 모양.

TS 대응: src/app/api/auth/route.ts, src/app/api/auth/check/route.ts
LoginScreen.tsx 가 보내는 본문과 기대하는 응답 형태를 그대로 유지해야 한다.
"""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """POST /api/auth 요청 본문."""

    password: str


class LoginResponse(BaseModel):
    """로그인 결과. 토큰 자체는 본문이 아니라 Set-Cookie 헤더로 나간다.

    이유: HttpOnly 쿠키여야 JS가 토큰을 못 읽고, XSS로 탈취되지 않는다.
    """

    success: bool
    message: str = ""


class AuthCheckResponse(BaseModel):
    """GET /api/auth/check — 페이지 로드 시 로그인 상태 확인용."""

    authenticated: bool
