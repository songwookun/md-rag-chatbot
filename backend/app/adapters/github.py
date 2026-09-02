"""GitHub 어댑터 — 노트 .md 파일 저장/로드/목록.

TS 원본: src/lib/github.ts

GitHub Contents API 를 httpx 로 직접 호출한다 (TS도 fetch 로 직접 호출했다).
PyGithub 같은 래퍼를 쓸 수도 있지만, 엔드포인트 3개뿐이라 직접 호출이 더 투명하다.
"""

import asyncio
import base64
import logging
import re
from functools import lru_cache

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

API_BASE = "https://api.github.com"

# 노트가 분류되어 들어가는 폴더. summarize 의 category 값과 1:1 대응
FOLDERS = ("articles", "concepts", "projects")

# 파일명 앞의 "2026-09-02-" 접두사. list_notes 가 벗겨낸다.
_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")

# httpx 기본 timeout 은 5초라 큰 노트에서 ReadTimeout 이 난다.
# None(무한 대기)은 더 나쁘다 — 한 요청이 영원히 매달린다.
_TIMEOUT = 30.0


@lru_cache
def _client() -> httpx.AsyncClient:
    """모듈 전역 HTTP 클라이언트 (연결 재사용).

    ★ 매 호출마다 AsyncClient 를 새로 만들면 TCP/TLS 핸드셰이크를 매번 다시 한다.
      get_all_contents 처럼 20~30개를 병렬로 부를 때 차이가 크다.
    """
    return httpx.AsyncClient(timeout=_TIMEOUT)


async def close() -> None:
    """앱 종료 시 연결 정리. main.py 의 lifespan 에서 호출한다."""
    await _client().aclose()
    _client.cache_clear()


def _repo() -> str:
    """레포 설정 검증. TS 대응: github.ts:1-6 getGitHubConfig"""
    settings = get_settings()
    if not settings.github_token or not settings.github_repo:
        raise RuntimeError("GitHub not configured (GITHUB_TOKEN / GITHUB_REPO)")
    return settings.github_repo


def _headers(*, raw: bool = False) -> dict[str, str]:
    """공통 인증 헤더.

    raw=True 면 Accept 를 바꿔 base64 대신 파일 원문을 그대로 받는다.
    ★ 이게 없으면 응답이 base64 JSON 이라 디코딩 한 단계가 더 붙는다.

    TS 대응: github.ts:119
    """
    headers = {"Authorization": f"Bearer {get_settings().github_token}"}
    if raw:
        headers["Accept"] = "application/vnd.github.raw"
    return headers


def _raise_for_status(resp: httpx.Response, context: str) -> None:
    """실패 응답을 예외로. 상태코드와 GitHub 의 message 를 **문자열에 남긴다**.

    ★ 이게 core/errors.py 와의 계약이다.
      errors.user_message 가 "401" / "Bad credentials" / "422" 같은 조각을 문자열에서 찾는다.
      httpx 기본 raise_for_status 는 상태코드는 남기지만 GitHub 이 준 사유("Bad credentials")는
      버린다. 그래서 직접 만든다.
    """
    if resp.is_success:
        return
    try:
        detail = resp.json().get("message", "")
    except Exception:
        detail = resp.text[:200]
    raise RuntimeError(f"GitHub API error {resp.status_code} ({context}): {detail}")


async def save(*, path: str, content: str, message: str) -> None:
    """새 .md 파일을 레포에 커밋.

    GitHub Contents API 는 파일 내용을 base64로 요구한다 (원문 그대로 못 보냄).

    TS 대응: github.ts:8-40
    """
    resp = await _client().put(
        f"{API_BASE}/repos/{_repo()}/contents/{path}",
        headers=_headers(),
        json={
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
        },
    )
    _raise_for_status(resp, f"save {path}")


async def get_content(path: str) -> str:
    """단일 경로의 .md 원문을 로드.

    ★ small-to-big 의 '답변' 쪽 — 벡터DB의 요약이 아니라 이 원문으로 답을 만든다.
      요약만으로 답하면 세부 정보가 이미 날아간 상태라 답변 품질이 떨어진다.

    TS 대응: github.ts:112-125
    """
    resp = await _client().get(
        f"{API_BASE}/repos/{_repo()}/contents/{path}",
        headers=_headers(raw=True),
    )
    _raise_for_status(resp, f"load {path}")
    return resp.text


async def list_notes() -> list[dict]:
    """FOLDERS 안의 .md 파일 목록. [{"name":..., "path":...}, ...]

    name 은 파일명에서 ".md" 와 날짜 접두사를 벗긴 것 —
    옵시디언 [[링크]] 에 쓰기 좋은 형태로 맞춘 것.

    TS 대응: github.ts:43-74
    """
    repo = _repo()
    notes: list[dict] = []

    for folder in FOLDERS:
        resp = await _client().get(
            f"{API_BASE}/repos/{repo}/contents/{folder}", headers=_headers()
        )
        # ★ 404 를 에러로 보지 않는다 — "아직 그 폴더에 노트가 없다"는 정상 상태다.
        #   실패로 처리하면 노트가 하나도 없는 새 볼트에서 전체가 죽는다.
        if not resp.is_success:
            continue
        for entry in resp.json():
            name = entry.get("name", "")
            if not name.endswith(".md"):
                continue
            notes.append(
                {
                    "name": _DATE_PREFIX.sub("", name.removesuffix(".md")),
                    "path": entry["path"],
                }
            )
    return notes


async def get_all_contents(limit: int | None = 30) -> list[dict]:
    """모든 노트의 원문을 병렬로 로드. 재색인(sync)용.

    TS 는 Promise.all 로 병렬 처리했다 → 파이썬은 asyncio.gather.

    TS 대응: github.ts:77-109

    ★ limit 은 원본(github.ts:84)의 `notes.slice(0, 30)` 을 옮긴 것인데,
      TS 는 31번째부터를 **아무 말 없이 버렸다**(notebooks/README.md 검증대상 #9).
      노트가 30개를 넘으면 재색인이 조용히 일부만 하고 "완료"라고 답한다.
      여기서는 잘릴 때 경고 로그를 남겨 최소한 드러나게 했다.
      limit=None 이면 전부 가져온다 — 노트가 늘면 이쪽으로 바꾸고 동시 실행 수를 제한할 것.
    """
    notes = await list_notes()
    if limit is not None and len(notes) > limit:
        log.warning(
            "노트 %d개 중 %d개만 로드합니다 (limit=%d). 나머지는 재색인되지 않습니다.",
            len(notes),
            limit,
            limit,
        )
        notes = notes[:limit]

    # ★ return_exceptions=True — 없으면 하나가 실패하는 순간 나머지가 전부 취소된다.
    #   재색인은 "되는 것만이라도 되는" 게 낫다.
    results = await asyncio.gather(
        *(get_content(note["path"]) for note in notes),
        return_exceptions=True,
    )

    loaded = []
    for note, result in zip(notes, results):
        if isinstance(result, BaseException):
            log.warning("노트 로드 실패, 건너뜁니다: %s (%s)", note["path"], result)
            continue
        loaded.append({**note, "content": result})
    return loaded
