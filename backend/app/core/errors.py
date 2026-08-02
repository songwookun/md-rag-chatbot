"""외부 서비스 예외 → 사용자에게 보여줄 한글 메시지.

TS 원본: src/app/api/chat/route.ts:11-49 getErrorMessage()

왜 따로 두는가 — 라우트 핸들러(api/chat.py)는 "흐름"만 보이게 하고,
"이 에러는 이렇게 안내한다"는 표는 여기 모아두면 나중에 문구만 고치기 쉽다.

TS는 문자열 매칭(msg.includes("429"))으로 판별했다. 파이썬도 같은 방식을 쓰되,
각 SDK가 던지는 예외 타입을 알게 되면 isinstance 로 바꾸는 게 더 정확하다.

=== 6단계에서 구현 ===
"""

from typing import Literal

Service = Literal["Gemini", "GitHub", "Pinecone"]


def user_message(exc: Exception, service: Service) -> str:
    """예외를 사용자용 안내 문구로 변환.

    TODO(6단계): 아래 표대로 구현
      msg = str(exc) 로 문자열화한 뒤 부분 매칭.

      [Gemini]
        429 / quota / RESOURCE_EXHAUSTED → "Gemini API 사용량이 소진되었습니다..."
        401 / 403 / API_KEY_INVALID      → "Gemini API 키가 유효하지 않습니다..."
        404                              → "Gemini 모델을 찾을 수 없습니다..."

      [GitHub]
        401 / Bad credentials → "GitHub 토큰이 만료되었습니다..."
        403 / rate limit      → "GitHub API 호출 한도를 초과했습니다..."
        404                   → "GitHub 저장소를 찾을 수 없습니다. GITHUB_REPO 확인..."
        422                   → "같은 이름의 파일이 이미 존재합니다..."

      [Pinecone]
        401 / Unauthorized / UNAUTHENTICATED → "Pinecone API 키가 유효하지 않습니다..."
        404 / not found                      → "Pinecone 인덱스를 찾을 수 없습니다..."
        dimension                            → "벡터 차원 불일치. 3072로 재생성..."
        quota / limit                        → "Pinecone 무료 한도 초과..."

      매칭 안 되면 fallback: f"{service} 오류: {msg}"

      원문 문구는 src/app/api/chat/route.ts:11-49 에 그대로 있으니 복사해 쓸 것.
    """
    raise NotImplementedError
