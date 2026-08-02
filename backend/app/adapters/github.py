"""GitHub 어댑터 — 노트 .md 파일 저장/로드/목록.

TS 원본: src/lib/github.ts

GitHub Contents API 를 httpx 로 직접 호출한다 (TS도 fetch 로 직접 호출했다).
PyGithub 같은 래퍼를 쓸 수도 있지만, 엔드포인트 3개뿐이라 직접 호출이 더 투명하다.

=== 3단계에서 구현 ===
"""

import httpx

API_BASE = "https://api.github.com"

# 노트가 분류되어 들어가는 폴더. summarize 의 category 값과 1:1 대응
FOLDERS = ("articles", "concepts", "projects")


def _headers(*, raw: bool = False) -> dict[str, str]:
    """공통 인증 헤더.

    raw=True 면 Accept 를 바꿔 base64 대신 파일 원문을 그대로 받는다.
    ★ 이게 없으면 응답이 base64 JSON 이라 디코딩 한 단계가 더 붙는다.

    TS 대응: github.ts:119  Accept: "application/vnd.github.raw"

    TODO(3단계): 구현
      Authorization: f"Bearer {settings.github_token}"
      raw 면 Accept: "application/vnd.github.raw"
    """
    raise NotImplementedError


async def save(*, path: str, content: str, message: str) -> None:
    """새 .md 파일을 레포에 커밋.

    GitHub Contents API 는 파일 내용을 base64로 요구한다 (원문 그대로 못 보냄).

    TS 대응: github.ts:8-40

    TODO(3단계): 구현
      PUT {API_BASE}/repos/{repo}/contents/{path}
      body: {"message": message,
             "content": base64.b64encode(content.encode()).decode()}
      힌트 — async with httpx.AsyncClient() as client: await client.put(...)
      응답이 2xx 아니면 예외를 던진다 (resp.raise_for_status()).
      ★ 상태코드가 에러 메시지에 남아야 core/errors.py 가 401/403/422 를 구분할 수 있다.
    """
    raise NotImplementedError


async def get_content(path: str) -> str:
    """단일 경로의 .md 원문을 로드.

    ★ small-to-big 의 '답변' 쪽 — 벡터DB의 요약이 아니라 이 원문으로 답을 만든다.
      요약만으로 답하면 세부 정보가 이미 날아간 상태라 답변 품질이 떨어진다.

    TS 대응: github.ts:112-125

    TODO(3단계): 구현
      GET {API_BASE}/repos/{repo}/contents/{path}  with _headers(raw=True)
      실패 시 예외. 반환은 resp.text
    """
    raise NotImplementedError


async def list_notes() -> list[dict]:
    """FOLDERS 안의 .md 파일 목록. [{"name":..., "path":...}, ...]

    name 은 파일명에서 ".md" 와 앞의 날짜 접두사("2026-08-01-")를 벗긴 것 —
    Obsidian [[링크]] 에 쓰기 좋은 형태로 맞춘 것.

    TS 대응: github.ts:43-74

    TODO(7단계): 구현
      폴더별로 GET .../contents/{folder}
      폴더가 없으면 404 가 나는데 이건 정상(아직 노트가 없는 것) → 건너뛴다
      정규식으로 접두사 제거: re.sub(r"^\\d{4}-\\d{2}-\\d{2}-", "", stem)
    """
    raise NotImplementedError


async def get_all_contents(limit: int = 30) -> list[dict]:
    """모든 노트의 원문을 병렬로 로드. 재색인(sync)용.

    TS 는 Promise.all 로 병렬 처리했다 → 파이썬은 asyncio.gather.
      results = await asyncio.gather(*[get_content(p) for p in paths],
                                     return_exceptions=True)
    ★ return_exceptions=True 를 주면 하나가 실패해도 나머지가 살아남는다.
      (안 주면 첫 예외에서 전체가 취소된다 — TS의 Promise.all 과 같은 동작)

    TS 대응: github.ts:77-109

    TODO(7단계): 구현
    """
    raise NotImplementedError
