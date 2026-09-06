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

    # 임베딩 차원. Pinecone 인덱스를 만들 때 정한 값과 **반드시 같아야** 한다.
    #   실험②(docs/experiments/02-sweep.md 결정 2) 결론: 768 이면 AUC 손실 0.001 미만에
    #   저장량 25%. 다만 현재 인덱스가 3072 로 만들어져 있어 값만 바꾸면
    #   차원 불일치로 전부 실패한다 → 새 인덱스를 만든 뒤에 768 로 내릴 것.
    embedding_dimensions: int = 3072

    # --- 인증 ---
    auth_password: str = ""
    auth_secret: str = ""

    # --- 재순위화 (실험③에서 채택) ---
    #   실험③: 보류AUC 0.9605 → 1.0000, 층 누수 6/28 → 0/28, R@1 0.947 → 1.000.
    #   대가는 응답 +2.5초. 근거: docs/experiments/03-abstention.md
    #
    #   ★ false 로 두면 임베딩 점수만으로 자른다(실험③ 이전 동작).
    #     torch 가 2GB 라 작은 인스턴스에 배포할 때는 끄는 쪽이 맞을 수 있다.
    rerank_enabled: bool = True
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    #   ★ 기본이 cpu 인 이유 — 빨라서가 아니라 **흔들리지 않아서**다. 실측(5쌍 x 3000자):
    #       cpu  중앙 2.31초 · 최대 2.41초   폭 1.0배
    #       mps  중앙 1.92초 · 최대 2.06초   폭 1.2배 — 그런데 다른 회차에서 7.9초까지 튀었다
    #     중앙값은 mps 가 0.3초 빠르지만 목표(10초)를 깨는 건 중앙값이 아니라 꼬리다.
    #     그리고 도커/클라우드에도, 이 저장소를 클론한 대부분의 기계에도 mps 는 없다.
    #     기본을 cpu 로 두면 README 의 숫자가 그 사람들에게도 참이 된다.
    #     맥에서 조금 더 빠르게 쓰고 싶으면 RERANK_DEVICE=mps.
    rerank_device: str = "cpu"

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
