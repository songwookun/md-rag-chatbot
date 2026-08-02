"""환경변수 → 타입 있는 설정 객체.

TS 대응: 각 파일에서 `process.env.GEMINI_API_KEY!` 로 흩어져 읽던 것을 한 곳으로 모음.
`!`(non-null 단언)는 런타임에 아무것도 검증하지 않지만, 여기서는 앱 기동 시점에
누락된 값을 잡아낸다 — "늦게 터지는 것보다 일찍 터지는 게 낫다".

이 파일은 0단계에서 완성된 상태. 수정할 일은 새 환경변수가 생길 때뿐.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env 파일에서 읽고, 대소문자 구분 안 함 (GEMINI_API_KEY → gemini_api_key)
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # NEXT_PUBLIC_* 같은 프론트 변수가 섞여도 무시
    )

    # --- 외부 서비스 ---
    gemini_api_key: str = ""
    github_token: str = ""
    github_repo: str = ""
    pinecone_api_key: str = ""
    pinecone_index: str = ""

    # --- 인증 ---
    auth_password: str = ""
    auth_secret: str = ""

    # --- 런타임 ---
    app_env: str = "development"

    @property
    def is_production(self) -> bool:
        """쿠키 Secure 플래그 분기용. TS: process.env.NODE_ENV === 'production'"""
        return self.app_env == "production"

    @property
    def signing_secret(self) -> str:
        """서명키. 별도 시크릿 있으면 그것, 없으면 로그인 비번 재사용.

        TS 대응: auth.ts:8-12 getSecret()
        """
        secret = self.auth_secret or self.auth_password
        if not secret:
            raise RuntimeError("AUTH_SECRET 또는 AUTH_PASSWORD 가 설정되지 않았습니다")
        return secret

    def missing_keys(self) -> list[str]:
        """비어 있는 필수 환경변수 이름 목록. /health 에서 사용."""
        required = {
            "GEMINI_API_KEY": self.gemini_api_key,
            "GITHUB_TOKEN": self.github_token,
            "GITHUB_REPO": self.github_repo,
            "PINECONE_API_KEY": self.pinecone_api_key,
            "PINECONE_INDEX": self.pinecone_index,
            "AUTH_PASSWORD": self.auth_password,
        }
        return [name for name, value in required.items() if not value]


@lru_cache
def get_settings() -> Settings:
    """캐시된 싱글턴. 매 요청마다 .env 를 다시 읽지 않게.

    FastAPI 의존성으로도 쓸 수 있다:  settings: Settings = Depends(get_settings)
    """
    return Settings()
