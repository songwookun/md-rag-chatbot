"""외부 수집 엔드포인트 — iOS 단축어 등 브라우저 밖에서 노트를 밀어넣는 통로.

TS 원본: src/app/api/collect/route.ts

chat 과의 차이:
    인증  쿠키가 아니라 Authorization: Bearer <AUTH_PASSWORD> 헤더
    입력  {"content": "..."}  (chat 은 {"message": "..."})
    출력  구조화된 JSON       (chat 은 사람이 읽을 문자열)
    분기  없음 — 무조건 저장 (질문 모드가 없다)

=== 7단계에서 구현 ===
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/collect")
async def collect():
    """외부에서 보낸 콘텐츠를 노트로 저장.

    TS 대응: collect/route.ts:8-95

    TODO(7단계): 구현

      시그니처:
        async def collect(body: CollectRequest, _=Depends(require_bearer))
        ※ CollectRequest(content: str) 를 schemas/chat.py 에 추가할 것

      본문은 services.ingest.ingest() 를 그대로 재사용한다.
        result = await ingest.ingest(body.content)
        return {"success": True, "title":..., "summary":..., "tags":...,
                "category":..., "saved": result.saved_to_github}

      ★ 여기서 리팩토링의 이득이 드러난다:
        TS 원본은 chat/route.ts 의 저장 로직(요약→관련노트→마크다운→저장)을
        collect/route.ts 에 통째로 복사해뒀다. 같은 코드가 두 벌이라
        한쪽만 고치면 동작이 갈린다.
        services/ingest.py 로 뽑아두면 두 엔드포인트가 같은 함수를 부른다.

      ★ 발견한 버그(TS 원본): collect 는 GitHub 에만 저장하고
        Pinecone upsert 를 하지 않는다 (collect/route.ts:67-78).
        그래서 단축어로 넣은 노트는 검색이 안 되고, sync 를 돌려야 잡힌다.
        ingest() 를 재사용하면 이 버그가 자동으로 사라진다.
    """
    raise NotImplementedError
